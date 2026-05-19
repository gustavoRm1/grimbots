# 📚 Documentação Completa - Sistema Multi-Gateway

## 🎯 Visão Geral

Este conjunto de documentos fornece uma visão completa e detalhada do sistema multi-gateway, incluindo:
- Arquitetura do sistema
- Padrões de design utilizados
- Interface obrigatória (PaymentGateway)
- Gateway Factory e Adapter
- Gateways existentes (análise detalhada)
- Como implementar novos gateways
- Exemplos práticos e casos de uso

---

## 📖 Documentos Disponíveis

### 1. REQUISITOS_GATEWAYS.md
**Documentação completa de requisitos**

Contém:
- Visão geral da arquitetura
- Padrões de design utilizados
- Interface obrigatória (PaymentGateway)
- Gateway Factory e Adapter
- Modelo de dados (Gateway)
- Fluxos de criação de pagamento e processamento de webhook
- Gateways existentes (análise detalhada)
- Checklist de implementação
- Exemplo completo de novo gateway

**Quando usar**: Para entender completamente a arquitetura e implementar novos gateways.

---

### 2. GUIA_RAPIDO_GATEWAYS.md
**Guia rápido de implementação**

Contém:
- Quick Start (passos básicos)
- Checklist mínimo
- Campos obrigatórios
- Padrões de retorno
- Mapeamento de status
- Dicas importantes
- Exemplo completo mínimo

**Quando usar**: Para implementar um novo gateway rapidamente (referência rápida).

---

### 3. RESUMO_EXECUTIVO_GATEWAYS.md
**Resumo executivo**

Contém:
- Visão geral do sistema
- Arquitetura visual
- Gateways disponíveis (comparação)
- Fluxos de criação e processamento
- Padrões de retorno
- Multi-tenancy
- Segurança
- Como adicionar novo gateway

**Quando usar**: Para ter uma visão geral do sistema (overview).

---

### 4. MAPEAMENTO_COMPLETO_GATEWAYS.md
**Mapeamento completo e visual**

Contém:
- Arquitetura visual detalhada
- Fluxos de dados (sequência detalhada)
- Estrutura de arquivos
- Tabela de comparação de gateways
- Padrões de implementação
- Casos de uso práticos
- Estatísticas e monitoramento
- Segurança

**Quando usar**: Para entender os fluxos de dados e padrões de implementação.

---

## 🚀 Quick Start

### Para Implementar um Novo Gateway:

1. **Leia o Guia Rápido**: `GUIA_RAPIDO_GATEWAYS.md`
2. **Crie o arquivo do gateway**: `gateway_novogateway.py`
3. **Implemente a interface**: `PaymentGateway`
4. **Registre no Factory**: `gateway_factory.py`
5. **Teste**: Crie pagamento e processe webhook
6. **Documente**: Características específicas do gateway

### Para Entender a Arquitetura:

1. **Leia o Resumo Executivo**: `RESUMO_EXECUTIVO_GATEWAYS.md`
2. **Leia o Mapeamento Completo**: `MAPEAMENTO_COMPLETO_GATEWAYS.md`
3. **Leia os Requisitos Completos**: `REQUISITOS_GATEWAYS.md`

---

## 📊 Gateways Disponíveis

### 1. SyncPay
- **Autenticação**: Bearer Token (client_id + client_secret)
- **Valores**: Reais (float)
- **Split**: Percentual (1-100%)
- **Webhook**: POST com dados em `data` wrapper

### 2. PushynPay
- **Autenticação**: Bearer Token (API Key)
- **Valores**: Centavos (int)
- **Split**: Valor fixo (máximo 50%)
- **Webhook**: POST com status direto

### 3. Paradise
- **Autenticação**: X-API-Key (Secret Key)
- **Valores**: Centavos (int)
- **Split**: Valor fixo (via store_id)
- **Webhook**: POST com status direto

### 4. WiinPay
- **Autenticação**: api_key no body
- **Valores**: Reais (float)
- **Split**: Percentual OU valor fixo
- **Webhook**: POST com status direto
- **Valor mínimo**: R$ 3,00

### 5. Átomo Pay
- **Autenticação**: api_token como query parameter
- **Valores**: Centavos (int)
- **Multi-tenancy**: Suporta producer_hash
- **Webhook**: POST com dados em múltiplos formatos

---

## 🏗️ Arquitetura

### Componentes Principais

```
BotManager
    ↓
GatewayFactory
    ↓
GatewayAdapter
    ↓
PaymentGateway (Interface)
    ↓
Gateways Concretos (SyncPay, PushynPay, Paradise, WiinPay, Átomo Pay)
```

### Padrões de Design

