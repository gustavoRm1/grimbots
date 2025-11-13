# Guia Rápido - Implementação de Novos Gateways

## 🚀 Quick Start

### 1. Criar Arquivo do Gateway

```python
# gateway_novogateway.py
from gateway_interface import PaymentGateway
from typing import Dict, Any, Optional
import requests
import logging

logger = logging.getLogger(__name__)

class NovoGateway(PaymentGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.novogateway.com.br"
    
    def get_gateway_name(self) -> str:
        return "NovoGateway"
    
    def get_gateway_type(self) -> str:
        return "novogateway"
    
    def get_webhook_url(self) -> str:
        from os import environ
        base_url = environ.get('WEBHOOK_URL', 'http://localhost:5000')
        return f"{base_url}/webhook/payment/novogateway"
    
    def generate_pix(self, amount: float, description: str, payment_id: str, 
                     customer_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        # Implementar criação de PIX
        pass
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Implementar processamento de webhook
        pass
    
    def verify_credentials(self) -> bool:
        # Implementar verificação de credenciais
        pass
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        # Implementar consulta de status
        pass
```

### 2. Registrar no GatewayFactory

```python
# gateway_factory.py
from gateway_novogateway import NovoGateway

_gateway_classes: Dict[str, Type[PaymentGateway]] = {
    # ... gateways existentes ...
    'novogateway': NovoGateway,  # ✅ ADICIONAR AQUI
}

# No método create_gateway():
elif gateway_type == 'novogateway':
    api_key = credentials.get('api_key')
    if not api_key:
        logger.error(f"❌ [Factory] NovoGateway requer api_key")
        return None
    gateway = gateway_class(api_key=api_key)
```

### 3. Adicionar ao Middleware

```python
# middleware/gateway_validator.py
valid_types = ['syncpay', 'pushynpay', 'paradise', 'wiinpay', 'atomopay', 'novogateway']
```

### 4. Testar

```python
# Teste básico
from gateway_factory import GatewayFactory

credentials = {'api_key': 'sua_api_key'}
gateway = GatewayFactory.create_gateway('novogateway', credentials)

# Testar generate_pix
result = gateway.generate_pix(
    amount=10.50,
    description='Produto de teste',
    payment_id='TEST_123'
)

# Testar verify_credentials
is_valid = gateway.verify_credentials()
```

---

## 📋 Checklist Mínimo

- [ ] Criar arquivo `gateway_novogateway.py`
- [ ] Implementar `PaymentGateway` interface
- [ ] Implementar `generate_pix()` com retorno padronizado
- [ ] Implementar `process_webhook()` com retorno padronizado
- [ ] Implementar `verify_credentials()`
- [ ] Implementar `get_payment_status()`
- [ ] Registrar no `GatewayFactory`
- [ ] Adicionar ao middleware
- [ ] Testar criação de pagamento
- [ ] Testar processamento de webhook

---

## 🔑 Campos Obrigatórios

### `generate_pix()` DEVE retornar:
- ✅ `pix_code`: Código PIX copia e cola
- ✅ `qr_code_url`: URL da imagem QR Code ou base64
- ✅ `transaction_id`: ID da transação no gateway
- ✅ `payment_id`: ID do pagamento no sistema

### `process_webhook()` DEVE retornar:
- ✅ `gateway_transaction_id`: ID da transação no gateway
- ✅ `status`: Status do pagamento ('pending', 'paid', 'failed')
- ✅ `amount`: Valor em reais

---

## 🎯 Padrões de Retorno

### `generate_pix()` - Formato Padrão:
```python
{
    'pix_code': str,              # OBRIGATÓRIO
    'qr_code_url': str,           # OBRIGATÓRIO
    'transaction_id': str,        # OBRIGATÓRIO
    'payment_id': str,            # OBRIGATÓRIO
    'gateway_hash': str,          # RECOMENDADO (para webhook matching)
    'reference': str,             # RECOMENDADO (para webhook matching)
    'qr_code_base64': str,        # OPCIONAL
    'expires_at': datetime        # OPCIONAL
}
```

### `process_webhook()` - Formato Padrão:
```python
{
    'gateway_transaction_id': str,  # OBRIGATÓRIO
    'status': str,                  # OBRIGATÓRIO ('pending', 'paid', 'failed')
    'amount': float,                # OBRIGATÓRIO
    'gateway_hash': str,            # RECOMENDADO (para webhook matching)
    'external_reference': str,      # RECOMENDADO (para webhook matching)
    'payer_name': str,              # OPCIONAL
    'payer_document': str,          # OPCIONAL
    'end_to_end_id': str            # OPCIONAL
}
```

---

## 🔍 Mapeamento de Status

