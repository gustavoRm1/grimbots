"""
Gateway Factory - Padrão Factory para criação de gateways
Gerencia criação e registro de gateways de pagamento
"""

import logging
from typing import Dict, Any, Optional, Type, List
from gateway_interface import PaymentGateway
from gateway_syncpay import SyncPayGateway
from gateway_pushyn import PushynGateway
from gateway_paradise import ParadisePaymentGateway
from gateway_wiinpay import WiinPayGateway

logger = logging.getLogger(__name__)


class GatewayFactory:
    """
    Factory para criar instâncias de gateways de pagamento
    
    Implementa Pattern Factory + Registry
    Permite adicionar novos gateways dinamicamente
    """
    
    # Registry de gateways disponíveis
    _gateway_classes: Dict[str, Type[PaymentGateway]] = {
        'syncpay': SyncPayGateway,
        'pushynpay': PushynGateway,
        'paradise': ParadisePaymentGateway,
        'wiinpay': WiinPayGateway,
    }
    
    @classmethod
    def create_gateway(
        cls, 
        gateway_type: str, 
        credentials: Dict[str, Any]
    ) -> Optional[PaymentGateway]:
        """
        Cria uma instância do gateway apropriado
        
        Args:
            gateway_type: Tipo do gateway ('syncpay', 'pushynpay', etc)
            credentials: Credenciais específicas do gateway
        
        Returns:
            Instância do gateway configurada ou None se inválido
        
        Examples:
            # SyncPay
            gateway = GatewayFactory.create_gateway('syncpay', {
                'client_id': 'xxx',
                'client_secret': 'yyy'
            })
            
            # Pushyn
            gateway = GatewayFactory.create_gateway('pushynpay', {
                'api_key': 'zzz'
            })
        """
        # Validar tipo de gateway
        if not gateway_type:
            logger.error("❌ [Factory] Tipo de gateway não informado")
            return None
        
        # Normalizar nome do gateway
        gateway_type = gateway_type.lower().strip()
        
        # Buscar classe do gateway
        gateway_class = cls._gateway_classes.get(gateway_type)
        
        if not gateway_class:
            logger.error(f"❌ [Factory] Gateway desconhecido: {gateway_type}")
            logger.error(f"Gateways disponíveis: {', '.join(cls._gateway_classes.keys())}")
            return None
        
        # Validar credenciais
        if not credentials or not isinstance(credentials, dict):
            logger.error(f"❌ [Factory] Credenciais inválidas para {gateway_type}")
            return None
        
        try:
            # Criar instância com credenciais específicas
            if gateway_type == 'syncpay':
                # SyncPay requer: client_id e client_secret
                client_id = credentials.get('client_id')
                client_secret = credentials.get('client_secret')
                
                if not client_id or not client_secret:
                    logger.error(f"❌ [Factory] SyncPay requer client_id e client_secret")
                    return None
                
                gateway = gateway_class(
                    client_id=client_id,
                    client_secret=client_secret
                )
                
            elif gateway_type == 'pushynpay':
                # Pushyn requer: api_key
                api_key = credentials.get('api_key')
                
                if not api_key:
                    logger.error(f"❌ [Factory] Pushyn requer api_key")
                    return None
                
                gateway = gateway_class(
                    api_key=api_key
                )
            
            elif gateway_type == 'paradise':
                # Paradise requer: api_key, product_hash, offer_hash
                api_key = credentials.get('api_key')
                product_hash = credentials.get('product_hash')
                offer_hash = credentials.get('offer_hash')
                store_id = credentials.get('store_id', '')
                split_percentage = credentials.get('split_percentage', 2.0)  # 2% PADRÃO
                
                if not api_key or not product_hash or not offer_hash:
                    logger.error(f"❌ [Factory] Paradise requer api_key, product_hash e offer_hash")
                    return None
                
                gateway = gateway_class(credentials={
                    'api_key': api_key,
                    'product_hash': product_hash,
                    'offer_hash': offer_hash,
                    'store_id': store_id,
                    'split_percentage': split_percentage
                })
            
            elif gateway_type == 'wiinpay':
                # ✅ WiinPay requer: api_key
                api_key = credentials.get('api_key')
                split_user_id = credentials.get('split_user_id', '')
                
                if not api_key:
                    logger.error(f"❌ [Factory] WiinPay requer api_key")
                    return None
                
                gateway = gateway_class(
                    api_key=api_key,
                    split_user_id=split_user_id
                )
            
            else:
                # Gateway registrado mas sem construtor definido
                logger.error(f"❌ [Factory] Construtor não implementado para: {gateway_type}")
                return None
            
            logger.info(f"✅ [Factory] Gateway {gateway.get_gateway_name()} criado com sucesso")
            return gateway
            
        except TypeError as e:
            logger.error(f"❌ [Factory] Erro ao instanciar {gateway_type}: Parâmetros incorretos - {e}")
            return None
        except Exception as e:
            logger.error(f"❌ [Factory] Erro ao criar gateway {gateway_type}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @classmethod
    def get_available_gateways(cls) -> List[str]:
        """
        Retorna lista de gateways disponíveis
        
        Returns:
            Lista com tipos de gateways registrados
        
        Example:
            >>> GatewayFactory.get_available_gateways()
            ['syncpay', 'pushynpay']
        """
        return list(cls._gateway_classes.keys())
    
    @classmethod
    def register_gateway(
        cls, 
        gateway_type: str, 
        gateway_class: Type[PaymentGateway]
    ) -> bool:
        """
        Registra um novo gateway dinamicamente
        
        Args:
            gateway_type: Tipo/identificador do gateway
            gateway_class: Classe que implementa PaymentGateway
        
        Returns:
            True se registrado com sucesso, False caso contrário
        
        Example:
            >>> class MyGateway(PaymentGateway):
            ...     pass
            >>> GatewayFactory.register_gateway('mygateway', MyGateway)
            True
        """
        try:
            # Validar tipo
            if not gateway_type or not isinstance(gateway_type, str):
                logger.error(f"❌ [Factory] Tipo de gateway inválido: {gateway_type}")
                return False
            
            # Validar classe
            if not gateway_class or not issubclass(gateway_class, PaymentGateway):
                logger.error(f"❌ [Factory] Classe deve herdar de PaymentGateway")
                return False
            
            # Normalizar nome
            gateway_type = gateway_type.lower().strip()
            
            # Verificar se já existe
            if gateway_type in cls._gateway_classes:
                logger.warning(f"⚠️ [Factory] Gateway {gateway_type} já registrado. Sobrescrevendo...")
            
            # Registrar
            cls._gateway_classes[gateway_type] = gateway_class
            logger.info(f"✅ [Factory] Gateway {gateway_type} registrado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ [Factory] Erro ao registrar gateway: {e}")
            return False
    
    @classmethod
    def unregister_gateway(cls, gateway_type: str) -> bool:
        """
        Remove um gateway do registro
        
        Args:
            gateway_type: Tipo do gateway a remover
        
        Returns:
            True se removido, False se não existia
        """
        gateway_type = gateway_type.lower().strip()
        
        if gateway_type in cls._gateway_classes:
            del cls._gateway_classes[gateway_type]
            logger.info(f"✅ [Factory] Gateway {gateway_type} removido do registro")
            return True
        else:
            logger.warning(f"⚠️ [Factory] Gateway {gateway_type} não encontrado no registro")
            return False
    
    @classmethod
    def is_gateway_available(cls, gateway_type: str) -> bool:
        """
        Verifica se um gateway está disponível
        
        Args:
            gateway_type: Tipo do gateway
        
        Returns:
            True se disponível, False caso contrário
        """
        return gateway_type.lower().strip() in cls._gateway_classes
    
    @classmethod
    def get_gateway_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Retorna informações sobre todos os gateways registrados
        
        Returns:
            Dicionário com informações dos gateways
        """
        info = {}
        
        for gateway_type, gateway_class in cls._gateway_classes.items():
            try:
                # Tentar obter informações básicas da classe
                info[gateway_type] = {
                    'class_name': gateway_class.__name__,
                    'module': gateway_class.__module__,
                    'docstring': gateway_class.__doc__.strip() if gateway_class.__doc__ else None
                }
            except Exception as e:
                logger.warning(f"⚠️ [Factory] Erro ao obter info de {gateway_type}: {e}")
                info[gateway_type] = {
                    'class_name': gateway_class.__name__,
                    'error': str(e)
                }
        
        return info