- **Strategy Pattern**: Interface `PaymentGateway` define o contrato
- **Factory Pattern**: `GatewayFactory` cria instâncias de gateways
- **Adapter Pattern**: `GatewayAdapter` normaliza dados entre gateways
- **Template Method Pattern**: Métodos abstratos definidos na interface

---

## 🔑 Interface Obrigatória

Todos os gateways DEVEM implementar a interface `PaymentGateway`:

```python
class PaymentGateway(ABC):
    @abstractmethod
    def generate_pix(self, amount: float, description: str, payment_id: str, customer_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Gera um pagamento PIX no gateway"""
        pass
    
    @abstractmethod
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processa webhook recebido do gateway"""
        pass
    
    @abstractmethod
    def verify_credentials(self) -> bool:
        """Verifica se as credenciais do gateway são válidas"""
        pass
    
    @abstractmethod
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Consulta status de um pagamento no gateway"""
        pass
    
    @abstractmethod
    def get_webhook_url(self) -> str:
        """Retorna URL do webhook para este gateway"""
        pass
    
    @abstractmethod
    def get_gateway_name(self) -> str:
        """Retorna nome identificador do gateway"""
        pass
    
    @abstractmethod
    def get_gateway_type(self) -> str:
        """Retorna tipo do gateway (usado para roteamento)"""
        pass
```

---

## 📋 Checklist de Implementação

### Passos Básicos:

- [ ] Criar arquivo `gateway_novogateway.py`
- [ ] Implementar interface `PaymentGateway`
- [ ] Implementar `generate_pix()` com retorno padronizado
- [ ] Implementar `process_webhook()` com retorno padronizado
- [ ] Implementar `verify_credentials()`
- [ ] Implementar `get_payment_status()`
- [ ] Registrar no `GatewayFactory`
- [ ] Adicionar ao middleware
- [ ] Testar criação de pagamento
- [ ] Testar processamento de webhook

### Campos Obrigatórios:

#### `generate_pix()` DEVE retornar:
- ✅ `pix_code`: Código PIX copia e cola
- ✅ `qr_code_url`: URL da imagem QR Code ou base64
- ✅ `transaction_id`: ID da transação no gateway
- ✅ `payment_id`: ID do pagamento no sistema

#### `process_webhook()` DEVE retornar:
- ✅ `gateway_transaction_id`: ID da transação no gateway
- ✅ `status`: Status do pagamento ('pending', 'paid', 'failed')
- ✅ `amount`: Valor em reais

---

## 🔍 Padrões de Retorno

### `generate_pix()` - Formato Padronizado:
```python
{
    'pix_code': str,              # OBRIGATÓRIO
    'qr_code_url': str,           # OBRIGATÓRIO
    'transaction_id': str,        # OBRIGATÓRIO
    'payment_id': str,            # OBRIGATÓRIO
    'gateway_hash': str,          # RECOMENDADO (para webhook matching)
    'reference': str,             # RECOMENDADO (para webhook matching)
    'producer_hash': str,         # OPCIONAL (multi-tenancy)
    'qr_code_base64': str,        # OPCIONAL
    'expires_at': datetime        # OPCIONAL
}
```

### `process_webhook()` - Formato Padronizado:
```python
{
    'gateway_transaction_id': str,  # OBRIGATÓRIO
    'status': str,                  # OBRIGATÓRIO ('pending', 'paid', 'failed')
    'amount': float,                # OBRIGATÓRIO
    'gateway_hash': str,            # RECOMENDADO (para webhook matching)
    'external_reference': str,      # RECOMENDADO (para webhook matching)
    'producer_hash': str,           # OPCIONAL (multi-tenancy)
    'payer_name': str,              # OPCIONAL
    'payer_document': str,          # OPCIONAL
    'end_to_end_id': str            # OPCIONAL
}
```

---

## 🔄 Fluxos

### Criação de Pagamento:
```
1. BotManager._generate_pix_payment()
   ↓
2. Busca Gateway no banco
   ↓
3. GatewayFactory.create_gateway(gateway_type, credentials)
   ↓
4. GatewayAdapter(gateway) - envolve o gateway
   ↓
5. gateway.generate_pix(amount, description, payment_id, customer_data)
   ↓
6. Retorna dict normalizado
   ↓
7. BotManager salva Payment no banco
```

### Processamento de Webhook:
```
1. app.py: payment_webhook(gateway_type)
   ↓
2. GatewayFactory.create_gateway(gateway_type, dummy_credentials)
   ↓
3. gateway.process_webhook(data)
   ↓
4. Retorna dict normalizado
   ↓
5. Busca Payment no banco (por múltiplas chaves)
   ↓
6. Atualiza status e processa entregável
```

---

## 🔐 Segurança

### Criptografia de Credenciais

Credenciais sensíveis são criptografadas automaticamente no modelo `Gateway`:

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

### Validação de Webhooks

