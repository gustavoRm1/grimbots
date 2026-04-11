"""
Bot Messenger Service
=====================
Serviço dedicado para comunicação com a API do Telegram.
Isola toda a lógica de envio de mensagens, mídia e rate limiting.
"""

import logging
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any, Optional, List
import json

logger = logging.getLogger(__name__)


class BotMessenger:
    """
    Serviço de mensageria do Telegram.
    Encapsula envio de mensagens, mídia e gestão de rate limits.
    """
    
    def __init__(self, max_concurrent: int = 10):
        """
        Inicializa o messenger com configurações de concorrência.
        
        Args:
            max_concurrent: Número máximo de requisições simultâneas
        """
        self.telegram_http_semaphore = threading.BoundedSemaphore(max_concurrent)
        
        # ✅ Session reutilizável + Retry/Backoff para envios pesados
        self._telegram_session = requests.Session()
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(['GET', 'POST']),
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=50,
            pool_maxsize=50,
        )
        self._telegram_session.mount('https://', adapter)
        self._telegram_session.mount('http://', adapter)
        
        logger.info(f"✅ BotMessenger inicializado (max_concurrent={max_concurrent})")
    
    def build_keyboard(
        self,
        buttons: List[Dict[str, Any]],
        resize_keyboard: bool = True,
        one_time_keyboard: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Constrói um reply markup para botões inline ou teclado.
        
        Args:
            buttons: Lista de botões (dicts com 'text', 'callback_data' ou 'url')
            resize_keyboard: Se True, ajusta o tamanho do teclado
            one_time_keyboard: Se True, teclado desaparece após uso
            
        Returns:
            Dict com estrutura do reply_markup ou None
        """
        if not buttons:
            return None
        
        # Verificar se é inline keyboard (tem callback_data ou url)
        is_inline = any('callback_data' in btn or 'url' in btn for btn in buttons)
        
        if is_inline:
            inline_keyboard = []
            row = []
            
            for btn in buttons:
                if 'url' in btn:
                    row.append({'text': btn['text'], 'url': btn['url']})
                elif 'callback_data' in btn:
                    row.append({'text': btn['text'], 'callback_data': btn['callback_data']})
                
                # Máximo 3 botões por linha para inline
                if len(row) == 3:
                    inline_keyboard.append(row)
                    row = []
            
            if row:
                inline_keyboard.append(row)
            
            return {'inline_keyboard': inline_keyboard}
        else:
            # Reply keyboard tradicional
            keyboard = []
            row = []
            
            for btn in buttons:
                row.append({'text': btn['text']})
                # Máximo 2 botões por linha para reply keyboard
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            
            if row:
                keyboard.append(row)
            
            return {
                'keyboard': keyboard,
                'resize_keyboard': resize_keyboard,
                'one_time_keyboard': one_time_keyboard
            }
    
    def send_message(
        self,
        token: str,
        chat_id: str,
        message: str,
        reply_markup: Optional[Dict] = None,
        parse_mode: str = 'HTML',
        disable_notification: bool = False
    ) -> bool:
        """
        Envia mensagem de texto para o Telegram.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message: Texto da mensagem
            reply_markup: Markup de botões opcional
            parse_mode: Modo de parsing (HTML, Markdown, etc)
            disable_notification: Se True, envia silenciosamente
            
        Returns:
            bool: True se enviado com sucesso
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_notification': disable_notification
        }
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            with self.telegram_http_semaphore:
                response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.debug(f"✅ Mensagem enviada para chat {chat_id}")
                    return True
            
            logger.warning(f"⚠️ Erro ao enviar mensagem: {response.status_code} - {response.text[:200]}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            return False
    
    def send_photo(
        self,
        token: str,
        chat_id: str,
        photo_url: str,
        caption: str = '',
        reply_markup: Optional[Dict] = None,
        parse_mode: str = 'HTML'
    ) -> bool:
        """
        Envia foto via URL.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            photo_url: URL da imagem
            caption: Legenda opcional
            reply_markup: Markup de botões opcional
            parse_mode: Modo de parsing da legenda
            
        Returns:
            bool: True se enviado com sucesso
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/sendPhoto"
        
        payload = {
            'chat_id': chat_id,
            'photo': photo_url,
            'parse_mode': parse_mode
        }
        
        if caption:
            payload['caption'] = caption
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            with self.telegram_http_semaphore:
                response = requests.post(url, json=payload, timeout=10)
            
            return response.status_code == 200 and response.json().get('ok', False)
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar foto: {e}")
            return False
    
    def send_video(
        self,
        token: str,
        chat_id: str,
        video_url: str,
        caption: str = '',
        reply_markup: Optional[Dict] = None,
        parse_mode: str = 'HTML',
        timeout: int = 30
    ) -> Optional[requests.Response]:
        """
        Envia vídeo via URL com retry e backoff.
        Usa session dedicada para uploads grandes.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            video_url: URL do vídeo
            caption: Legenda opcional
            reply_markup: Markup de botões opcional
            parse_mode: Modo de parsing
            timeout: Timeout em segundos
            
        Returns:
            Response object ou None em caso de erro
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/sendVideo"
        
        payload = {
            'chat_id': chat_id,
            'video': video_url,
            'parse_mode': parse_mode
        }
        
        if caption:
            # Telegram limita caption em 1024 chars
            if len(caption) > 1024:
                caption = caption[:1021] + '...'
            payload['caption'] = caption
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            with self.telegram_http_semaphore:
                response = self._telegram_session.post(url, json=payload, timeout=timeout)
            
            # Validar HTTP 5xx sem quebrar fluxo
            if response is not None and response.status_code >= 500:
                try:
                    response.raise_for_status()
                except Exception as e:
                    logger.warning(f"⚠️ HTTP {response.status_code} ao enviar vídeo, mas continuando: {e}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar vídeo: {e}")
            return None
    
    def send_audio(
        self,
        token: str,
        chat_id: str,
        audio_url: str,
        caption: str = '',
        reply_markup: Optional[Dict] = None,
        parse_mode: str = 'HTML'
    ) -> bool:
        """
        Envia áudio via URL.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            audio_url: URL do áudio
            caption: Legenda opcional
            reply_markup: Markup de botões opcional
            parse_mode: Modo de parsing
            
        Returns:
            bool: True se enviado com sucesso
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/sendAudio"
        
        payload = {
            'chat_id': chat_id,
            'audio': audio_url,
            'parse_mode': parse_mode
        }
        
        if caption:
            payload['caption'] = caption
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            with self.telegram_http_semaphore:
                response = requests.post(url, json=payload, timeout=10)
            
            return response.status_code == 200 and response.json().get('ok', False)
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar áudio: {e}")
            return False
    
    def send_document(
        self,
        token: str,
        chat_id: str,
        document_url: str,
        caption: str = '',
        reply_markup: Optional[Dict] = None,
        parse_mode: str = 'HTML'
    ) -> bool:
        """
        Envia documento via URL.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            document_url: URL do documento
            caption: Legenda opcional
            reply_markup: Markup de botões opcional
            parse_mode: Modo de parsing
            
        Returns:
            bool: True se enviado com sucesso
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/sendDocument"
        
        payload = {
            'chat_id': chat_id,
            'document': document_url,
            'parse_mode': parse_mode
        }
        
        if caption:
            payload['caption'] = caption
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            with self.telegram_http_semaphore:
                response = requests.post(url, json=payload, timeout=10)
            
            return response.status_code == 200 and response.json().get('ok', False)
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar documento: {e}")
            return False
    
    def send_message_with_media(
        self,
        token: str,
        chat_id: str,
        message: str,
        media_type: Optional[str] = None,
        media_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        reply_markup: Optional[Dict] = None
    ) -> bool:
        """
        Envia mensagem com mídia opcional (foto, vídeo, áudio).
        Se a mensagem for muito longa para a legenda, envia em duas partes.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message: Texto da mensagem
            media_type: Tipo de mídia ('photo', 'video', 'audio') ou None
            media_url: URL da mídia
            reply_markup: Markup de botões opcional
            
        Returns:
            bool: True se enviado com sucesso
        """
        if not media_type or not media_url:
            # Sem mídia, enviar só texto
            return self.send_message(token, chat_id, message, reply_markup)
        
        base_url = f"https://api.telegram.org/bot{token}"
        
        # Preparar caption (limitado pelo Telegram)
        caption_text = message[:1024] if len(message) > 1024 else message
        
        if media_type == 'photo':
            if len(message) > 1500:
                # Muito longo para caption, enviar separado
                result = self.send_photo(token, chat_id, media_url, '', reply_markup)
                if result:
                    # Enviar texto em mensagem separada
                    return self.send_message(token, chat_id, message)
                return result
            else:
                return self.send_photo(token, chat_id, media_url, caption_text, reply_markup)
        
        elif media_type == 'video':
            if len(message) > 1500:
                # Enviar vídeo sem caption primeiro
                response = self.send_video(token, chat_id, media_url, '', reply_markup)
                if response and response.status_code == 200:
                    # Enviar texto em mensagem separada
                    return self.send_message(token, chat_id, message)
                return response is not None and response.status_code == 200
            else:
                response = self.send_video(token, chat_id, media_url, caption_text, reply_markup)
                return response is not None and response.status_code == 200
        
        elif media_type == 'audio':
            if len(message) > 1500:
                # Enviar áudio sem caption primeiro
                result = self.send_audio(token, chat_id, media_url, '', reply_markup)
                if result:
                    return self.send_message(token, chat_id, message)
                return result
            else:
                return self.send_audio(token, chat_id, media_url, caption_text, reply_markup)
        
        else:
            logger.warning(f"⚠️ media_type desconhecido: {media_type!r} (enviando só texto)")
            return self.send_message(token, chat_id, message, reply_markup)
    
    def answer_callback_query(
        self,
        token: str,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> bool:
        """
        Responde a uma callback query (botão inline pressionado).
        
        Args:
            token: Token do bot
            callback_query_id: ID da callback query
            text: Texto opcional para mostrar
            show_alert: Se True, mostra como alerta
            
        Returns:
            bool: True se respondido com sucesso
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/answerCallbackQuery"
        
        payload = {
            'callback_query_id': callback_query_id,
            'show_alert': show_alert
        }
        
        if text:
            payload['text'] = text
        
        try:
            with self.telegram_http_semaphore:
                response = requests.post(url, json=payload, timeout=5)
            
            return response.status_code == 200 and response.json().get('ok', False)
            
        except Exception as e:
            logger.error(f"❌ Erro ao responder callback: {e}")
            return False
    
    def edit_message_text(
        self,
        token: str,
        chat_id: str,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict] = None,
        parse_mode: str = 'HTML'
    ) -> bool:
        """
        Edita o texto de uma mensagem existente.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message_id: ID da mensagem a editar
            text: Novo texto
            reply_markup: Novo markup opcional
            parse_mode: Modo de parsing
            
        Returns:
            bool: True se editado com sucesso
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/editMessageText"
        
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            with self.telegram_http_semaphore:
                response = requests.post(url, json=payload, timeout=10)
            
            return response.status_code == 200 and response.json().get('ok', False)
            
        except Exception as e:
            logger.error(f"❌ Erro ao editar mensagem: {e}")
            return False
    
    def delete_message(
        self,
        token: str,
        chat_id: str,
        message_id: int
    ) -> bool:
        """
        Deleta uma mensagem.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message_id: ID da mensagem a deletar
            
        Returns:
            bool: True se deletado com sucesso
        """
        base_url = f"https://api.telegram.org/bot{token}"
        url = f"{base_url}/deleteMessage"
        
        payload = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        
        try:
            with self.telegram_http_semaphore:
                response = requests.post(url, json=payload, timeout=5)
            
            return response.status_code == 200 and response.json().get('ok', False)
            
        except Exception as e:
            logger.error(f"❌ Erro ao deletar mensagem: {e}")
            return False
