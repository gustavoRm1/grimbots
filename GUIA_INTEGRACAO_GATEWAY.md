# 📘 Guia Completo: Integração de Novos Gateways de Pagamento

## 📋 **Índice**

1. [Arquitetura Atual](#arquitetura-atual)
2. [Componentes do Sistema](#componentes-do-sistema)
3. [Passo a Passo para Integrar Novo Gateway](#passo-a-passo)
4. [Exemplo Prático: Integração de Novo Gateway](#exemplo-prático)
5. [Checklist de Integração](#checklist)

---

## 🏗️ **Arquitetura Atual**

### **Padrões de Design Implementados**

1. **Strategy Pattern** (`gateway_interface.py`)
   - Interface abstrata `PaymentGateway` define o contrato
   - Cada gateway implementa isoladamente

2. **Factory Pattern** (`gateway_factory.py`)
   - `GatewayFactory` cria instâncias dinamicamente
   - Registry de gateways disponíveis

3. **Isolamento Completo**
   - Cada gateway em arquivo separado
   - Zero dependências entre gateways
   - Fácil manutenção e testes

### **Gateways Atuais**

| Gateway | Arquivo | Tipo | Status |
|---------|---------|------|--------|
| **SyncPay** | `gateway_syncpay.py` | `syncpay` | ✅ Ativo |
| **PushynPay** | `gateway_pushyn.py` | `pushynpay` | ✅ Ativo |
| **Paradise** | `gateway_paradise.py` | `paradise` | ✅ Ativo |
| **WiinPay** | `gateway_wiinpay.py` | `wiinpay` | ✅ Ativo |

---

## 🔧 **Componentes do Sistema**

### **1. Interface Base (`gateway_interface.py`)**

```python
class PaymentGateway(ABC):
    @abstractmethod
    def generate_pix(...) -> Optional[Dict[str, Any]]
    
    @abstractmethod
    def process_webhook(...) -> Optional[Dict[str, Any]]
    
    @abstractmethod
    def verify_credentials(...) -> bool
    
    @abstractmethod
    def get_payment_status(...) -> Optional[Dict[str, Any]]
    
    @abstractmethod
    def get_webhook_url(...) -> str
    
    @abstractmethod
    def get_gateway_name(...) -> str
    
    @abstractmethod
    def get_gateway_type(...) -> str
```

**Formato de Retorno `generate_pix()`:**
```python
{
    'pix_code': str,              # ✅ OBRIGATÓRIO - Código PIX copia e cola
    'qr_code_url': str,           # ✅ OBRIGATÓRIO - URL da imagem QR Code
    'transaction_id': str,        # ✅ OBRIGATÓRIO - ID da transação no gateway
    'payment_id': str,            # ✅ OBRIGATÓRIO - ID do pagamento no sistema
    'qr_code_base64': str,        # ⚠️ OPCIONAL - QR Code em base64
    'expires_at': datetime        # ⚠️ OPCIONAL - Data de expiração
}
```

**Formato de Retorno `process_webhook()` e `get_payment_status()`:**
```python
{
    'payment_id': str,              # ID único do pagamento
    'status': str,                  # 'pending', 'paid', 'failed'
    'amount': float,                # Valor em reais
    'gateway_transaction_id': str,  # ID no gateway
    'payer_name': str,              # ⚠️ OPCIONAL
    'payer_document': str,          # ⚠️ OPCIONAL
    'end_to_end_id': str           # ⚠️ OPCIONAL - E2E do BC
}
```

### **2. Factory (`gateway_factory.py`)**

```python
class GatewayFactory:
    _gateway_classes: Dict[str, Type[PaymentGateway]] = {
        'syncpay': SyncPayGateway,
        'pushynpay': PushynGateway,
        'paradise': ParadisePaymentGateway,
        'wiinpay': WiinPayGateway,
        # ✅ Adicionar novo gateway aqui
    }
    
    @classmethod
    def create_gateway(cls, gateway_type: str, credentials: Dict) -> Optional[PaymentGateway]:
        # Lógica de criação
```

### **3. Model (`models.py`)**

```python
class Gateway(db.Model):
    gateway_type = db.Column(db.String(30))  # syncpay, pushynpay, etc
    
    # Credenciais genéricas (criptografadas)
    client_id = db.Column(db.String(255))
    _client_secret = db.Column('client_secret', db.String(1000))  # Criptografado
    _api_key = db.Column('api_key', db.String(1000))  # Criptografado
    
    # ✅ Campos específicos podem ser adicionados conforme necessário
    _product_hash = db.Column('product_hash', db.String(1000))  # Paradise
    _split_user_id = db.Column('split_user_id', db.String(1000))  # WiinPay
    
    split_percentage = db.Column(db.Float, default=2.0)  # 2% PADRÃO
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
```

### **4. Webhook (`app.py`)**

```python
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
def payment_webhook(gateway_type):
    # Roteamento automático baseado em gateway_type
    # Ex: /webhook/payment/novogateway → cria instância e processa
```

---

## 📝 **Passo a Passo para Integrar Novo Gateway**

### **Passo 1: Criar Arquivo do Gateway**

Criar `gateway_novogateway.py`:

```python
"""
Gateway NovoGateway - Implementação Isolada
Documentação: https://docs.novogateway.com
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class NovoGateway(PaymentGateway):
    """
    Implementação do gateway NovoGateway
    
    Características:
    - Autenticação via API Key
    - Webhook para confirmação de pagamento
    """
    
    def __init__(self, api_key: str, merchant_id: str = None):
        """
        Inicializa gateway NovoGateway
        
        Args:
            api_key: Chave de API do gateway
            merchant_id: ID do merchant (opcional)
        """
        self.api_key = api_key
        self.merchant_id = merchant_id
        self.base_url = "https://api.novogateway.com.br"
        self.split_percentage = 2.0  # 2% PADRÃO
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "NovoGateway"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "novogateway"
    
    def get_webhook_url(self) -> str:
        """URL do webhook NovoGateway"""
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        return f"{webhook_base}/webhook/payment/novogateway"
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via NovoGateway
        
        Endpoint: POST /api/v1/pix/create
        """
        try:
            # Validar valor
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # Preparar payload conforme API do gateway
            url = f"{self.base_url}/api/v1/pix/create"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'amount': float(amount),
                'description': description,
                'external_id': payment_id,
                'webhook_url': self.get_webhook_url(),
                # Adicionar campos específicos do gateway
            }
            
            logger.info(f"📤 [{self.get_gateway_name()}] Gerando PIX: R$ {amount:.2f} | ID: {payment_id}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                
                # ✅ Mapear resposta do gateway para formato padrão
                return {
                    'pix_code': data.get('pix_copy_paste'),  # Nome do campo na API
                    'qr_code_url': data.get('qr_code_url'),
                    'transaction_id': data.get('transaction_id'),
                    'payment_id': payment_id,
                    'qr_code_base64': data.get('qr_code_base64'),  # Se disponível
                    'expires_at': None  # Se disponível
                }
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook recebido do NovoGateway
        
        Args:
            data: Dados brutos do webhook (JSON)
        
        Returns:
            Dict no formato padrão ou None
        """
        try:
            # ✅ Mapear dados do webhook para formato padrão
            status_map = {
                'pending': 'pending',
                'paid': 'paid',
                'approved': 'paid',
                'failed': 'failed',
                'cancelled': 'failed'
            }
            
            gateway_status = data.get('status', '').lower()
            status = status_map.get(gateway_status, 'pending')
            
            return {
                'payment_id': data.get('external_id'),  # ID do sistema
                'status': status,
                'amount': float(data.get('amount', 0)),
                'gateway_transaction_id': data.get('transaction_id'),
                'payer_name': data.get('payer_name'),
                'payer_document': data.get('payer_document'),
                'end_to_end_id': data.get('end_to_end_id')
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas
        
        Endpoint: GET /api/v1/auth/verify
        """
        try:
            url = f"{self.base_url}/api/v1/auth/verify"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas")
                return True
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas: Status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento
        
        Endpoint: GET /api/v1/pix/{transaction_id}/status
        """
        try:
            url = f"{self.base_url}/api/v1/pix/{transaction_id}/status"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # ✅ Reutilizar lógica do process_webhook
                return self.process_webhook(data)
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: Status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            return None
```

### **Passo 2: Registrar no Factory**

Editar `gateway_factory.py`:

```python
# 1. Importar novo gateway
from gateway_novogateway import NovoGateway

class GatewayFactory:
    # 2. Adicionar ao registry
    _gateway_classes: Dict[str, Type[PaymentGateway]] = {
        'syncpay': SyncPayGateway,
        'pushynpay': PushynGateway,
        'paradise': ParadisePaymentGateway,
        'wiinpay': WiinPayGateway,
        'novogateway': NovoGateway,  # ✅ NOVO
    }
    
    @classmethod
    def create_gateway(cls, gateway_type: str, credentials: Dict[str, Any]) -> Optional[PaymentGateway]:
        # ... código existente ...
        
        # 3. Adicionar lógica de criação
        elif gateway_type == 'novogateway':
            api_key = credentials.get('api_key')
            merchant_id = credentials.get('merchant_id', '')
            
            if not api_key:
                logger.error(f"❌ [Factory] NovoGateway requer api_key")
                return None
            
            gateway = gateway_class(
                api_key=api_key,
                merchant_id=merchant_id
            )
```

### **Passo 3: Atualizar Model (se necessário)**

Se o novo gateway precisar de campos específicos no banco de dados:

```python
# models.py - Gateway class

# Adicionar campo específico (se necessário)
_merchant_id = db.Column('merchant_id', db.String(1000))  # Criptografado
```

E criar migration:

```python
# migrations/migrate_add_novogateway_fields.py

def upgrade():
    op.add_column('gateways', sa.Column('merchant_id', sa.String(1000), nullable=True))
```

### **Passo 4: Testar Webhook**

O webhook é roteado automaticamente via:
```
POST /webhook/payment/novogateway
```

O sistema já processa automaticamente baseado no `gateway_type`.

---

## 💡 **Exemplo Prático: Integração de Novo Gateway**

### **Cenário: Gateway "QuickPay"**

**API do QuickPay:**
- Base URL: `https://api.quickpay.com.br`
- Autenticação: Bearer Token via `api_key`
- Criar PIX: `POST /v2/pix/create`
- Webhook: `POST /webhook/quickpay`
- Status: `GET /v2/pix/{id}/status`

**Implementação:**

```python
# gateway_quickpay.py
class QuickPayGateway(PaymentGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.quickpay.com.br"
    
    def get_gateway_type(self) -> str:
        return "quickpay"
    
    def generate_pix(self, amount, description, payment_id, customer_data=None):
        url = f"{self.base_url}/v2/pix/create"
        headers = {'Authorization': f'Bearer {self.api_key}'}
        payload = {
            'valor': amount,  # Campo específico da API
            'descricao': description,
            'id_externo': payment_id
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'pix_code': data['codigo_pix'],  # Mapear campo
                'qr_code_url': data['qr_code'],
                'transaction_id': data['id_transacao'],
                'payment_id': payment_id
            }
        return None
```

**Registro no Factory:**

```python
# gateway_factory.py
from gateway_quickpay import QuickPayGateway

_gateway_classes = {
    # ... existentes ...
    'quickpay': QuickPayGateway,
}

# No create_gateway:
elif gateway_type == 'quickpay':
    api_key = credentials.get('api_key')
    if not api_key:
        return None
    return QuickPayGateway(api_key=api_key)
```

---

## ✅ **Checklist de Integração**

### **Implementação**
- [ ] Criar arquivo `gateway_nomegateway.py`
- [ ] Implementar todos os métodos abstratos de `PaymentGateway`
- [ ] Implementar `get_gateway_name()` (nome amigável)
- [ ] Implementar `get_gateway_type()` (tipo para roteamento)
- [ ] Implementar `get_webhook_url()` (URL do webhook)
- [ ] Implementar `generate_pix()` (retornar formato padrão)
- [ ] Implementar `process_webhook()` (mapear para formato padrão)
- [ ] Implementar `verify_credentials()` (validação de credenciais)
- [ ] Implementar `get_payment_status()` (consulta de status)

### **Integração**
- [ ] Importar gateway em `gateway_factory.py`
- [ ] Adicionar ao `_gateway_classes` registry
- [ ] Adicionar lógica de criação no `create_gateway()`
- [ ] Testar criação de instância via Factory
- [ ] Verificar se webhook é roteado corretamente

### **Banco de Dados (se necessário)**
- [ ] Adicionar campos específicos no model `Gateway` (se necessário)
- [ ] Criar migration para novos campos (se necessário)
- [ ] Testar salvamento/recuperação de credenciais

### **Testes**
- [ ] Testar `generate_pix()` com valores válidos
- [ ] Testar `verify_credentials()` com credenciais válidas/inválidas
- [ ] Testar `process_webhook()` com payload real do gateway
- [ ] Testar `get_payment_status()` com transaction_id válido
- [ ] Testar integração completa (criar PIX → receber webhook → verificar status)

### **Documentação**
- [ ] Adicionar docstring detalhada no gateway
- [ ] Documentar campos específicos necessários
- [ ] Documentar formato do webhook esperado
- [ ] Adicionar exemplos de uso

---

## 🔍 **Pontos de Atenção**

### **1. Formato de Retorno**
- ✅ **SEMPRE** retornar no formato padrão definido
- ✅ Mapear campos específicos do gateway para o formato padrão
- ✅ Garantir que campos obrigatórios estejam presentes

### **2. Tratamento de Erros**
- ✅ Logar todos os erros com contexto
- ✅ Retornar `None` em caso de erro (não lançar exceções)
- ✅ Validar entradas antes de processar

### **3. Webhook**
- ✅ O webhook é roteado automaticamente via `/webhook/payment/{gateway_type}`
- ✅ Implementar `process_webhook()` para mapear dados do gateway
- ✅ Validar assinatura/autenticação do webhook (se necessário)

### **4. Credenciais**
- ✅ Credenciais são armazenadas criptografadas no banco
- ✅ Usar `Gateway` model para salvar/recuperar
- ✅ Validar credenciais antes de usar

### **5. Split Payment**
- ✅ Sistema suporta split payment (padrão 2%)
- ✅ Configurar `split_percentage` no gateway/model
- ✅ Implementar split no `generate_pix()` se gateway suportar

---

## 📚 **Referências**

- **Interface Base**: `gateway_interface.py`
- **Factory**: `gateway_factory.py`
- **Exemplos**: `gateway_syncpay.py`, `gateway_pushyn.py`, `gateway_paradise.py`, `gateway_wiinpay.py`
- **Model**: `models.py` (classe `Gateway`)
- **Webhook**: `app.py` (rota `/webhook/payment/<gateway_type>`)
- **Uso**: `bot_manager.py` (método `_generate_pix_payment()`)

---

## ❓ **Dúvidas Frequentes**

**Q: Preciso modificar o banco de dados?**
A: Apenas se o gateway precisar de campos específicos além de `client_id`, `client_secret`, `api_key`. Caso contrário, use os campos genéricos.

**Q: Como testar sem credenciais reais?**
A: Use `verify_credentials()` com credenciais de teste/sandbox do gateway.

**Q: O webhook precisa de autenticação especial?**
A: Depende do gateway. Se necessário, implemente validação em `process_webhook()`.

**Q: Posso adicionar métodos específicos do gateway?**
A: Sim, mas mantenha os métodos abstratos implementados. Métodos extras podem ser chamados diretamente via instância.

---

**✅ Sistema pronto para integração de novos gateways seguindo este padrão!**

