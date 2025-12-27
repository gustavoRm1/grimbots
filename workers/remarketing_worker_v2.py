import json
import os
import sys
import time
import signal
import threading
import logging
import random

import requests

# Garantir que o diretório raiz do projeto esteja no sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from redis_manager import get_redis_connection

# -------------------------------------------------
# Logging
# -------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "remarketing_worker.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("remarketing-worker")

# -------------------------------------------------
# Rate limit por token (thread-safe)
# -------------------------------------------------
_rate_lock = threading.Lock()
_last_send_ts = {}
_min_interval_seconds = 1.2


def _rate_limit(token: str):
    if not token:
        return
    with _rate_lock:
        last_ts = _last_send_ts.get(token)
        now = time.time()
        sleep_for = 0.0
        if last_ts is not None:
            elapsed = now - last_ts
            if elapsed < _min_interval_seconds:
                sleep_for = _min_interval_seconds - elapsed
        _last_send_ts[token] = now + sleep_for
    if sleep_for > 0:
        time.sleep(sleep_for)


# -------------------------------------------------
# Envio Telegram direto via requests
# -------------------------------------------------
def send_telegram_message(token: str, chat_id: str, message: str,
                          media_url: str = None, media_type: str = 'video',
                          buttons: list = None, timeout_sec: int = 5):
    base_url = f"https://api.telegram.org/bot{token}"

    # Inline keyboard
    reply_markup = None
    if buttons:
        inline_keyboard = []
        for button in buttons:
            button_dict = {'text': button.get('text')}
            if button.get('url'):
                button_dict['url'] = button['url']
            elif button.get('callback_data'):
                button_dict['callback_data'] = button['callback_data']
            else:
                button_dict['callback_data'] = 'button_pressed'
            inline_keyboard.append([button_dict])
        reply_markup = {'inline_keyboard': inline_keyboard}

    def _post(url, payload):
        _rate_limit(token)
        with requests.Session() as session:
            return session.post(url, json=payload, timeout=timeout_sec)

    try:
        if media_url:
            caption_text = message[:1500] if len(message) > 1500 else message
            if media_type == 'photo':
                url = f"{base_url}/sendPhoto"
                payload = {
                    'chat_id': chat_id,
                    'photo': media_url,
                    'caption': caption_text,
                    'parse_mode': 'HTML'
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                response = _post(url, payload)
            elif media_type == 'video':
                url = f"{base_url}/sendVideo"
                payload = {
                    'chat_id': chat_id,
                    'video': media_url,
                    'caption': caption_text,
                    'parse_mode': 'HTML'
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                response = _post(url, payload)
            elif media_type == 'audio':
                url = f"{base_url}/sendAudio"
                payload = {
                    'chat_id': chat_id,
                    'audio': media_url,
                    'caption': caption_text,
                    'parse_mode': 'HTML'
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                response = _post(url, payload)
            else:
                # fallback texto
                url = f"{base_url}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                response = _post(url, payload)
        else:
            url = f"{base_url}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            if reply_markup:
                payload['reply_markup'] = reply_markup
            response = _post(url, payload)

        result_data = None
        try:
            if getattr(response, 'content', None):
                result_data = response.json()
        except Exception:
            logger.warning(f"⚠️ Telegram retornou 200 sem JSON parseável | chat_id={chat_id}")

        if response.status_code == 200 and (not result_data or result_data.get('ok')):
            return result_data or True

        error_description = result_data.get('description', 'Erro desconhecido') if isinstance(result_data, dict) else 'Resposta inválida'
        error_code = result_data.get('error_code', response.status_code) if isinstance(result_data, dict) else response.status_code

        if response.status_code == 403 and isinstance(error_description, str) and 'user is deactivated' in error_description.lower():
            return {'error': True, 'error_code': 403, 'description': error_description, 'deactivated': True}

        logger.error(f"❌ Erro Telegram: status={response.status_code}, error_code={error_code}, desc={error_description}")
        return {'error': True, 'error_code': error_code, 'description': error_description}

    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout ao enviar mensagem para chat {chat_id}")
        return {'error': True, 'error_code': -1, 'description': 'timeout'}
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem Telegram: {e}", exc_info=True)
        return {'error': True, 'error_code': -1, 'description': str(e)}


# -------------------------------------------------
# Worker loop
# -------------------------------------------------
stop_event = threading.Event()


def shutdown(sig, frame):
    logger.warning("🛑 Shutdown recebido, encerrando worker...")
    stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


def process_job(job: dict):
    bot_id = job.get('bot_id')
    campaign_id = job.get('campaign_id')
    chat_id = job.get('telegram_user_id')
    message = job.get('message', '') or ''
    media_url = job.get('media_url')
    media_type = job.get('media_type')
    buttons = job.get('buttons')
    audio_enabled = bool(job.get('audio_enabled'))
    audio_url = job.get('audio_url')
    token = job.get('bot_token')

    if not token:
        logger.error(f"❌ Job sem token: bot_id={bot_id} campaign_id={campaign_id} chat_id={chat_id}")
        return

    # Blacklist (Redis set opcional): remarketing:blacklist:{bot_id}
    try:
        redis_conn = get_redis_connection()
        blk_key = f"remarketing:blacklist:{bot_id}"
        if redis_conn.sismember(blk_key, str(chat_id)):
            logger.info(f"🚫 Chat em blacklist, ignorando: bot_id={bot_id} chat_id={chat_id}")
            return
    except Exception:
        pass

    try:
        send_result = send_telegram_message(
            token=token,
            chat_id=str(chat_id),
            message=message,
            media_url=media_url,
            media_type=media_type,
            buttons=buttons
        )
    except Exception as send_error:
        logger.error(
            f"❌ ERRO REAL AO ENVIAR REMARKETING | bot_id={bot_id} campaign_id={campaign_id} chat_id={chat_id} err={send_error}",
            exc_info=True
        )
        send_result = {'error': True, 'error_code': -1, 'description': str(send_error)}

    error_code = None
    if isinstance(send_result, dict) and send_result.get('error'):
        error_code = int(send_result.get('error_code') or 0)
        desc = (send_result.get('description') or '').lower()
        if error_code == 403 and ('bot was blocked' in desc or 'forbidden: bot was blocked' in desc):
            try:
                redis_conn = get_redis_connection()
                redis_conn.sadd(f"remarketing:blacklist:{bot_id}", str(chat_id))
            except Exception:
                pass
        if error_code in (0, -1):
            time.sleep(2)
            return
    elif send_result and audio_enabled and audio_url:
        try:
            send_telegram_message(
                token=token,
                chat_id=str(chat_id),
                message="",
                media_url=audio_url,
                media_type='audio',
                buttons=None
            )
        except Exception:
            pass


def drain(bot_id: int):
    redis_conn = get_redis_connection()
    queue_key = f"remarketing:queue:{bot_id}"
    logger.info(f"🚀 Iniciando drain da fila {queue_key}")
    msg_counter = 0

    while not stop_event.is_set():
        item = redis_conn.blpop(queue_key, timeout=5)
        if not item:
            break

        _, raw = item
        try:
            job = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode('utf-8'))
        except Exception:
            logger.warning(f"⚠️ Job inválido (JSON parse falhou): bot_id={bot_id}")
            continue

        logger.debug(f"📥 Remarketing dequeue bot_id={bot_id} chat_id={job.get('telegram_user_id')}")

        job_type = job.get('type')
        if job_type == 'campaign_done':
            logger.info(f"🏁 Campaign DONE bot_id={bot_id} campaign_id={job.get('campaign_id')}")
            continue

        process_job(job)

        msg_counter += 1
        time.sleep(random.uniform(1.2, 2.5))
        if msg_counter % 100 == 0:
            logger.info(f"⏸️ Micro pause remarketing bot_id={bot_id} msgs={msg_counter}")
            time.sleep(random.uniform(10, 20))


def main():
    logger.info("🔥 REMARKETING WORKER V2.0 (standalone) INICIADO")
    redis_conn = get_redis_connection()

    while not stop_event.is_set():
        try:
            keys = redis_conn.keys("remarketing:queue:*")
            if not keys:
                time.sleep(2)
                continue

            # BLPOP múltiplas filas priorizando a primeira disponível
            str_keys = [k.decode() if isinstance(k, (bytes, bytearray)) else str(k) for k in keys]
            item = redis_conn.blpop(str_keys, timeout=5)
            if not item:
                continue

            queue_key, raw = item
            key_str = queue_key.decode() if isinstance(queue_key, (bytes, bytearray)) else queue_key
            try:
                bot_id = int(str(key_str).split(":")[-1])
            except Exception:
                logger.warning(f"⚠️ Chave inválida ignorada: {queue_key}")
                continue

            # processar o item já retirado
            try:
                job = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode('utf-8'))
            except Exception:
                logger.warning(f"⚠️ Job inválido (JSON parse falhou): bot_id={bot_id}")
                continue

            logger.debug(f"📥 Remarketing dequeue bot_id={bot_id} chat_id={job.get('telegram_user_id')}")

            job_type = job.get('type')
            if job_type == 'campaign_done':
                logger.info(f"🏁 Campaign DONE bot_id={bot_id} campaign_id={job.get('campaign_id')}")
            else:
                process_job(job)
                msg_counter = 1
                time.sleep(random.uniform(1.2, 2.5))
                if msg_counter % 100 == 0:
                    logger.info(f"⏸️ Micro pause remarketing bot_id={bot_id} msgs={msg_counter}")
                    time.sleep(random.uniform(10, 20))

        except Exception as e:
            logger.critical(f"💥 Falha geral no worker principal: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