### Status do Gateway → Status Interno:
```python
# PAGO
'paid' → 'paid'
'approved' → 'paid'
'confirmed' → 'paid'
'completed' → 'paid'
'success' → 'paid'

# PENDENTE
'pending' → 'pending'
'waiting' → 'pending'
'processing' → 'pending'

# FALHADO
'failed' → 'failed'
'cancelled' → 'failed'
'canceled' → 'failed'
'expired' → 'failed'
'rejected' → 'failed'
```

---

## 💡 Dicas Importantes

### 1. Validação de Valores
- Sempre validar `amount > 0`
- Converter valores se necessário (reais ↔ centavos)
- Verificar limites (valor mínimo/máximo)

### 2. Tratamento de Erros
- Sempre tratar erros e retornar `None` em caso de falha
- Logar erros com contexto suficiente
- Não lançar exceções não tratadas

### 3. Normalização de Dados
- Sempre normalizar status para formato interno
- Sempre normalizar valores para reais (float)
- Sempre converter IDs para string

### 4. Logging
- Usar `logger.info()` para operações normais
- Usar `logger.error()` para erros
- Usar `logger.debug()` para informações detalhadas
- Incluir contexto suficiente nos logs

### 5. Webhook Matching
- Sempre retornar `gateway_transaction_id` no webhook
- Sempre retornar `gateway_hash` se disponível
- Sempre retornar `external_reference` se disponível
- Usar múltiplas chaves para matching (fallback)

---

## 🔧 Configuração no Banco de Dados

### Modelo `Gateway`:
```python
class Gateway(db.Model):
    gateway_type = db.Column(db.String(30), nullable=False)  # 'novogateway'
    _api_key = db.Column('api_key', db.String(1000))  # Criptografado
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    # ... outros campos ...
```

### Propriedades com Criptografia:
```python
@property
def api_key(self):
    """Descriptografa api_key ao acessar"""
    if not self._api_key:
        return None
    from utils.encryption import decrypt
    return decrypt(self._api_key)

@api_key.setter
def api_key(self, value):
    """Criptografa api_key ao armazenar"""
    if not value:
        self._api_key = None
    else:
        from utils.encryption import encrypt
        self._api_key = encrypt(value)
```

---

## 📝 Exemplo Completo Mínimo

```python
"""
Gateway NovoGateway - Implementação Mínima
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)

class NovoGateway(PaymentGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.novogateway.com.br"
    
    def get_gateway_name(self) -> str:
        return "NovoGateway"
    
    def get_gateway_type(self) -> str:
        return "novogateway"
    
    def get_webhook_url(self) -> str:
        base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
        return f"{base_url}/webhook/payment/novogateway"
    
    def generate_pix(self, amount: float, description: str, payment_id: str,
                     customer_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            # Validar valor
            if amount <= 0:
                logger.error(f"❌ Valor inválido: {amount}")
                return None
            
            # Preparar payload
            payload = {
                'amount': amount,
                'description': description,
                'payment_id': payment_id,
                'webhook_url': self.get_webhook_url()
            }
            
            # Fazer requisição
            url = f"{self.base_url}/api/v1/pix/create"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'pix_code': data.get('pix_code'),
                    'qr_code_url': data.get('qr_code_url'),
                    'transaction_id': str(data.get('transaction_id')),
                    'payment_id': payment_id
                }
            else:
                logger.error(f"❌ Erro: Status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao gerar PIX: {e}")
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            transaction_id = data.get('transaction_id') or data.get('id')
            status_raw = data.get('status', '').lower()
            amount = float(data.get('amount') or 0)
            
            if not transaction_id:
                logger.error(f"❌ Webhook sem transaction_id")
                return None
            
            # Mapear status
            status_map = {
                'paid': 'paid',
                'approved': 'paid',
                'pending': 'pending',
                'failed': 'failed',
                'cancelled': 'failed'
            }
            status = status_map.get(status_raw, 'pending')
            
            return {
                'gateway_transaction_id': str(transaction_id),
                'status': status,
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar webhook: {e}")
            return None
    
    def verify_credentials(self) -> bool:
        try:
            if not self.api_key or len(self.api_key) < 10:
                return False
            
            # Testar credenciais (exemplo)
            url = f"{self.base_url}/api/v1/auth/verify"
            headers = {'Authorization': f'Bearer {self.api_key}'}
            response = requests.get(url, headers=headers, timeout=10)
            
            return response.status_code == 200
        except:
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/api/v1/pix/{transaction_id}"
            headers = {'Authorization': f'Bearer {self.api_key}'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return self.process_webhook(response.json())
            return None
        except:
            return None
```

---

## 🎓 Próximos Passos

1. **Revisar Documentação da API**: Entender endpoints, autenticação, formatos de dados
2. **Implementar Gateway**: Seguir este guia e o documento completo
3. **Testar**: Testar criação de pagamento e processamento de webhook
4. **Documentar**: Documentar características específicas do gateway
5. **Deploy**: Deploy e monitoramento

---

**Última atualização**: 2024-11-12
**Versão**: 1.0

