# Requisitos para Implementação de Novos Gateways de Pagamento

## 📋 Índice

1. [Visão Geral da Arquitetura](#visão-geral-da-arquitetura)
2. [Padrões de Design Utilizados](#padrões-de-design-utilizados)
3. [Interface Obrigatória (PaymentGateway)](#interface-obrigatória-paymentgateway)
4. [Gateway Factory](#gateway-factory)
5. [Gateway Adapter](#gateway-adapter)
6. [Modelo de Dados (Gateway)](#modelo-de-dados-gateway)
7. [Fluxo de Criação de Pagamento](#fluxo-de-criação-de-pagamento)
8. [Fluxo de Processamento de Webhook](#fluxo-de-processamento-de-webhook)
9. [Gateways Existentes - Análise Detalhada](#gateways-existentes---análise-detalhada)
10. [Checklist de Implementação](#checklist-de-implementação)
11. [Exemplo Completo - Novo Gateway](#exemplo-completo---novo-gateway)

---

## 1. Visão Geral da Arquitetura

### 1.1 Sistema Multi-Gateway

O sistema suporta múltiplos gateways de pagamento simultaneamente, permitindo que cada usuário configure um ou mais gateways. A arquitetura foi projetada para:

- **Isolamento completo**: Cada gateway é independente e isolado
- **Extensibilidade**: Novos gateways podem ser adicionados sem modificar código existente
- **Normalização**: Todos os gateways retornam o mesmo formato através do `GatewayAdapter`
- **Multi-tenancy**: Suporte a múltiplos usuários com diferentes gateways (via `producer_hash`)

### 1.2 Componentes Principais

```
┌─────────────────────────────────────────────────────────────┐
│                    BotManager                                │
│  - Gerencia criação de pagamentos                           │
│  - Usa GatewayFactory para criar instâncias                 │
│  - Processa resultados e salva no banco                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  GatewayFactory                              │
│  - Registry de gateways disponíveis                         │
│  - Cria instâncias com credenciais específicas              │
│  - Envolve com GatewayAdapter (padrão)                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  GatewayAdapter                              │
│  - Normaliza entrada/saída de todos os gateways             │
│  - Tratamento de erros uniforme                             │
│  - Logging consistente                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              PaymentGateway (Interface)                      │
│  - Interface abstrata que todos os gateways implementam     │
│  - Métodos obrigatórios definidos                           │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        ▼            ▼            ▼            ▼
   ┌────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐
   │SyncPay │  │PushynPay│  │Paradise  │  │AtomoPay  │
   │Gateway │  │Gateway  │  │Gateway   │  │Gateway   │
   └────────┘  └─────────┘  └──────────┘  └──────────┘
```

### 1.3 Fluxo de Dados

#### Criação de Pagamento:
```
1. BotManager._generate_pix_payment()
   ↓
2. Busca Gateway no banco (models.Gateway)
   ↓
3. GatewayFactory.create_gateway(gateway_type, credentials)
   ↓
4. GatewayAdapter(gateway) - envolve o gateway
   ↓
5. gateway.generate_pix(amount, description, payment_id, customer_data)
   ↓
6. Retorna dict normalizado: {pix_code, qr_code_url, transaction_id, ...}
   ↓
7. BotManager salva Payment no banco
```

#### Processamento de Webhook:
```
1. app.py: payment_webhook(gateway_type)
   ↓
2. GatewayFactory.create_gateway(gateway_type, dummy_credentials)
   ↓
3. gateway.process_webhook(data)
   ↓
4. Retorna dict normalizado: {gateway_transaction_id, status, amount, ...}
   ↓
5. Busca Payment no banco (por gateway_transaction_id, hash, reference)
   ↓
6. Atualiza status e processa entregável
```

---

## 2. Padrões de Design Utilizados

### 2.1 Strategy Pattern
- **PaymentGateway**: Interface abstrata que define o contrato
- **Implementações concretas**: Cada gateway implementa a interface
- **Isolamento**: Mudanças em um gateway não afetam outros

### 2.2 Factory Pattern
- **GatewayFactory**: Cria instâncias de gateways baseado no tipo
- **Registry**: Mantém registro de todos os gateways disponíveis
- **Extensibilidade**: Novos gateways são registrados no factory

### 2.3 Adapter Pattern
- **GatewayAdapter**: Normaliza entrada/saída de todos os gateways
- **Consistência**: Garante que todos retornem o mesmo formato
- **Transparência**: GatewayAdapter implementa PaymentGateway, então é transparente para o sistema

### 2.4 Template Method Pattern
- **PaymentGateway**: Define métodos abstratos que devem ser implementados
- **Implementações**: Cada gateway implementa os métodos conforme sua API

---

## 3. Interface Obrigatória (PaymentGateway)

### 3.1 Arquivo: `gateway_interface.py`

Todos os gateways DEVEM implementar a interface `PaymentGateway`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

class PaymentGateway(ABC):
    """Interface abstrata para todos os gateways de pagamento"""
    
    @abstractmethod
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera um pagamento PIX no gateway
        
        Args:
            amount: Valor em reais (ex: 10.50)
            description: Descrição do produto/serviço
            payment_id: ID único do pagamento no sistema
            customer_data: Dados opcionais do cliente (nome, CPF, email, etc)
        
        Returns:
            Dict com dados do PIX gerado:
            {
                'pix_code': str,              # Código PIX copia e cola (OBRIGATÓRIO)
                'qr_code_url': str,           # URL da imagem QR Code (OBRIGATÓRIO)
                'transaction_id': str,        # ID da transação no gateway (OBRIGATÓRIO)
                'payment_id': str,            # ID do pagamento no sistema (OBRIGATÓRIO)
                'qr_code_base64': str,        # QR Code em base64 (opcional)
                'gateway_hash': str,          # Hash da transação (para webhook matching) (RECOMENDADO)
                'reference': str,             # Reference externo (para webhook matching) (RECOMENDADO)
                'producer_hash': str,         # Hash do producer (multi-tenancy) (OPCIONAL)
                'expires_at': datetime        # Data de expiração (opcional)
            }
            
            None em caso de erro
        """
        pass
    
    @abstractmethod
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook recebido do gateway
        
        Args:
            data: Dados brutos do webhook (JSON do gateway)
        
        Returns:
            Dict com dados processados:
            {
                'payment_id': str,              # ID único do pagamento (OPCIONAL - será buscado)
                'status': str,                  # 'pending', 'paid', 'failed' (OBRIGATÓRIO)
                'amount': float,                # Valor em reais (OBRIGATÓRIO)
                'gateway_transaction_id': str,  # ID no gateway (OBRIGATÓRIO)
                'gateway_hash': str,            # Hash da transação (RECOMENDADO)
                'external_reference': str,      # Reference externo (RECOMENDADO)
                'producer_hash': str,           # Hash do producer (multi-tenancy) (OPCIONAL)
                'payer_name': str,              # Nome do pagador (opcional)
                'payer_document': str,          # CPF/CNPJ (opcional)
                'end_to_end_id': str            # E2E do BC (opcional)
            }
            
            None em caso de erro
        """
        pass
    
    @abstractmethod
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais do gateway são válidas
        
        Returns:
            True se credenciais válidas, False caso contrário
        """
        pass
    
    @abstractmethod
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento no gateway
        
        Args:
            transaction_id: ID da transação no gateway
        
        Returns:
            Mesmo formato do process_webhook()
            None em caso de erro
        """
        pass
    
    @abstractmethod
    def get_webhook_url(self) -> str:
        """
        Retorna URL do webhook para este gateway
        
        Returns:
            URL completa do webhook (ex: https://domain.com/webhook/payment/syncpay)
        """
        pass
    
    @abstractmethod
    def get_gateway_name(self) -> str:
        """
        Retorna nome identificador do gateway
        
        Returns:
            Nome do gateway (ex: 'SyncPay', 'PushynPay')
        """
        pass
    
    @abstractmethod
    def get_gateway_type(self) -> str:
        """
        Retorna tipo do gateway (usado para roteamento)
        
        Returns:
            Tipo do gateway (ex: 'syncpay', 'pushynpay')
        """
        pass
    
    def extract_producer_hash(
        self,
        webhook_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Extrai producer_hash do webhook para multi-tenancy (implementação opcional).
        
        Gateways que suportam multi-tenancy devem sobrescrever este método.
        
        Args:
            webhook_data: Dados brutos do webhook
        
        Returns:
            str: producer_hash ou None se não suportado/não encontrado
        """
        return None
```

### 3.2 Campos Obrigatórios no Retorno

#### `generate_pix()` DEVE retornar:
- ✅ `pix_code`: Código PIX copia e cola (string)
- ✅ `qr_code_url`: URL da imagem QR Code ou base64 (string)
- ✅ `transaction_id`: ID da transação no gateway (string)
- ✅ `payment_id`: ID do pagamento no sistema (string)

#### `process_webhook()` DEVE retornar:
- ✅ `gateway_transaction_id`: ID da transação no gateway (string)
- ✅ `status`: Status do pagamento ('pending', 'paid', 'failed') (string)
- ✅ `amount`: Valor em reais (float)

### 3.3 Campos Recomendados

#### Para `generate_pix()`:
- 🔵 `gateway_hash`: Hash da transação (para webhook matching)
- 🔵 `reference`: Reference externo (para webhook matching)
- 🔵 `producer_hash`: Hash do producer (multi-tenancy)

#### Para `process_webhook()`:
- 🔵 `gateway_hash`: Hash da transação (para webhook matching)
- 🔵 `external_reference`: Reference externo (para webhook matching)
- 🔵 `producer_hash`: Hash do producer (multi-tenancy)

---

## 4. Gateway Factory

### 4.1 Arquivo: `gateway_factory.py`

O `GatewayFactory` é responsável por criar instâncias de gateways:

```python
class GatewayFactory:
    """Factory para criar instâncias de gateways de pagamento"""
    
    # Registry de gateways disponíveis
    _gateway_classes: Dict[str, Type[PaymentGateway]] = {
        'syncpay': SyncPayGateway,
        'pushynpay': PushynGateway,
        'paradise': ParadisePaymentGateway,
        'wiinpay': WiinPayGateway,
        'atomopay': AtomPayGateway,
        # ✅ NOVO GATEWAY: Adicionar aqui
        # 'novogateway': NovoGateway,
    }
    
    @classmethod
    def create_gateway(
        cls, 
        gateway_type: str, 
        credentials: Dict[str, Any],
        use_adapter: bool = True
    ) -> Optional[PaymentGateway]:
        """
        Cria uma instância do gateway apropriado
        
        Args:
            gateway_type: Tipo do gateway ('syncpay', 'pushynpay', etc)
            credentials: Credenciais específicas do gateway
            use_adapter: Se True, envolve o gateway com GatewayAdapter (padrão: True)
        
        Returns:
            Instância do gateway configurada (com ou sem adapter) ou None se inválido
        """
        # 1. Validar tipo de gateway
        # 2. Buscar classe do gateway no registry
        # 3. Validar credenciais
        # 4. Criar instância com credenciais específicas
        # 5. Envolver com GatewayAdapter se use_adapter=True
        # 6. Retornar instância
        pass
```

### 4.2 Registro de Novo Gateway

Para adicionar um novo gateway, você DEVE:

1. **Importar a classe do gateway**:
```python
from gateway_novogateway import NovoGateway
```

2. **Registrar no `_gateway_classes`**:
```python
_gateway_classes: Dict[str, Type[PaymentGateway]] = {
    # ... gateways existentes ...
    'novogateway': NovoGateway,  # ✅ NOVO GATEWAY
}
```

3. **Implementar lógica de criação no `create_gateway()`**:
```python
elif gateway_type == 'novogateway':
    # NovoGateway requer: api_key
    api_key = credentials.get('api_key')
    
    if not api_key:
        logger.error(f"❌ [Factory] NovoGateway requer api_key")
        return None
    
    gateway = gateway_class(
        api_key=api_key
    )
```

### 4.3 Credenciais por Gateway

Cada gateway tem credenciais específicas:

| Gateway | Credenciais Obrigatórias | Credenciais Opcionais |
|---------|-------------------------|----------------------|
| SyncPay | `client_id`, `client_secret` | `split_user_id`, `split_percentage` |
| PushynPay | `api_key` | `split_account_id`, `split_percentage` |
| Paradise | `api_key`, `product_hash` | `offer_hash`, `store_id`, `split_percentage` |
| WiinPay | `api_key` | `split_user_id`, `split_percentage` |
| Átomo Pay | `api_token` | `product_hash`, `offer_hash` |

**Novo Gateway**: Definir credenciais obrigatórias e opcionais conforme documentação da API.

---

## 5. Gateway Adapter

### 5.1 Arquivo: `gateway_adapter.py`

O `GatewayAdapter` normaliza entrada/saída de todos os gateways:

```python
class GatewayAdapter(PaymentGateway):
    """
    Adapter que normaliza dados entre gateways diferentes.
    Garante consistência de formato, tratamento de erros e logging.
    """
    
    def __init__(self, gateway: PaymentGateway):
        """Args: gateway: Instância do gateway a ser adaptada"""
        self._gateway = gateway
    
    def generate_pix(...) -> Optional[Dict[str, Any]]:
        """Normaliza generate_pix de todos os gateways"""
        # 1. Validar inputs
        # 2. Chamar gateway real
        # 3. Normalizar resposta
        # 4. Retornar formato padronizado
        pass
    
    def process_webhook(...) -> Optional[Dict[str, Any]]:
        """Normaliza process_webhook de todos os gateways"""
        # 1. Validar webhook_data
        # 2. Chamar gateway real
        # 3. Normalizar resposta
        # 4. Retornar formato padronizado
        pass
```

### 5.2 Normalização de Respostas

O `GatewayAdapter` normaliza respostas para garantir consistência:

#### `generate_pix()` - Campos Normalizados:
```python
normalized = {
    'transaction_id': result.get('transaction_id') or result.get('id') or result.get('hash'),
    'pix_code': result.get('pix_code') or result.get('qr_code') or result.get('emv'),
    'qr_code_url': result.get('qr_code_url') or result.get('qr_code_base64') or '',
    'qr_code_base64': result.get('qr_code_base64'),
    'payment_id': payment_id,
    'gateway_hash': result.get('gateway_hash') or result.get('hash') or result.get('transaction_hash'),
    'reference': result.get('reference') or result.get('external_reference'),
    'producer_hash': result.get('producer_hash'),
    'status': result.get('status', 'pending'),
    'error': result.get('error')
}
```

#### `process_webhook()` - Status Normalizado:
```python
# Mapeamento de status para formato interno
paid_aliases = {
    'paid', 'pago', 'approved', 'aprovado', 'confirmed', 'confirmado',
    'completed', 'concluded', 'concluido', 'concluído', 'success', 'succeeded',
    'received', 'recebido', 'settled', 'captured', 'finished', 'done'
}
failed_aliases = {
    'failed', 'falhou', 'cancelled', 'canceled', 'refused', 'rejected',
    'expired', 'chargeback', 'reversed', 'denied'
}

# Normalizar status
if any(candidate in paid_aliases for candidate in status_candidates):
    status = 'paid'
elif any(candidate in failed_aliases for candidate in status_candidates):
    status = 'failed'
else:
    status = 'pending'
```

### 5.3 Uso do Adapter

O `GatewayAdapter` é usado automaticamente pelo `GatewayFactory`:

```python
# Criar gateway com adapter (padrão)
gateway = GatewayFactory.create_gateway('syncpay', credentials, use_adapter=True)
# gateway é uma instância de GatewayAdapter que envolve SyncPayGateway

# Criar gateway sem adapter (não recomendado)
gateway = GatewayFactory.create_gateway('syncpay', credentials, use_adapter=False)
# gateway é uma instância direta de SyncPayGateway
```

**Recomendação**: Sempre usar `use_adapter=True` (padrão) para garantir normalização.

---

## 6. Modelo de Dados (Gateway)

### 6.1 Arquivo: `models.py`

O modelo `Gateway` armazena configurações de gateways no banco de dados:

```python
class Gateway(db.Model):
    """Gateway de Pagamento"""
    __tablename__ = 'gateways'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Tipo de gateway
    gateway_type = db.Column(db.String(30), nullable=False)  # syncpay, pushynpay, paradise, etc
    
    # Credenciais (criptografadas)
    client_id = db.Column(db.String(255))
    _client_secret = db.Column('client_secret', db.String(1000))  # Criptografado
    _api_key = db.Column('api_key', db.String(1000))  # Criptografado
    
    # Campos específicos por gateway (criptografados)
    _product_hash = db.Column('product_hash', db.String(1000))  # Criptografado
    _offer_hash = db.Column('offer_hash', db.String(1000))  # Criptografado
    store_id = db.Column(db.String(50))  # ID da conta (não sensível)
    _split_user_id = db.Column('split_user_id', db.String(1000))  # Criptografado
    
    # Multi-tenancy (não criptografado - apenas identificador)
    producer_hash = db.Column(db.String(100), nullable=True, index=True)
    
    # Split configuration (padrão 2%)
    split_percentage = db.Column(db.Float, default=2.0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    last_error = db.Column(db.Text)
    
    # Estatísticas
    total_transactions = db.Column(db.Integer, default=0)
    successful_transactions = db.Column(db.Integer, default=0)
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    verified_at = db.Column(db.DateTime)
```

### 6.2 Propriedades com Criptografia

Credenciais sensíveis são criptografadas automaticamente:

```python
@property
def api_key(self):
    """Descriptografa api_key ao acessar"""
    if not self._api_key:
        return None
    try:
        from utils.encryption import decrypt
        return decrypt(self._api_key)
    except Exception as e:
        logger.error(f"Erro ao descriptografar api_key gateway {self.id}: {e}")
        return None

@api_key.setter
def api_key(self, value):
    """Criptografa api_key ao armazenar"""
    if not value:
        self._api_key = None
    else:
        from utils.encryption import encrypt
        self._api_key = encrypt(value)
```

### 6.3 Adicionar Campos para Novo Gateway

Se o novo gateway precisar de campos específicos:

1. **Adicionar coluna no banco** (migration):
```python
# migration: add_novogateway_fields.py
_novo_campo = db.Column('novo_campo', db.String(1000))  # Criptografado
```

2. **Adicionar propriedade no modelo**:
```python
@property
def novo_campo(self):
    """Descriptografa novo_campo ao acessar"""
    if not self._novo_campo:
        return None
    try:
        from utils.encryption import decrypt
        return decrypt(self._novo_campo)
    except Exception as e:
        logger.error(f"Erro ao descriptografar novo_campo gateway {self.id}: {e}")
        return None

@novo_campo.setter
def novo_campo(self, value):
    """Criptografa novo_campo ao armazenar"""
    if not value:
        self._novo_campo = None
    else:
        from utils.encryption import encrypt
        self._novo_campo = encrypt(value)
```

3. **Atualizar `bot_manager.py` para passar credenciais**:
```python
credentials = {
    # ... outras credenciais ...
    'novo_campo': gateway.novo_campo,  # ✅ NOVO CAMPO
}
```

---

## 7. Fluxo de Criação de Pagamento

### 7.1 Arquivo: `bot_manager.py`

O método `_generate_pix_payment()` é responsável por criar pagamentos:

```python
def _generate_pix_payment(
    self, 
    bot_id: int, 
    amount: float, 
    description: str,
    customer_name: str, 
    customer_username: str, 
    customer_user_id: str,
    ...
) -> Optional[Dict[str, Any]]:
    """
    Gera pagamento PIX via gateway configurado
    """
    # 1. Buscar bot e gateway no banco
    bot = db.session.get(Bot, bot_id)
    gateway = Gateway.query.filter_by(
        user_id=bot.user_id,
        is_active=True,
        is_verified=True
    ).first()
    
    # 2. Preparar credenciais específicas do gateway
    credentials = {
        'client_id': gateway.client_id,
        'client_secret': gateway.client_secret,
        'api_key': gateway.api_key,
        'api_token': gateway.api_key if gateway.gateway_type == 'atomopay' else None,
        'product_hash': gateway.product_hash,
        'offer_hash': gateway.offer_hash,
        'store_id': gateway.store_id,
        'split_user_id': gateway.split_user_id,
        'split_percentage': user_commission
    }
    
    # 3. Criar gateway via Factory
    payment_gateway = GatewayFactory.create_gateway(
        gateway_type=gateway.gateway_type,
        credentials=credentials
    )
    
    # 4. Gerar PIX
    pix_result = payment_gateway.generate_pix(
        amount=amount,
        description=description,
        payment_id=payment_id,
        customer_data={
            'name': customer_name or 'Cliente',
            'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
            'phone': customer_user_id,
            'document': customer_user_id
        }
    )
    
    # 5. Salvar Payment no banco
    payment = Payment(
        bot_id=bot_id,
        payment_id=payment_id,
        amount=amount,
        status=payment_status,
        gateway_type=gateway.gateway_type,
        gateway_transaction_id=gateway_transaction_id,
        gateway_transaction_hash=gateway_hash,
        product_description=pix_result.get('pix_code'),
        ...
    )
    db.session.add(payment)
    db.session.commit()
    
    # 6. Retornar resultado
    return pix_result
```

### 7.2 Dados do Cliente

O sistema passa dados do cliente para o gateway:

```python
customer_data = {
    'name': customer_name or 'Cliente',
    'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
    'phone': customer_user_id,  # User ID do Telegram
    'document': customer_user_id  # User ID do Telegram
}
```

**Observação**: Alguns gateways requerem dados reais (CPF, telefone, etc). O gateway deve gerar dados únicos se necessário (ver gateways existentes).

### 7.3 Validações Específicas

Alguns gateways têm validações específicas:

```python
# WiinPay: valor mínimo R$ 3,00
if gateway.gateway_type == 'wiinpay' and amount < 3.0:
    logger.error(f"❌ WIINPAY: Valor mínimo R$ 3,00 | Produto: R$ {amount:.2f}")
    return None
```

**Novo Gateway**: Adicionar validações específicas conforme documentação da API.

---

## 8. Fluxo de Processamento de Webhook

### 8.1 Arquivo: `app.py`

A rota `/webhook/payment/<gateway_type>` processa webhooks:

```python
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@limiter.limit("500 per minute")
@csrf.exempt
def payment_webhook(gateway_type):
    """
    Webhook para confirmação de pagamento
    """
    # 1. Receber dados do webhook
    data = request.get_json(silent=True)
    
    # 2. Criar gateway com credenciais dummy (webhook não precisa de credenciais reais)
    dummy_credentials = {}
    if gateway_type == 'syncpay':
        dummy_credentials = {'client_id': 'dummy', 'client_secret': 'dummy'}
    elif gateway_type == 'pushynpay':
        dummy_credentials = {'api_key': 'dummy'}
    # ... outros gateways ...
    
    # 3. Criar gateway com adapter
    gateway_instance = GatewayFactory.create_gateway(
        gateway_type, 
        dummy_credentials, 
        use_adapter=True
    )
    
    # 4. Extrair producer_hash (multi-tenancy)
    producer_hash = None
    if hasattr(gateway_instance, 'extract_producer_hash'):
        producer_hash = gateway_instance.extract_producer_hash(data)
        if producer_hash:
            # Buscar Gateway pelo producer_hash
            gateway = Gateway.query.filter_by(
                gateway_type=gateway_type,
                producer_hash=producer_hash
            ).first()
    
    # 5. Processar webhook
    result = gateway_instance.process_webhook(data)
    
    # 6. Buscar Payment no banco (por múltiplas chaves)
    payment = None
    
    # Prioridade 1: gateway_transaction_id
    if result.get('gateway_transaction_id'):
        payment = Payment.query.filter_by(
            gateway_transaction_id=str(result.get('gateway_transaction_id'))
        ).first()
    
    # Prioridade 2: gateway_hash
    if not payment and result.get('gateway_hash'):
        payment = Payment.query.filter_by(
            gateway_transaction_hash=str(result.get('gateway_hash'))
        ).first()
    
    # Prioridade 3: external_reference
    if not payment and result.get('external_reference'):
        # Tentar extrair payment_id do reference
        # ...
        payment = Payment.query.filter_by(payment_id=extracted_payment_id).first()
    
    # 7. Atualizar status do pagamento
    if payment:
        payment.status = result.get('status')
        if result.get('status') == 'paid':
            # Processar entregável
            send_payment_delivery(payment, bot_manager)
            # Atualizar estatísticas
            payment.bot.total_sales += 1
            payment.bot.total_revenue += payment.amount
            # ...
        db.session.commit()
    
    # 8. Retornar 200 (webhook processado)
    return jsonify({'status': 'ok'}), 200
```

### 8.2 Busca de Payment

O sistema busca o `Payment` por múltiplas chaves (prioridade):

1. **gateway_transaction_id**: ID da transação no gateway
2. **gateway_hash**: Hash da transação
3. **external_reference**: Reference externo (pode conter payment_id)
4. **amount + gateway_type + status pending**: Fallback (últimos 10 pagamentos)

### 8.3 Multi-Tenancy

Gateways que suportam multi-tenancy (ex: Átomo Pay) devem:

1. **Extrair producer_hash do webhook**:
```python
def extract_producer_hash(self, webhook_data: Dict[str, Any]) -> Optional[str]:
    """Extrai producer_hash do webhook"""
    producer_data = webhook_data.get('producer', {})
    if isinstance(producer_data, dict):
        return producer_data.get('hash')
    return None
```

2. **Salvar producer_hash no Gateway**:
```python
# No generate_pix(), salvar producer_hash no Gateway
if pix_result.get('producer_hash'):
    gateway.producer_hash = pix_result.get('producer_hash')
    db.session.commit()
```

3. **Filtrar por producer_hash no webhook**:
```python
# No payment_webhook(), filtrar por producer_hash
if producer_hash:
    gateway = Gateway.query.filter_by(
        gateway_type=gateway_type,
        producer_hash=producer_hash
    ).first()
    if gateway:
        # Filtrar Payments do usuário correto
        user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
        payment_query = payment_query.filter(Payment.bot_id.in_(user_bot_ids))
```

---

## 9. Gateways Existentes - Análise Detalhada

### 9.1 SyncPay

**Arquivo**: `gateway_syncpay.py`

**Características**:
- Autenticação: Bearer Token (client_id + client_secret)
- Valores: Reais (float)
- Split: Percentual (1-100%)
- Webhook: POST com dados em `data` wrapper

**Credenciais**:
- `client_id`: UUID do client ID
- `client_secret`: UUID do client secret
- `split_user_id`: UUID do usuário para split (opcional)
- `split_percentage`: Percentual de split (opcional)

**Métodos**:
- `_generate_bearer_token()`: Gera token Bearer (válido por 1 hora)
- `generate_pix()`: Cria pagamento PIX
- `process_webhook()`: Processa webhook (dados em `data` wrapper)
- `verify_credentials()`: Verifica credenciais (gera token)

**Resposta `generate_pix()`**:
```python
{
    'pix_code': str,  # Código PIX
    'qr_code_url': str,  # URL do QR Code
    'transaction_id': str,  # identifier
    'payment_id': str,
    'expires_at': None
}
```

**Webhook `process_webhook()`**:
```python
{
    'gateway_transaction_id': str,  # id
    'status': str,  # 'paid', 'pending', 'failed'
    'amount': float,  # Valor em reais
    'external_reference': str  # external_reference
}
```

### 9.2 PushynPay

**Arquivo**: `gateway_pushyn.py`

**Características**:
- Autenticação: Bearer Token (API Key)
- Valores: Centavos (int)
- Split: Valor fixo (máximo 50%)
- Webhook: POST com status direto

**Credenciais**:
- `api_key`: API Key da Pushyn
- `split_account_id`: Account ID para split (opcional)
- `split_percentage`: Percentual de split (opcional)

**Métodos**:
- `generate_pix()`: Cria pagamento PIX (valores em centavos)
- `process_webhook()`: Processa webhook (status direto)
- `verify_credentials()`: Verifica credenciais (validação básica)
- `get_payment_status()`: Consulta status (GET /api/transactions/{id})

**Resposta `generate_pix()`**:
```python
{
    'pix_code': str,  # qr_code
    'qr_code_url': str,  # qr_code_base64 ou URL gerada
    'qr_code_base64': str,  # Base64 do QR Code
    'transaction_id': str,  # id
    'payment_id': str,
    'expires_at': None
}
```

**Webhook `process_webhook()`**:
```python
{
    'gateway_transaction_id': str,  # id
    'status': str,  # 'paid', 'pending', 'failed'
    'amount': float,  # Valor em reais (convertido de centavos)
    'payer_name': str,  # payer_name
    'payer_document': str,  # payer_national_registration
    'end_to_end_id': str  # end_to_end_id
}
```

### 9.3 Paradise

**Arquivo**: `gateway_paradise.py`

**Características**:
- Autenticação: X-API-Key (Secret Key)
- Valores: Centavos (int)
- Split: Valor fixo (via store_id)
- Webhook: POST com status direto

**Credenciais**:
- `api_key`: Secret Key (sk_...)
- `product_hash`: Código do produto (prod_...)
- `offer_hash`: ID da oferta (opcional - não enviado para evitar duplicação)
- `store_id`: ID da conta para split
- `split_percentage`: Percentual de split (padrão 2%)

**Métodos**:
- `generate_pix()`: Cria pagamento PIX (valores em centavos)
- `process_webhook()`: Processa webhook (status direto)
- `verify_credentials()`: Verifica credenciais (validação local)
- `get_payment_status()`: Consulta status (GET /check_status.php?hash={id})

**Resposta `generate_pix()`**:
```python
{
    'pix_code': str,  # qr_code
    'qr_code_url': str,  # qr_code_base64 ou URL gerada
    'transaction_id': str,  # transaction_id (numérico)
    'transaction_hash': str,  # id (painel) ou hash
    'payment_id': str
}
```

**Webhook `process_webhook()`**:
```python
{
    'gateway_transaction_id': str,  # transaction_id ou id
    'status': str,  # 'paid', 'pending', 'failed'
    'amount': float  # Valor em reais (convertido de centavos)
}
```

**Observações**:
- ✅ Dados únicos por transação (email, CPF, telefone, nome) - timestamp + hash
- ✅ Reference único (timestamp + hash) - evita IDs duplicados
- ❌ Não enviar offerHash para evitar duplicação

### 9.4 WiinPay

**Arquivo**: `gateway_wiinpay.py`

**Características**:
- Autenticação: api_key no body
- Valores: Reais (float)
- Split: Percentual OU valor fixo
- Webhook: POST com status direto
- Valor mínimo: R$ 3,00

**Credenciais**:
- `api_key`: Chave API da WiinPay
- `split_user_id`: User ID para split (opcional)
- `split_percentage`: Percentual de split (opcional)

**Métodos**:
- `generate_pix()`: Cria pagamento PIX (valores em reais)
- `process_webhook()`: Processa webhook (status direto)
- `verify_credentials()`: Verifica credenciais (validação básica)
- `get_payment_status()`: Consulta status (GET /payment/{id})

**Resposta `generate_pix()`**:
```python
{
    'pix_code': str,  # qr_code
    'qr_code_url': str,  # qr_code_url
    'transaction_id': str,  # paymentId
    'payment_id': str,
    'gateway_type': str,  # 'wiinpay'
    'amount': float
}
```

**Webhook `process_webhook()`**:
```python
{
    'gateway_transaction_id': str,  # id
    'status': str,  # 'paid', 'pending', 'failed'
    'amount': float,  # Valor em reais
    'payer_name': str,  # payer_name
    'payer_document': str,  # payer_document
    'gateway_type': str  # 'wiinpay'
}
```

### 9.5 Átomo Pay

**Arquivo**: `gateway_atomopay.py`

**Características**:
- Autenticação: api_token como query parameter
- Valores: Centavos (int)
- Multi-tenancy: Suporta producer_hash
- Webhook: POST com dados em múltiplos formatos

**Credenciais**:
- `api_token`: Token de API
- `product_hash`: Hash do produto (obrigatório para criar ofertas)
- `offer_hash`: Hash da oferta (opcional - criado dinamicamente)

**Métodos**:
- `generate_pix()`: Cria pagamento PIX (valores em centavos)
- `process_webhook()`: Processa webhook (múltiplos formatos)
- `verify_credentials()`: Verifica credenciais (GET /products)
- `get_payment_status()`: Consulta status (GET /transactions/{id})
- `extract_producer_hash()`: Extrai producer_hash do webhook (multi-tenancy)

**Resposta `generate_pix()`**:
```python
{
    'pix_code': str,  # pix_qr_code
    'qr_code_url': str,  # pix_url ou pix_base64
    'transaction_id': str,  # id (webhook busca por este)
    'transaction_hash': str,  # hash (fallback)
    'gateway_hash': str,  # hash (para webhook matching)
    'producer_hash': str,  # producer.hash (multi-tenancy)
    'payment_id': str,
    'reference': str  # reference (para webhook matching)
}
```

**Webhook `process_webhook()`**:
```python
{
    'gateway_transaction_id': str,  # id
    'gateway_hash': str,  # hash
    'producer_hash': str,  # producer.hash
    'status': str,  # 'paid', 'pending', 'failed'
    'amount': float,  # Valor em reais (convertido de centavos)
    'external_reference': str  # reference
}
```

**Observações**:
- ✅ Dados únicos por transação (email, CPF, telefone, nome) - timestamp + hash
- ✅ Reference único (timestamp + hash) - evita IDs duplicados
- ✅ Ofertas criadas dinamicamente (evita conflitos de valor)
- ✅ Multi-tenancy via producer_hash
- ✅ product_hash obrigatório (criado dinamicamente se não existir)

---

## 10. Checklist de Implementação

### 10.1 Criar Arquivo do Gateway

- [ ] Criar arquivo `gateway_novogateway.py`
- [ ] Importar `PaymentGateway` de `gateway_interface`
- [ ] Criar classe `NovoGateway(PaymentGateway)`
- [ ] Implementar método `__init__()` com credenciais

### 10.2 Implementar Métodos Obrigatórios

- [ ] Implementar `generate_pix()`
  - [ ] Validar valor (amount > 0)
  - [ ] Converter valor se necessário (reais ↔ centavos)
  - [ ] Fazer requisição à API do gateway
  - [ ] Extrair `pix_code`, `qr_code_url`, `transaction_id`
  - [ ] Retornar dict no formato padronizado
  - [ ] Tratar erros e retornar `None` em caso de falha

- [ ] Implementar `process_webhook()`
  - [ ] Extrair `gateway_transaction_id` do webhook
  - [ ] Extrair `status` do webhook
  - [ ] Mapear status para formato interno ('pending', 'paid', 'failed')
  - [ ] Extrair `amount` do webhook
  - [ ] Converter valor se necessário (centavos → reais)
  - [ ] Retornar dict no formato padronizado
  - [ ] Tratar erros e retornar `None` em caso de falha

- [ ] Implementar `verify_credentials()`
  - [ ] Validar credenciais localmente (formato, tamanho, etc)
  - [ ] Fazer requisição de teste à API (se disponível)
  - [ ] Retornar `True` se válidas, `False` caso contrário

- [ ] Implementar `get_payment_status()`
  - [ ] Fazer requisição à API para consultar status
  - [ ] Processar resposta usando `process_webhook()`
  - [ ] Retornar dict no formato padronizado
  - [ ] Tratar erros e retornar `None` em caso de falha

- [ ] Implementar `get_webhook_url()`
  - [ ] Retornar URL completa do webhook
  - [ ] Formato: `{WEBHOOK_URL}/webhook/payment/{gateway_type}`

- [ ] Implementar `get_gateway_name()`
  - [ ] Retornar nome amigável do gateway (ex: 'NovoGateway')

- [ ] Implementar `get_gateway_type()`
  - [ ] Retornar tipo do gateway (ex: 'novogateway')

### 10.3 Implementar Métodos Opcionais

- [ ] Implementar `extract_producer_hash()` (se suportar multi-tenancy)
  - [ ] Extrair producer_hash do webhook
  - [ ] Retornar hash ou `None` se não suportado

### 10.4 Registrar no GatewayFactory

- [ ] Importar classe do gateway em `gateway_factory.py`
- [ ] Adicionar ao `_gateway_classes`:
  ```python
  'novogateway': NovoGateway,
  ```
- [ ] Implementar lógica de criação no `create_gateway()`:
  ```python
  elif gateway_type == 'novogateway':
      # Validar credenciais obrigatórias
      # Criar instância do gateway
      # Retornar gateway
  ```

### 10.5 Atualizar Modelo de Dados (se necessário)

- [ ] Adicionar colunas no modelo `Gateway` (se necessário)
- [ ] Criar migration para adicionar colunas no banco
- [ ] Adicionar propriedades com criptografia (se necessário)
- [ ] Atualizar `bot_manager.py` para passar credenciais

### 10.6 Atualizar BotManager

- [ ] Adicionar validações específicas (se necessário)
- [ ] Atualizar `credentials` dict para incluir credenciais do novo gateway
- [ ] Testar criação de pagamento

### 10.7 Atualizar Middleware (se necessário)

- [ ] Adicionar tipo do gateway em `middleware/gateway_validator.py`
- [ ] Atualizar lista de gateways válidos

### 10.8 Testes

- [ ] Testar `generate_pix()` com valores válidos
- [ ] Testar `generate_pix()` com valores inválidos
- [ ] Testar `process_webhook()` com webhook válido
- [ ] Testar `process_webhook()` com webhook inválido
- [ ] Testar `verify_credentials()` com credenciais válidas
- [ ] Testar `verify_credentials()` com credenciais inválidas
- [ ] Testar `get_payment_status()` com transaction_id válido
- [ ] Testar `get_payment_status()` com transaction_id inválido
- [ ] Testar criação de pagamento end-to-end
- [ ] Testar processamento de webhook end-to-end

### 10.9 Documentação

- [ ] Documentar credenciais obrigatórias
- [ ] Documentar credenciais opcionais
- [ ] Documentar formato de webhook
- [ ] Documentar validações específicas
- [ ] Documentar limites (valor mínimo/máximo, etc)
- [ ] Documentar características especiais (split, multi-tenancy, etc)

---

## 11. Exemplo Completo - Novo Gateway

### 11.1 Arquivo: `gateway_novogateway.py`

```python
"""
Gateway NovoGateway - Implementação Completa
Documentação: https://api.novogateway.com.br/docs
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
    - Autenticação via Bearer Token (API Key)
    - Valores em reais (float)
    - Split payment por percentual
    - Webhook POST para confirmação
    """
    
    def __init__(self, api_key: str, split_user_id: str = None):
        """
        Inicializa gateway NovoGateway
        
        Args:
            api_key: API Key do NovoGateway
            split_user_id: User ID para split (opcional)
        """
        if not api_key or not api_key.strip():
            raise ValueError("api_key é obrigatório para NovoGateway")
        
        self.api_key = api_key.strip()
        self.base_url = os.environ.get('NOVOGATEWAY_API_URL', 'https://api.novogateway.com.br')
        self.split_user_id = split_user_id or os.environ.get('NOVOGATEWAY_SPLIT_USER_ID', None)
        self.split_percentage = 2  # 2% de comissão PADRÃO
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "NovoGateway"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "novogateway"
    
    def get_webhook_url(self) -> str:
        """URL do webhook NovoGateway"""
        webhook_base = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
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
            
            # Preparar dados do cliente
            if not customer_data:
                customer_data = {}
            
            customer_name = customer_data.get('name') or 'Cliente'
            customer_email = customer_data.get('email') or f"user{payment_id}@telegram.user"
            customer_phone = customer_data.get('phone') or '11999999999'
            customer_document = customer_data.get('document') or '00000000000'
            
            # Configurar split (se configurado)
            split_config = None
            if self.split_user_id:
                split_value = round(amount * (self.split_percentage / 100), 2)
                split_config = {
                    'user_id': self.split_user_id,
                    'percentage': self.split_percentage,
                    'value': split_value
                }
                logger.info(f"💰 [{self.get_gateway_name()}] Split configurado: {self.split_percentage}% = R$ {split_value:.2f}")
            
            # Criar payload
            payload = {
                'amount': amount,
                'description': description,
                'payment_id': payment_id,
                'customer': {
                    'name': customer_name,
                    'email': customer_email,
                    'phone': customer_phone,
                    'document': customer_document
                },
                'webhook_url': self.get_webhook_url()
            }
            
            if split_config:
                payload['split'] = split_config
            
            # Headers
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Fazer requisição
            url = f"{self.base_url}/api/v1/pix/create"
            logger.info(f"📤 [{self.get_gateway_name()}] Criando PIX: R$ {amount:.2f}...")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            # Processar resposta
            if response.status_code == 200:
                data = response.json()
                
                # Extrair dados da resposta
                pix_code = data.get('pix_code') or data.get('qr_code') or data.get('emv')
                transaction_id = data.get('transaction_id') or data.get('id') or data.get('uuid')
                qr_code_url = data.get('qr_code_url') or data.get('qr_code_image_url')
                qr_code_base64 = data.get('qr_code_base64')
                
                if not pix_code or not transaction_id:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta inválida - faltando pix_code ou transaction_id")
                    logger.error(f"Resposta: {data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso! ID: {transaction_id}")
                
                # Gerar URL do QR Code se não fornecida
                if not qr_code_url and not qr_code_base64:
                    import urllib.parse
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={urllib.parse.quote(pix_code)}'
                
                return {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url or qr_code_base64 or '',
                    'qr_code_base64': qr_code_base64,
                    'transaction_id': str(transaction_id),
                    'payment_id': payment_id,
                    'gateway_hash': data.get('hash') or data.get('transaction_hash'),
                    'reference': data.get('reference') or payment_id,
                    'expires_at': None
                }
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                logger.error(f"Resposta: {error_data}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook NovoGateway
        
        Campos esperados:
        - transaction_id: ID da transação
        - status: Status (paid, pending, failed)
        - amount: Valor em reais
        - payer_name: Nome do pagador (opcional)
        - payer_document: CPF/CNPJ (opcional)
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook...")
            logger.debug(f"Dados: {data}")
            
            # Extrair dados do webhook
            transaction_id = data.get('transaction_id') or data.get('id') or data.get('uuid')
            status_raw = data.get('status', '').lower()
            amount = float(data.get('amount') or 0)
            
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem transaction_id")
                return None
            
            # Mapear status para formato interno
            status_map = {
                'paid': 'paid',
                'approved': 'paid',
                'confirmed': 'paid',
                'pending': 'pending',
                'waiting': 'pending',
                'processing': 'pending',
                'failed': 'failed',
                'cancelled': 'failed',
                'canceled': 'failed',
                'expired': 'failed',
                'rejected': 'failed'
            }
            
            status = status_map.get(status_raw, 'pending')
            
            # Extrair dados do pagador (opcional)
            payer_name = data.get('payer_name') or data.get('customer_name')
            payer_document = data.get('payer_document') or data.get('payer_cpf') or data.get('payer_cnpj')
            end_to_end_id = data.get('end_to_end_id') or data.get('e2e_id')
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado: {status} | R$ {amount:.2f}")
            
            return {
                'gateway_transaction_id': str(transaction_id),
                'status': status,
                'amount': amount,
                'gateway_hash': data.get('hash') or data.get('transaction_hash'),
                'external_reference': data.get('reference') or data.get('payment_id'),
                'payer_name': payer_name,
                'payer_document': payer_document,
                'end_to_end_id': end_to_end_id
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se credenciais NovoGateway são válidas
        
        Endpoint: GET /api/v1/auth/verify
        """
        try:
            if not self.api_key or len(self.api_key) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key inválida ou vazia")
                return False
            
            # Fazer requisição de verificação
            url = f"{self.base_url}/api/v1/auth/verify"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json'
            }
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Verificando credenciais...")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas")
                return True
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (401)")
                return False
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status inesperado: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento
        
        Endpoint: GET /api/v1/pix/{transaction_id}
        """
        try:
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_id não fornecido")
                return None
            
            url = f"{self.base_url}/api/v1/pix/{transaction_id}"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json'
            }
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando status: {transaction_id}...")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Processar usando a mesma lógica do webhook
                return self.process_webhook(data)
            elif response.status_code == 404:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Transação não encontrada: {transaction_id}")
                return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar: Status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            return None
```

### 11.2 Registrar no GatewayFactory

```python
# gateway_factory.py

from gateway_novogateway import NovoGateway

_gateway_classes: Dict[str, Type[PaymentGateway]] = {
    'syncpay': SyncPayGateway,
    'pushynpay': PushynGateway,
    'paradise': ParadisePaymentGateway,
    'wiinpay': WiinPayGateway,
    'atomopay': AtomPayGateway,
    'novogateway': NovoGateway,  # ✅ NOVO GATEWAY
}

# No método create_gateway():
elif gateway_type == 'novogateway':
    # NovoGateway requer: api_key
    api_key = credentials.get('api_key')
    split_user_id = credentials.get('split_user_id', '')
    
    if not api_key:
        logger.error(f"❌ [Factory] NovoGateway requer api_key")
        return None
    
    gateway = gateway_class(
        api_key=api_key,
        split_user_id=split_user_id
    )
```

### 11.3 Atualizar Middleware

```python
# middleware/gateway_validator.py

valid_types = ['syncpay', 'pushynpay', 'paradise', 'wiinpay', 'atomopay', 'novogateway']
```

### 11.4 Atualizar BotManager (se necessário)

```python
# bot_manager.py

# Adicionar validações específicas (se necessário)
if gateway.gateway_type == 'novogateway' and amount < 1.0:
    logger.error(f"❌ NOVOGATEWAY: Valor mínimo R$ 1,00 | Produto: R$ {amount:.2f}")
    return None

# Adicionar credenciais (se necessário)
credentials = {
    # ... outras credenciais ...
    'split_user_id': gateway.split_user_id,  # Se necessário
}
```

### 11.5 Atualizar Webhook Handler (se necessário)

```python
# app.py

elif gateway_type == 'novogateway':
    dummy_credentials = {'api_key': 'dummy'}
```

---

## 12. Conclusão

Este documento fornece uma visão completa da arquitetura de gateways do sistema, incluindo:

- ✅ Interface obrigatória (`PaymentGateway`)
- ✅ Factory Pattern (`GatewayFactory`)
- ✅ Adapter Pattern (`GatewayAdapter`)
- ✅ Modelo de dados (`Gateway`)
- ✅ Fluxos de criação e processamento de webhook
- ✅ Análise detalhada dos gateways existentes
- ✅ Checklist de implementação
- ✅ Exemplo completo de novo gateway

**Próximos Passos**:
1. Revisar documentação da API do novo gateway
2. Implementar gateway seguindo este documento
3. Testar implementação
4. Documentar características específicas
5. Deploy e monitoramento

---

**Última atualização**: 2024-11-12
**Versão**: 1.0
**Autor**: Sistema de Requisitos - Gateways

