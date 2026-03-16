"""
Gateway ÁguiaPags - Implementação para Geração de PIX
Autor: Sistema GrimBots
Data: 2026-03-16
"""

import logging
import requests
import csv
import os
import random
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AguiaGateway:
    """
    Gateway ÁguiaPags para processamento de pagamentos PIX
    Implementa comunicação outbound com a API da ÁguiaPags
    """
    
    def __init__(self, api_key: str, sandbox: bool = True):
        """
        Inicializa o gateway ÁguiaPags
        
        Args:
            api_key: Chave de API para autenticação
            sandbox: Flag para ambiente de sandbox (default: True)
        """
        self.api_key = api_key
        self.sandbox = sandbox
        
        # URLs da API
        if sandbox:
            self.base_url = "https://sandbox-aguiapags.com/api/v1"
            logger.info("🔧 ÁguiaPags: Modo Sandbox ativado")
        else:
            self.base_url = "https://aguiapags.com/api/v1"
            logger.info("🏭 ÁguiaPags: Modo Produção ativado")
        
        # Headers padrão para requisições
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Cache para KYC (antifraude)
        self._kyc_cache = None
        self._kyc_cache_timestamp = None
        self._kyc_cache_duration = 3600  # 1 hora em segundos
        
        logger.info("✅ ÁguiaPags Gateway inicializado com sucesso")
    
    def _load_kyc_data(self) -> Optional[list]:
        """
        Carrega dados KYC do arquivo CSV com cache em memória
        
        Returns:
            Lista de dicionários com dados de clientes ou None se erro
        """
        try:
            # Verificar se cache é válido
            current_time = datetime.now().timestamp()
            if (self._kyc_cache is not None and 
                self._kyc_cache_timestamp is not None and 
                current_time - self._kyc_cache_timestamp < self._kyc_cache_duration):
                logger.debug("📋 KYC: Usando cache em memória")
                return self._kyc_cache
            
            # Carregar do arquivo
            kyc_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'cpf_nome_formatado.csv')
            
            if not os.path.exists(kyc_file):
                logger.error(f"❌ KYC: Arquivo não encontrado: {kyc_file}")
                return None
            
            kyc_data = []
            with open(kyc_file, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get('cpf') and row.get('nome'):
                        kyc_data.append({
                            'cpf': row['cpf'].strip(),
                            'nome': row['nome'].strip()
                        })
            
            # Atualizar cache
            self._kyc_cache = kyc_data
            self._kyc_cache_timestamp = current_time
            
            logger.info(f"📋 KYC: Carregados {len(kyc_data)} registros do CSV")
            return kyc_data
            
        except Exception as e:
            logger.error(f"❌ KYC: Erro ao carregar dados: {str(e)}")
            return None
    
    def _get_random_customer(self) -> Optional[Dict[str, str]]:
        """
        Sorteia um cliente válido dos dados KYC
        
        Returns:
            Dicionário com nome e cpf do cliente ou None se erro
        """
        try:
            kyc_data = self._load_kyc_data()
            
            if not kyc_data:
                logger.error("❌ KYC: Nenhum dado disponível para sorteio")
                return None
            
            # Sortear cliente aleatório
            customer = random.choice(kyc_data)
            
            # Gerar email baseado no nome
            name_parts = customer['nome'].lower().split()
            email_base = name_parts[0] + '.' + name_parts[-1] if len(name_parts) > 1 else name_parts[0]
            email = f"{email_base}@cliente.com"
            
            logger.debug(f"🎲 KYC: Cliente sorteado - {customer['nome']} ({customer['cpf']})")
            
            return {
                'name': customer['nome'],
                'document': customer['cpf'],
                'email': email
            }
            
        except Exception as e:
            logger.error(f"❌ KYC: Erro ao sortear cliente: {str(e)}")
            return None
    
    def generate_pix(self, amount: float, description: str, payment_id: str, **kwargs) -> Dict[str, Any]:
        """
        Gera um PIX através da API ÁguiaPags
        
        Args:
            amount: Valor do pagamento em reais (ex: 10.50)
            description: Descrição do pagamento
            payment_id: ID externo do pagamento (nosso payment_id)
            **kwargs: Parâmetros adicionais (ignorados neste gateway)
            
        Returns:
            Dicionário com resultado da transação:
            {
                'transaction_id': str,  # ID da transação na ÁguiaPags
                'pix_code': str,       # Código PIX para pagamento
                'status': 'pending',   # Status padrão
                'error': None or str   # Mensagem de erro se falhar
            }
        """
        try:
            logger.info(f"🚀 ÁguiaPags: Iniciando geração de PIX - Amount: {amount}, PaymentID: {payment_id}")
            
            # Obter dados do cliente via KYC
            customer = self._get_random_customer()
            if not customer:
                return {
                    'transaction_id': None,
                    'pix_code': None,
                    'status': 'error',
                    'error': 'KYC: Não foi possível obter dados do cliente'
                }
            
            # Converter valor para centavos
            amount_cents = int(amount * 100)
            logger.debug(f"💰 Valor convertido: {amount} BRL -> {amount_cents} centavos")
            
            # Montar payload conforme documentação
            payload = {
                "amount": amount_cents,
                "paymentMethod": "PIX",
                "externalRef": str(payment_id),  # INJEÇÃO CRÍTICA AQUI
                "customer": {
                    "name": customer['name'],  # Vindo do KYC
                    "email": customer['email'],  # Email baseado no nome
                    "phone": "5511999999999",
                    "document": {
                        "number": customer['document'],  # Vindo do KYC
                        "type": "cpf"
                    }
                },
                "items": [
                    {
                        "title": description or "Produto Digital Grimbots",
                        "unitPrice": amount_cents,
                        "quantity": 1
                    }
                ]
            }
            
            logger.debug(f"📦 Payload montado: {payload}")
            
            # Fazer requisição para API
            url = f"{self.base_url}/transactions"
            logger.debug(f"🌐 Enviando requisição para: {url}")
            
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30  # Timeout de 30 segundos
            )
            
            logger.info(f"📡 Resposta ÁguiaPags: Status {response.status_code}")
            
            # Validar resposta
            if response.status_code not in [200, 201]:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"❌ ÁguiaPags: Erro na resposta - {error_msg}")
                return {
                    'transaction_id': None,
                    'pix_code': None,
                    'status': 'error',
                    'error': f'Erro na API: {error_msg}'
                }
            
            # Parse da resposta
            try:
                response_data = response.json()
                logger.debug(f"📋 Resposta JSON: {response_data}")
                
                # Extrair dados conforme documentação
                pix_data = response_data.get('data', {})
                pix_code = pix_data.get('pix', {}).get('qrcode')
                transaction_id = pix_data.get('id')
                
                if not pix_code:
                    error_msg = "Código PIX não encontrado na resposta"
                    logger.error(f"❌ ÁguiaPags: {error_msg}")
                    return {
                        'transaction_id': transaction_id,
                        'pix_code': None,
                        'status': 'error',
                        'error': error_msg
                    }
                
                if not transaction_id:
                    error_msg = "ID da transação não encontrado na resposta"
                    logger.error(f"❌ ÁguiaPags: {error_msg}")
                    return {
                        'transaction_id': None,
                        'pix_code': pix_code,
                        'status': 'error',
                        'error': error_msg
                    }
                
                logger.info(f"✅ ÁguiaPags: PIX gerado com sucesso - TransactionID: {transaction_id}")
                
                return {
                    'transaction_id': transaction_id,
                    'pix_code': pix_code,
                    'status': 'pending',
                    'error': None
                }
                
            except ValueError as e:
                error_msg = f"Erro ao parsear JSON: {str(e)}"
                logger.error(f"❌ ÁguiaPags: {error_msg}")
                return {
                    'transaction_id': None,
                    'pix_code': None,
                    'status': 'error',
                    'error': error_msg
                }
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout na requisição à API ÁguiaPags"
            logger.error(f"❌ ÁguiaPags: {error_msg}")
            return {
                'transaction_id': None,
                'pix_code': None,
                'status': 'error',
                'error': error_msg
            }
            
        except requests.exceptions.ConnectionError:
            error_msg = "Erro de conexão com a API ÁguiaPags"
            logger.error(f"❌ ÁguiaPags: {error_msg}")
            return {
                'transaction_id': None,
                'pix_code': None,
                'status': 'error',
                'error': error_msg
            }
            
        except Exception as e:
            error_msg = f"Erro inesperado: {str(e)}"
            logger.error(f"❌ ÁguiaPags: {error_msg}")
            return {
                'transaction_id': None,
                'pix_code': None,
                'status': 'error',
                'error': error_msg
            }
    
    def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Consulta status de uma transação (método placeholder para implementação futura)
        
        Args:
            transaction_id: ID da transação na ÁguiaPags
            
        Returns:
            Dicionário com status da transação
        """
        # TODO: Implementar consulta de status quando necessário
        logger.warning(f"⚠️ ÁguiaPags: get_transaction_status não implementado ainda - TransactionID: {transaction_id}")
        return {
            'transaction_id': transaction_id,
            'status': 'unknown',
            'error': 'Método não implementado'
        }
    
    def cancel_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Cancela uma transação (método placeholder para implementação futura)
        
        Args:
            transaction_id: ID da transação na ÁguiaPags
            
        Returns:
            Dicionário com resultado do cancelamento
        """
        # TODO: Implementar cancelamento quando necessário
        logger.warning(f"⚠️ ÁguiaPags: cancel_transaction não implementado ainda - TransactionID: {transaction_id}")
        return {
            'transaction_id': transaction_id,
            'status': 'error',
            'error': 'Método não implementado'
        }


# Função de factory para criação do gateway
def create_aguia_gateway(api_key: str, sandbox: bool = True) -> AguiaGateway:
    """
    Factory para criar instância do gateway ÁguiaPags
    
    Args:
        api_key: Chave de API da ÁguiaPags
        sandbox: Flag para ambiente sandbox
        
    Returns:
        Instância do AguiaGateway
    """
    return AguiaGateway(api_key=api_key, sandbox=sandbox)


# Teste básico quando executado diretamente
if __name__ == "__main__":
    # Configurar logging para teste
    logging.basicConfig(level=logging.INFO)
    
    # Teste de criação do gateway
    try:
        gateway = create_aguia_gateway("test_api_key", sandbox=True)
        logger.info("✅ Gateway ÁguiaPags criado com sucesso")
        
        # Teste de geração de PIX (vai falhar sem API key real, mas testa a estrutura)
        result = gateway.generate_pix(10.50, "Teste Integration", "test_payment_123")
        logger.info(f"🧪 Teste result: {result}")
        
    except Exception as e:
        logger.error(f"❌ Erro no teste: {str(e)}")
