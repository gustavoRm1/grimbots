# ✅ CORREÇÃO AUTENTICAÇÃO BABYLON - BASIC AUTH

**Data:** 2025-01-27  
**Problema:** Erro 401 Unauthorized ao gerar PIX  
**Causa:** Autenticação incorreta (estava usando Bearer Token, mas Babylon usa Basic Auth)

---

## 🔍 PROBLEMA IDENTIFICADO

O Babylon usa **Basic Authentication**, não Bearer Token:
- **Username:** Secret Key
- **Password:** Company ID
- **Formato:** `Authorization: Basic {base64(Secret Key:Company ID)}`

O código estava usando:
```python
'Authorization': f'Bearer {self.api_key}'
```

---

## ✅ CORREÇÕES IMPLEMENTADAS

### 1. Gateway Babylon (`gateway_babylon.py`)

#### Autenticação Basic Auth
- ✅ Adicionado suporte para `company_id` no construtor
- ✅ Implementada autenticação Basic: `Base64(Secret Key:Company ID)`
- ✅ Validação de ambas as credenciais antes de fazer requisições

**Mudanças:**
```python
# ANTES
def __init__(self, api_key: str, ...):
    self.api_key = api_key

# DEPOIS
def __init__(self, api_key: str, company_id: str = None, ...):
    self.secret_key = api_key  # Secret Key = username
    self.company_id = company_id  # Company ID = password
```

#### Headers de Autenticação
```python
# ANTES
headers = {
    'Authorization': f'Bearer {self.api_key}',
    ...
}

# DEPOIS
import base64
credentials_string = f"{self.secret_key}:{self.company_id}"
credentials_base64 = base64.b64encode(credentials_string.encode('utf-8')).decode('utf-8')

headers = {
    'Authorization': f'Basic {credentials_base64}',
    ...
}
```

#### Validação de Credenciais
- ✅ Verifica presença de Secret Key E Company ID
- ✅ Valida formato básico (tamanho mínimo)
- ✅ Logs detalhados para diagnóstico

### 2. Gateway Factory (`gateway_factory.py`)

#### Criação do Gateway
```python
elif gateway_type == 'babylon':
    api_key = credentials.get('api_key')  # Secret Key
    company_id = credentials.get('company_id') or credentials.get('client_id')
    
    if not api_key:
        logger.error(f"❌ [Factory] Babylon requer api_key (Secret Key)")
        return None
    
    if not company_id:
        logger.error(f"❌ [Factory] Babylon requer company_id (Company ID)")
        return None
    
    gateway = gateway_class(
        api_key=api_key,  # Secret Key
        company_id=company_id,  # Company ID
        ...
    )
```

### 3. Backend - Rota de Criação (`app.py`)

#### Salvamento de Credenciais
```python
elif gateway_type == 'babylon':
    api_key_value = data.get('api_key')  # Secret Key
    company_id_value = data.get('company_id') or data.get('client_id')  # Company ID
    
    if api_key_value:
        gateway.api_key = api_key_value  # Criptografado (Secret Key)
    
    if company_id_value:
        gateway.client_id = company_id_value  # Company ID (não criptografado)
```

#### Montagem de Credenciais
```python
credentials = {
    ...
    'api_key': gateway.api_key,  # Secret Key (descriptografada)
    'company_id': gateway.client_id,  # Company ID (armazenado em client_id)
    ...
}
```

#### Validação
```python
if gateway_type == 'babylon':
    if not credentials.get('api_key'):
        logger.error(f"❌ [Babylon] api_key (Secret Key) não configurado")
        ...
    if not credentials.get('company_id'):
        logger.error(f"❌ [Babylon] company_id (Company ID) não configurado")
        ...
```

### 4. Bot Manager (`bot_manager.py`)

#### Montagem de Credenciais
```python
credentials = {
    ...
    'company_id': gateway.client_id if gateway.gateway_type == 'babylon' else None,
    ...
}
```

#### Validação Específica
```python
elif gateway.gateway_type == 'babylon':
    if not api_key:
        logger.error(f"❌ BABYLON: api_key (Secret Key) ausente")
        return None
    if not gateway.client_id:
        logger.error(f"❌ BABYLON: client_id (Company ID) ausente")
        return None
```

### 5. Modelo Gateway (`models.py`)

#### Método to_dict()
```python
elif self.gateway_type == 'babylon':
    result['api_key'] = self.api_key  # Secret Key (descriptografada)
    result['company_id'] = self.client_id  # Company ID (armazenado em client_id)
```

### 6. Frontend (`templates/settings.html`)

#### Formulário de Criação
- ✅ Campo "Secret Key" (obrigatório)
- ✅ Campo "Company ID" (obrigatório)
- ✅ Instruções atualizadas

#### Formulário de Edição
- ✅ Campo "Secret Key" (obrigatório)
- ✅ Campo "Company ID" (obrigatório - usa `client_id` do backend)
- ✅ Instruções atualizadas

#### Estado JavaScript
```javascript
babylon: { api_key: '', company_id: '' }
```

#### Reset de Formulário
```javascript
} else if (type === 'babylon') {
    this.gateways[type] = { api_key: '', company_id: '' };
}
```

---

## 📋 ESTRUTURA DE ARMAZENAMENTO

### No Banco de Dados

| Campo | Valor | Criptografado | Descrição |
|-------|-------|---------------|-----------|
| `_api_key` | Secret Key | ✅ Sim | Chave secreta (username) |
| `client_id` | Company ID | ❌ Não | ID da empresa (password) |

**Nota:** `client_id` não é criptografado pois não é uma credencial sensível (apenas identifica a conta).

### Nas Requisições

**Para o Gateway:**
- `api_key`: Secret Key (descriptografada)
- `company_id`: Company ID (de `client_id`)

**No Header HTTP:**
```
Authorization: Basic {base64(Secret Key:Company ID)}
```

---

## ✅ VALIDAÇÕES IMPLEMENTADAS

### Backend
1. ✅ Verifica presença de Secret Key
2. ✅ Verifica presença de Company ID
3. ✅ Valida formato básico (tamanho mínimo)

### Frontend
1. ✅ Campos obrigatórios marcados com `*`
2. ✅ Validação HTML5 (`required`)
3. ✅ Instruções claras sobre onde obter credenciais

---

## 🔧 COMO OBTER AS CREDENCIAIS

1. Acesse o painel do gateway Babylon
2. Navegue até **Integrações → Chaves de API**
3. Copie a **Secret Key** (será usada como Secret Key)
4. Copie o **Company ID** (será usado como Company ID)

---

## ✅ RESULTADO

Após essas correções:
- ✅ Autenticação Basic Auth implementada corretamente
- ✅ Ambas as credenciais são coletadas no frontend
- ✅ Ambas as credenciais são validadas antes de usar
- ✅ Headers HTTP corretos são enviados
- ✅ Erro 401 Unauthorized deve ser resolvido

---

**Status:** ✅ Implementação completa  
**Próximo Passo:** Testar geração de PIX com credenciais corretas

