# 🧠 Debate Técnico: Sistema de Condições no Fluxo

**Objetivo:** Criar sistema visual e intuitivo para usuário final configurar condições que determinam o caminho do lead no funil.

---

## 🎯 REQUISITOS DO USUÁRIO FINAL

### O que o usuário quer:
1. **Liberdade total:** Criar fluxos onde o lead toma decisões
2. **Condições visuais:** Configurar condições de forma intuitiva no frontend
3. **Múltiplos caminhos:** Diferentes steps baseados em diferentes condições
4. **Simplicidade:** Não precisa saber programar

### Exemplos de uso:
- **Step de mensagem:** "Digite seu email"
  - Se email válido → Step "Email confirmado"
  - Se email inválido → Step "Email inválido, tente novamente"
  
- **Step de botões:** "Você quer continuar?"
  - Botão "Sim" → Step "Continuar"
  - Botão "Não" → Step "Finalizar"

- **Step de pagamento:**
  - Se pago → Step "Acesso liberado"
  - Se não pago → Step "Lembrete de pagamento"

---

## 💡 PROPOSTA DE SOLUÇÃO

### **OPÇÃO 1: Sistema de Condições por Step (RECOMENDADO)**

Cada step pode ter múltiplas condições, cada uma levando a um step diferente.

#### Estrutura:
```javascript
{
  "id": "step_123",
  "type": "message",
  "config": {
    "message": "Digite seu email:"
  },
  "conditions": [
    {
      "id": "cond_1",
      "type": "text_validation",
      "validation": "email",
      "target_step": "step_email_valid",
      "order": 1
    },
    {
      "id": "cond_2",
      "type": "text_validation",
      "validation": "any",
      "target_step": "step_email_invalid",
      "order": 2,
      "max_attempts": 3
    }
  ]
}
```

#### Interface Visual:
```
┌─────────────────────────────────────┐
│ Step: Digite seu email             │
├─────────────────────────────────────┤
│ Mensagem: "Digite seu email:"      │
│                                     │
│ 📋 Condições:                       │
│ ┌─────────────────────────────────┐ │
│ │ ✅ Se email válido              │ │
│ │    → Ir para: Step "Email OK"   │ │
│ │    [Editar] [Remover]           │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ ⚠️ Se qualquer texto            │ │
│ │    → Ir para: Step "Tente novamente"│
│ │    Máx tentativas: 3            │ │
│ │    [Editar] [Remover]           │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [+ Adicionar Condição]              │
└─────────────────────────────────────┘
```

#### Vantagens:
- ✅ Intuitivo: Cada condição é clara e visual
- ✅ Flexível: Múltiplas condições por step
- ✅ Ordem de avaliação: Condições são avaliadas em ordem
- ✅ Fallback automático: Última condição pode ser "qualquer coisa"

#### Desvantagens:
- ⚠️ Pode ficar complexo com muitas condições
- ⚠️ Precisa de ordem clara de avaliação

---

### **OPÇÃO 2: Sistema de Gatilhos (Mais Avançado)**

Similar ao sistema descrito na análise, mas com interface visual.

#### Estrutura:
```javascript
{
  "id": "step_123",
  "triggers": [
    {
      "type": "user_text",
      "condition": "email_regex",
      "target_step": "step_email_valid"
    },
    {
      "type": "user_text",
      "condition": "any",
      "target_step": "step_email_invalid"
    }
  ]
}
```

#### Vantagens:
- ✅ Mais técnico e poderoso
- ✅ Alinhado com arquitetura EDA

#### Desvantagens:
- ❌ Menos intuitivo para usuário final
- ❌ Terminologia técnica (triggers, conditions)

---

### **OPÇÃO 3: Híbrido - Condições Visuais com Gatilhos (BEST OF BOTH WORLDS)**

Interface visual de "Condições" que gera "Gatilhos" internamente.

#### Estrutura:
```javascript
{
  "id": "step_123",
  "type": "message",
  "config": {
    "message": "Digite seu email:"
  },
  // ✅ Interface visual usa "conditions"
  "conditions": [
    {
      "id": "cond_1",
      "label": "Se email válido",
      "type": "text_validation",
      "validation": "email",
      "target_step": "step_email_valid",
      "order": 1
    }
  ],
  // ✅ Backend converte para "triggers"
  "_triggers": [
    {
      "type": "user_text",
      "condition": "email_regex",
      "target_step": "step_email_valid"
    }
  ]
}
```

#### Vantagens:
- ✅ Interface intuitiva (conditions)
- ✅ Backend poderoso (triggers)
- ✅ Melhor dos dois mundos

---

## 🎨 TIPOS DE CONDIÇÕES PROPOSTOS

### **1. Condição de Texto (para step `message`)**
- **Email válido** → Valida formato de email
- **Telefone válido** → Valida telefone brasileiro
- **CPF válido** → Valida CPF
- **Texto contém** → Verifica se texto contém palavra/frase
- **Texto igual a** → Comparação exata
- **Qualquer texto** → Aceita qualquer resposta (fallback)

### **2. Condição de Botão (para step `buttons`)**
- **Botão específico clicado** → Cada botão leva a step diferente
- **Qualquer botão** → Fallback genérico

### **3. Condição de Pagamento (para step `payment`)**
- **Pagamento confirmado** → Se pago
- **Pagamento pendente** → Se não pago
- **Pagamento expirado** → Se timeout

### **4. Condição de Tempo**
- **Tempo decorrido** → Após X minutos, ir para step

