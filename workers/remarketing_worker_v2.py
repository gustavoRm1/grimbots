import os
import sys
import time
import signal
import threading
import logging

# Garantir que o diretório raiz do projeto esteja no sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from redis_manager import get_redis_connection
from bot_manager import BotManager


# Garantir diretório de logs
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

stop_event = threading.Event()
bot_manager = BotManager()


def shutdown(sig, frame):
    logger.warning("🛑 Shutdown recebido, encerrando worker...")
    stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


def drain_queue(bot_id: int):
    """Processa uma fila por vez, isolando falhas por bot."""
    try:
        logger.info(f"🚀 Iniciando drain da fila remarketing:queue:{bot_id}")
        bot_manager._remarketing_worker_loop(
            bot_id=bot_id,
            stop_event=stop_event
        )
    except Exception as e:
        logger.error(f"❌ Worker falhou para bot_id={bot_id}: {e}", exc_info=True)


def main():
    logger.info("🔥 REMARKETING WORKER V2.0 INICIADO")

    redis_conn = get_redis_connection()

    while not stop_event.is_set():
        try:
            keys = redis_conn.keys("remarketing:queue:*")

            if not keys:
                time.sleep(2)
                continue

            for raw_key in keys:
                try:
                    key = raw_key.decode() if isinstance(raw_key, (bytes, bytearray)) else raw_key
                    bot_id = int(str(key).split(":")[-1])
                    drain_queue(bot_id)
                except ValueError:
                    logger.warning(f"⚠️ Chave inválida ignorada: {raw_key}")
                except Exception as e:
                    logger.error(f"❌ Erro ao processar chave {raw_key}: {e}", exc_info=True)

            time.sleep(1)

        except Exception as e:
            logger.critical(f"💥 Falha geral no worker principal: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