- ✅ Rate limiting: 500 webhooks/minuto
- ✅ CSRF exempt: Webhooks externos não enviam CSRF token
- ✅ Validação de gateway_type: Apenas gateways válidos
- ✅ Logging: Todos os webhooks são registrados

---

## 📊 Estatísticas

### Modelo `Gateway`:
- `total_transactions`: Total de transações
- `successful_transactions`: Transações bem-sucedidas
- `is_active`: Gateway ativo
- `is_verified`: Gateway verificado
- `last_error`: Último erro (se houver)

### Atualização de Estatísticas:
```python
# No webhook, quando status vira 'paid':
payment.bot.total_sales += 1
payment.bot.total_revenue += payment.amount
payment.bot.owner.total_sales += 1
payment.bot.owner.total_revenue += payment.amount
gateway.total_transactions += 1
gateway.successful_transactions += 1
```

---

## 🎯 Próximos Passos

1. **Revisar Documentação**: Ler todos os documentos disponíveis
2. **Entender Arquitetura**: Estudar os componentes principais
3. **Implementar Gateway**: Seguir o checklist de implementação
4. **Testar**: Testar criação de pagamento e processamento de webhook
5. **Documentar**: Documentar características específicas do gateway
6. **Deploy**: Deploy e monitoramento

---

## 📝 Observações Importantes

### 1. Dados Únicos por Transação

Alguns gateways (ex: Paradise, Átomo Pay) requerem dados únicos por transação:
- ✅ Email único (timestamp + hash)
- ✅ CPF único (timestamp + hash)
- ✅ Telefone único (timestamp + hash)
- ✅ Nome único (timestamp + hash)
- ✅ Reference único (timestamp + hash)

### 2. Validações Específicas

Alguns gateways têm validações específicas:
- ✅ WiinPay: Valor mínimo R$ 3,00
- ✅ PushynPay: Valor mínimo R$ 0,50
- ✅ Paradise: Valor mínimo R$ 0,01
- ✅ Átomo Pay: Valor mínimo R$ 0,50

### 3. Split Payment

Alguns gateways suportam split payment:
- ✅ SyncPay: Percentual (1-100%)
- ✅ PushynPay: Valor fixo (máximo 50%)
- ✅ Paradise: Valor fixo (via store_id)
- ✅ WiinPay: Percentual OU valor fixo
- ❌ Átomo Pay: Não suporta split

### 4. Multi-Tenancy

Apenas Átomo Pay suporta multi-tenancy:
- ✅ Extrai producer_hash do webhook
- ✅ Salva producer_hash no Gateway
- ✅ Filtra por producer_hash no webhook

---

## 📚 Referências

### Arquivos de Código:
- `gateway_interface.py`: Interface obrigatória
- `gateway_factory.py`: Factory de gateways
- `gateway_adapter.py`: Adapter de normalização
- `gateway_syncpay.py`: Gateway SyncPay
- `gateway_pushyn.py`: Gateway PushynPay
- `gateway_paradise.py`: Gateway Paradise
- `gateway_wiinpay.py`: Gateway WiinPay
- `gateway_atomopay.py`: Gateway Átomo Pay
- `bot_manager.py`: Gerencia criação de pagamentos
- `app.py`: Rotas e webhooks
- `models.py`: Modelo Gateway
- `middleware/gateway_validator.py`: Validação de gateways

### Documentos:
- `REQUISITOS_GATEWAYS.md`: Documentação completa de requisitos
- `GUIA_RAPIDO_GATEWAYS.md`: Guia rápido de implementação
- `RESUMO_EXECUTIVO_GATEWAYS.md`: Resumo executivo
- `MAPEAMENTO_COMPLETO_GATEWAYS.md`: Mapeamento completo e visual

---

## 🆘 Suporte

### Dúvidas Frequentes:

1. **Como adicionar um novo gateway?**
   - Leia `GUIA_RAPIDO_GATEWAYS.md` para passos básicos
   - Leia `REQUISITOS_GATEWAYS.md` para documentação completa

2. **Como funciona o GatewayAdapter?**
   - Leia `REQUISITOS_GATEWAYS.md` seção "Gateway Adapter"
   - Leia `gateway_adapter.py` para código

3. **Como funciona o multi-tenancy?**
   - Leia `RESUMO_EXECUTIVO_GATEWAYS.md` seção "Multi-Tenancy"
   - Leia `gateway_atomopay.py` para exemplo

4. **Como testar um gateway?**
   - Leia `GUIA_RAPIDO_GATEWAYS.md` seção "Testes"
   - Leia `REQUISITOS_GATEWAYS.md` seção "Checklist de Implementação"

---

## 📄 Licença

Este documento é parte do sistema de gerenciamento de bots Telegram.

---

**Última atualização**: 2024-11-12
**Versão**: 1.0
**Autor**: Sistema de Requisitos - Gateways