---

## 🚀 IMPLEMENTAÇÃO RECOMENDADA

### **FASE 1: Interface Visual de Condições**

#### No Frontend (`templates/bot_config.html`):

1. **Seção de Condições no Modal de Edição:**
```html
<div class="mb-4 p-4 bg-blue-900 bg-opacity-20 border border-blue-500 rounded-lg">
    <label class="block text-sm font-medium text-blue-300 mb-3">
        <i class="fas fa-code-branch mr-2"></i>Condições (O que acontece após este step?)
    </label>
    
    <div id="conditions-list-${stepId}" class="space-y-2 mb-3">
        <!-- Lista de condições -->
    </div>
    
    <button type="button" 
            onclick="addCondition('${stepId}')"
            class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium">
        <i class="fas fa-plus mr-2"></i>Adicionar Condição
    </button>
</div>
```

2. **Modal de Adicionar/Editar Condição:**
```html
<div class="modal">
    <h3>Nova Condição</h3>
    
    <label>Tipo de Condição:</label>
    <select id="condition-type">
        <option value="text_validation">Validação de Texto</option>
        <option value="button_click">Clique em Botão</option>
        <option value="payment_status">Status de Pagamento</option>
        <option value="time_elapsed">Tempo Decorrido</option>
    </select>
    
    <!-- Campos dinâmicos baseados no tipo -->
    <div id="condition-config">
        <!-- Configuração específica do tipo -->
    </div>
    
    <label>Ir para Step:</label>
    <select id="condition-target-step">
        <!-- Lista de steps disponíveis -->
    </select>
</div>
```

### **FASE 2: Backend - Processamento de Condições**

#### Em `bot_manager.py`:

```python
def _evaluate_conditions(self, step: Dict[str, Any], user_input: str, context: Dict[str, Any]) -> Optional[str]:
    """
    Avalia condições do step e retorna próximo step_id
    
    Args:
        step: Step atual com condições
        user_input: Input do usuário (texto, callback_data, etc.)
        context: Contexto adicional (payment_status, etc.)
    
    Returns:
        step_id do próximo step ou None
    """
    conditions = step.get('conditions', [])
    
    # Ordenar por ordem (order)
    sorted_conditions = sorted(conditions, key=lambda c: c.get('order', 0))
    
    for condition in sorted_conditions:
        condition_type = condition.get('type')
        
        if condition_type == 'text_validation':
            if self._match_text_validation(condition, user_input):
                return condition.get('target_step')
        
        elif condition_type == 'button_click':
            if self._match_button_click(condition, user_input):
                return condition.get('target_step')
        
        elif condition_type == 'payment_status':
            if self._match_payment_status(condition, context):
                return condition.get('target_step')
        
        elif condition_type == 'time_elapsed':
            if self._match_time_elapsed(condition, context):
                return condition.get('target_step')
    
    return None  # Nenhuma condição matchou

def _match_text_validation(self, condition: Dict[str, Any], user_input: str) -> bool:
    """Valida texto do usuário"""
    validation = condition.get('validation')
    
    if validation == 'email':
        import re
        return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', user_input))
    
    elif validation == 'phone':
        import re
        # Telefone brasileiro: (XX) XXXXX-XXXX ou XXXXXXXXXXX
        return bool(re.match(r'^(\+55\s?)?(\(?\d{2}\)?\s?)?\d{4,5}-?\d{4}$', user_input))
    
    elif validation == 'cpf':
        # Validação básica de CPF (11 dígitos)
        import re
        cpf = re.sub(r'\D', '', user_input)
        return len(cpf) == 11
    
    elif validation == 'contains':
        keyword = condition.get('value', '')
        return keyword.lower() in user_input.lower()
    
    elif validation == 'equals':
        value = condition.get('value', '')
        return user_input.strip().lower() == value.lower()
    
    elif validation == 'any':
        return bool(user_input and user_input.strip())
    
    return False
```

---

## 📋 PLANO DE IMPLEMENTAÇÃO

### **ETAPA 1: Frontend - Interface de Condições (2-3 dias)**
1. ✅ Adicionar seção "Condições" no modal de edição de step
2. ✅ Criar modal para adicionar/editar condição
3. ✅ Tipos de condições com campos dinâmicos
4. ✅ Lista visual de condições com ordem
5. ✅ Validação de condições (evitar loops)

### **ETAPA 2: Backend - Engine de Condições (2 dias)**
1. ✅ Função `_evaluate_conditions`
2. ✅ Validações de texto (email, phone, CPF, etc.)
3. ✅ Processamento de botões contextuais
4. ✅ Integração com fluxo existente

### **ETAPA 3: Integração com Fluxo (1 dia)**
1. ✅ Modificar `_execute_flow_recursive` para usar condições
2. ✅ Processar mensagens de texto com condições
3. ✅ Processar callbacks de botões com condições
4. ✅ Testes end-to-end

---

## 🎯 CONCLUSÃO

**Recomendação:** Implementar **OPÇÃO 3 (Híbrido)** com interface visual de "Condições" que é intuitiva para o usuário final, mas internamente converte para sistema de gatilhos poderoso.

**Prioridade:** ALTA - Esta é a funcionalidade que transforma o fluxo de "sequencial" para "condicional", dando liberdade total ao usuário.

**Complexidade:** MÉDIA - Requer mudanças no frontend e backend, mas é bem estruturado.

**Impacto:** ALTO - Permite criar funis complexos e personalizados sem código.

