"""
MODIFICAÇÕES NO utils/tracking_service.py - ARQUITETO SÊNIOR QI 200

ADICIONAR:
1. generate_tracking_token() - Gera tracking token único
2. save_tracking_token() - Salva tracking data com tracking_token como chave
3. recover_by_tracking_token() - Recupera tracking data por tracking_token
"""

# ============================================================================
# ADICIONAR ESTAS FUNÇÕES NO tracking_service.py
# ============================================================================

"""
import uuid

class TrackingService:
    # ... métodos existentes ...
    
    @staticmethod
    def generate_tracking_token() -> str:
        \"\"\"
        Gera tracking token único (UUID)
        
        Este token é o identificador unificado para tracking
        entre PageView, ViewContent e Purchase
        
        Returns:
            UUID string (ex: "550e8400-e29b-41d4-a716-446655440000")
        \"\"\"
        return str(uuid.uuid4())
    
    @staticmethod
    def save_tracking_token(
        tracking_token: str,
        tracking_data: Dict[str, Any]
    ) -> bool:
        \"\"\"
        Salva tracking data com tracking_token como chave principal
        
        Args:
            tracking_token: Token único gerado
            tracking_data: Dict com dados de tracking
        
        Returns:
            True se salvo com sucesso, False caso contrário
        \"\"\"
        if not r:
            logger.warning("⚠️ Redis não disponível - tracking_token não salvo")
            return False
        
        if not tracking_token:
            logger.error("❌ tracking_token vazio")
            return False
        
        try:
            key = f"tracking_token:{tracking_token}"
            ttl_seconds = TrackingService.TTL_DAYS * 24 * 3600
            r.setex(key, ttl_seconds, json.dumps(tracking_data))
            logger.debug(f"🔑 Tracking token salvo: {key}")
            
            # ✅ TAMBÉM salvar nas chaves antigas (compatibilidade)
            # Isso garante que recuperação por fbclid/telegram_user_id ainda funciona
            fbclid = tracking_data.get('fbclid')
            telegram_user_id = tracking_data.get('telegram_user_id')
            grim = tracking_data.get('grim')
            
            if fbclid:
                key_fbclid = f"tracking:fbclid:{fbclid}"
                r.setex(key_fbclid, ttl_seconds, json.dumps(tracking_data))
            
            if telegram_user_id:
                key_chat = f"tracking:chat:{telegram_user_id}"
                r.setex(key_chat, ttl_seconds, json.dumps(tracking_data))
            
            if grim:
                key_grim = f"tracking_grim:{grim}"
                r.setex(key_grim, ttl_seconds, json.dumps(tracking_data))
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro salvando tracking_token: {e}")
            return False
    
    @staticmethod
    def recover_by_tracking_token(
        tracking_token: str
    ) -> Optional[Dict[str, Any]]:
        \"\"\"
        Recupera tracking data por tracking_token (PRIORIDADE MÁXIMA)
        
        Args:
            tracking_token: Token único gerado
        
        Returns:
            Dict com dados de tracking ou None se não encontrado
        \"\"\"
        if not r:
            logger.warning("⚠️ Redis não disponível - tracking_token não recuperado")
            return None
        
        if not tracking_token:
            logger.warning("⚠️ tracking_token vazio")
            return None
        
        try:
            key = f"tracking_token:{tracking_token}"
            data = r.get(key)
            
            if data:
                tracking_data = json.loads(data)
                logger.info(f"✅ Tracking recuperado via tracking_token: {tracking_token}")
                return tracking_data
            else:
                logger.warning(f"⚠️ Tracking token não encontrado: {tracking_token}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro recuperando tracking_token: {e}")
            return None
    
    @staticmethod
    def build_external_id_array(
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None
    ) -> List[str]:
        \"\"\"
        Constrói array de external_id IMUTÁVEL e CONSISTENTE
        
        ✅ ORDEM FIXA (nunca alterar):
        1. hash(fbclid) - sempre primeiro (se disponível)
        2. hash(telegram_user_id) - sempre segundo (se disponível)
        
        Args:
            fbclid: Facebook Click ID
            telegram_user_id: ID do usuário no Telegram
        
        Returns:
            List[str] - Array ordenado de external_id hashes
        \"\"\"
        external_ids = []
        
        # ✅ PRIORIDADE 1: fbclid primeiro (matching Meta Pixel)
        if fbclid:
            fbclid_hash = TrackingService.hash_fbclid(fbclid)
            if fbclid_hash and fbclid_hash not in external_ids:
                external_ids.append(fbclid_hash)
        
        # ✅ PRIORIDADE 2: telegram_user_id segundo
        if telegram_user_id:
            telegram_hash = TrackingService.hash_telegram_id(telegram_user_id)
            if telegram_hash and telegram_hash not in external_ids:
                external_ids.append(telegram_hash)
        
        return external_ids
"""

