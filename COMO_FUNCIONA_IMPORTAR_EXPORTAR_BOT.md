# 📖 COMO FUNCIONA: Importar/Exportar Bot

## 🎯 VISÃO GERAL

A funcionalidade **Importar/Exportar Bot** permite que você **copie todas as configurações de um bot** e **aplique em outro bot**, seja na mesma conta ou em outra conta diferente. Isso elimina a necessidade de reconfigurar manualmente tudo novamente.

---

## 📋 FLUXO COMPLETO: EXPORTAR BOT

### **1. ACESSO**
- Clique no botão **"Importar/Exportar Bot"** no dashboard (ao lado de "Adicionar Bot" e "Remarketing Geral")
- O modal abre com duas abas: **"Exportar"** e **"Importar"**

### **2. ABA EXPORTAR**

#### **Passo 1: Selecionar Bot**
- Uma lista de todos os seus bots é exibida em cards
- Clique no bot que deseja exportar
- O bot selecionado fica destacado com borda azul

#### **Passo 2: Exportar**
- Clique em **"Exportar Configurações"**
- O sistema faz uma requisição para: `GET /api/bots/{bot_id}/export`
- O backend busca todas as configurações do bot:
  - Mensagem de boas-vindas (texto, mídia, áudio)
  - Botões principais (com order bumps)
  - Botões de redirecionamento
  - Downsells
  - Upsells
  - Link de acesso
  - Mensagens personalizadas (sucesso, pendente)
  - Fluxo visual (se configurado)
  - Referência ao gateway usado (sem credenciais)
  - Referência à assinatura (sem chat_id/links específicos)
- As configurações são montadas em um JSON estruturado
- O JSON aparece em uma textarea abaixo

#### **Passo 3: Usar o JSON**
Você tem 3 opções:
1. **Copiar JSON**: Clique em "Copiar JSON" → JSON vai para área de transferência
2. **Download JSON**: Clique em "Download" → Arquivo `.json` é baixado
3. **Copiar manualmente**: Selecione e copie o texto da textarea

### **3. O QUE É EXPORTADO**

✅ **SIM, é exportado:**
- Mensagem de boas-vindas completa
- Todos os botões principais (com order bumps)
- Botões de redirecionamento
- Configurações de downsells
- Configurações de upsells
- Link de acesso
- Mensagens personalizadas
- Fluxo visual completo
- Versão do formato de exportação

❌ **NÃO é exportado (por segurança/ambiente):**
- Token do bot
- Credenciais de gateway
- Chat ID do grupo VIP
- Link do grupo VIP
- IDs do banco de dados
- Informações específicas do ambiente

⚠️ **Referências exportadas (precisam ser reconfiguradas):**
- Tipo de gateway usado (mas não as credenciais)
- Configurações de assinatura (mas não chat_id/link)

---

## 📥 FLUXO COMPLETO: IMPORTAR BOT

### **1. ACESSO**
- No mesmo modal, clique na aba **"Importar"**
- Você pode colar um JSON ou fazer upload de um arquivo

### **2. OPÇÃO 1: COLAR JSON**
- Cole o JSON exportado anteriormente na textarea
- O sistema valida **automaticamente em tempo real** (com debounce de 500ms)
- Validações realizadas:
  - ✅ JSON válido (sintaxe correta)
  - ✅ Versão compatível (deve ser 1.0)
  - ✅ Estrutura correta (deve ter campo "config")
  - ✅ Tipos de dados corretos (strings, arrays, objetos)
  - ✅ Tamanhos válidos (welcome_message max 4096 chars)
  - ✅ Formatos válidos (URLs, tipos de mídia)
  - ✅ Referências válidas (flow_start_step_id existe em flow_steps)

### **3. OPÇÃO 2: UPLOAD DE ARQUIVO**
- Clique em "Escolher arquivo" ou arraste um arquivo `.json`
- Validações:
  - ✅ Tamanho máximo: 5MB
  - ✅ Tipo: deve ser arquivo JSON (`.json` ou `application/json`)
- O arquivo é lido e o conteúdo é colado automaticamente na textarea
- A validação é executada imediatamente

### **4. PREVIEW DA IMPORTAÇÃO**
Após validação bem-sucedida, aparece um **preview** mostrando:
- ✅ Nome do bot original
- ✅ Data de exportação
- ✅ Resumo das configurações:
  - Mensagem inicial: ✅ ou ❌
  - Quantidade de botões principais
  - Quantidade de downsells
  - Quantidade de upsells
  - Fluxo visual: ✅ ou ❌
  - Gateway usado
  - Assinatura configurada: ✅ ou ❌

### **5. SELECIONAR DESTINO**
Você escolhe onde aplicar as configurações:

#### **OPÇÃO A: Criar Novo Bot**
- Marque "Criar novo bot"
- Digite o **Token do novo bot** (obrigatório)
  - Formato: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
  - O sistema valida o formato em tempo real
  - Se inválido, mostra erro em vermelho
- Digite o **Nome do novo bot** (opcional)
  - Se não informado, usa o nome do bot exportado

#### **OPÇÃO B: Bot Existente**
- Marque "Bot existente"
- Selecione um bot da lista dropdown
- ⚠️ **ATENÇÃO**: As configurações atuais serão **SUBSTITUÍDAS** completamente!

### **6. CONFIRMAÇÃO**
- Se for **novo bot**: Confirma criação
- Se for **bot existente**: Confirma substituição com aviso claro

### **7. IMPORTAÇÃO**
- Clique em **"Importar"**
- O sistema faz requisição para: `POST /api/bots/import`
- O backend processa:

#### **BACKEND: Validação Prévia (ANTES de criar/modificar qualquer coisa)**
1. ✅ Valida estrutura do JSON
2. ✅ Valida versão (deve ser 1.0)
3. ✅ Valida todos os campos (tipos, tamanhos, formatos)
4. ✅ Valida referências cruzadas (flow_start_step_id)
5. ✅ Valida gateway (se referenciado, verifica se existe na conta)

#### **BACKEND: Criação/Seleção do Bot**
- Se for **novo bot**:
  1. Valida formato do token
  2. Verifica se token não está em uso
  3. Valida token com Telegram API
  4. Cria novo bot no banco
  5. Se algum erro ocorrer, remove o bot criado (rollback)
- Se for **bot existente**:
  1. Verifica se bot existe
  2. Verifica se bot pertence ao usuário

#### **BACKEND: Aplicação das Configurações**
- Cria ou atualiza `BotConfig` no banco
- Aplica campo por campo:
  - `welcome_message`, `welcome_media_url`, `welcome_media_type`
  - `welcome_audio_enabled`, `welcome_audio_url`
  - `main_buttons` (via `set_main_buttons()`)
  - `redirect_buttons` (via `set_redirect_buttons()`)
  - `downsells_enabled`, `downsells` (via `set_downsells()`)
  - `upsells_enabled`, `upsells` (via `set_upsells()`)
  - `access_link`, `success_message`, `pending_message`
  - `flow_enabled`, `flow_steps` (via `set_flow_steps()`), `flow_start_step_id`

#### **BACKEND: Commit e Resposta**
- Se tudo OK: Salva no banco (`db.session.commit()`)
- Se erro: Faz rollback e remove bot criado (se houver)
- Retorna resposta com:
  - ✅ Sucesso
  - Bot ID e nome
  - Warnings (se gateway/assinatura precisarem ser reconfigurados)

### **8. RESULTADO**
- Se sucesso: Página recarrega, mostrando o bot novo ou atualizado
- Se erro: Mostra mensagem de erro específica
- Warnings aparecem no alert (ex: "Gateway 'pushynpay' não encontrado. Configure manualmente")

---

## 🔧 DETALHES TÉCNICOS

### **Estrutura do JSON Exportado**

```json
{
  "version": "1.0",
  "bot_name": "Nome do Bot",
  "exported_at": "2024-01-15T10:30:00",
  "config": {
    "welcome_message": "Olá! Bem-vindo...",
    "welcome_media_url": "https://...",
    "welcome_media_type": "video",
    "welcome_audio_enabled": false,
    "welcome_audio_url": null,
    "main_buttons": [
      {
        "text": "Comprar Agora",
        "price": 97.00,
        "description": "Descrição do produto",
        "order_bump": {
          "enabled": true,
          "message": "Bônus especial!",
          "price": 27.00,
          "description": "Bônus exclusivo"
        }
      }
    ],
    "redirect_buttons": [
      {
        "text": "Saiba Mais",
        "url": "https://..."
      }
    ],
    "downsells_enabled": true,
    "downsells": [
      {
        "delay_minutes": 5,
        "message": "Oferta especial...",
        "media_url": "...",
        "buttons": [...]
      }
    ],
    "upsells_enabled": true,
    "upsells": [
      {
        "trigger_product": "Produto Principal",
        "delay_minutes": 0,
        "message": "Oferta complementar...",
        "price": 47.00,
        "description": "..."
      }
    ],
    "access_link": "https://...",
    "success_message": "Pagamento aprovado!",
    "pending_message": "Aguardando pagamento...",
    "flow_enabled": true,
    "flow_steps": [...],
    "flow_start_step_id": "step_1",
    "gateway_type": "pushynpay",
    "subscription": {
      "enabled": true,
      "duration_value": 30,
      "duration_unit": "days"
    }
  }
}
```

### **Validações no Frontend**

1. **Sintaxe JSON**: `JSON.parse()` - se falhar, mostra erro
2. **Versão**: Deve ser `"1.0"`
3. **Estrutura**: Deve ter campo `config` (objeto)
4. **Tipos de dados**:
   - `welcome_message`: string, max 4096 chars
   - `welcome_media_type`: "video" ou "photo"
   - `main_buttons`: array de objetos, cada um com `text`
   - `flow_steps`: array de objetos, cada um com `id` único
5. **Referências**: `flow_start_step_id` deve existir em `flow_steps`
6. **Formato de token**: Regex `/^\d+:[A-Za-z0-9_-]+$/` e min 20 chars

### **Validações no Backend**

1. **Estrutura básica**: `export_data`, `version`, `config`
2. **Versão**: Deve ser `"1.0"`
3. **Validação completa**: Função `_validate_import_config()` valida:
   - Tipos de todos os campos
   - Tamanhos (strings, arrays)
   - Formatos (URLs, tipos de mídia)
   - Estrutura de arrays aninhados
   - Referências cruzadas
4. **Token (se novo bot)**:
   - Formato válido
   - Não está em uso
   - Válido no Telegram API
5. **Gateway**: Se referenciado, verifica se existe na conta do usuário

### **Segurança**

✅ **Implementado:**
- Validação completa antes de aplicar (evita dados inválidos)
- Rollback automático se erro ocorrer após criar bot
- Sanitização de dados (prevenção XSS)
- Validação de permissões (bot deve pertencer ao usuário)
- Validação de token com Telegram (evita tokens inválidos)

❌ **NÃO exportado (por segurança):**
- Tokens do bot
- Credenciais de gateway (API keys, secrets)
- IDs do banco de dados
- Informações específicas do ambiente

### **Tratamento de Erros**

**Frontend:**
- Validação em tempo real com feedback visual
- Mensagens de erro claras e específicas
- Prevenção de envio de dados inválidos

**Backend:**
- Validação completa antes de qualquer modificação
- Rollback automático em caso de erro
- Mensagens de erro específicas
- Logs detalhados para debug

---

## ⚠️ LIMITAÇÕES E AVISOS

### **O que precisa ser reconfigurado manualmente:**

1. **Gateway de Pagamento**
   - O sistema exporta apenas o **tipo** de gateway (ex: "pushynpay")
   - Você precisa configurar as credenciais manualmente em **Configurações → Gateways**
   - Warnings aparecem se o gateway não estiver configurado

2. **Assinatura (Grupo VIP)**
   - O sistema exporta apenas a **configuração** (duração, remoção automática)
   - Você precisa configurar manualmente:
     - Chat ID do grupo Telegram
     - Link do grupo VIP
   - Isso é intencional (chat_id e link são específicos do ambiente)

3. **Token do Bot**
   - Obviamente, cada bot precisa de um token único
   - Para criar novo bot, você precisa gerar token no @BotFather

---

## 📝 CASOS DE USO

### **Caso 1: Duplicar Bot na Mesma Conta**
1. Exporte o bot original
2. Na aba Importar, cole o JSON
3. Selecione "Criar novo bot"
4. Informe token do novo bot
5. Importe

### **Caso 2: Copiar Configurações para Bot Existente**
1. Exporte o bot de origem
2. Na aba Importar, cole o JSON
3. Selecione "Bot existente"
4. Escolha o bot destino
5. ⚠️ Confirme substituição
6. Importe

### **Caso 3: Transferir Bot para Outra Conta**
1. Na conta origem: Exporte o bot
2. Copie o JSON (ou baixe o arquivo)
3. Faça login na conta destino
4. Na conta destino: Abra Importar/Exportar Bot
5. Cole o JSON ou faça upload do arquivo
6. Crie novo bot com novo token
7. Configure gateway e assinatura manualmente (se necessário)

---

## 🔍 DEBUGGING

### **Se o modal não abrir:**
1. Verifique console do navegador (F12) para erros JavaScript
2. Verifique se `showImportExportModal` está sendo setado para `true`
3. Verifique se o elemento modal existe no DOM
4. Limpe cache do navegador (Ctrl+Shift+R)

### **Se a exportação falhar:**
1. Verifique se o bot tem configurações (`BotConfig` existe)
2. Verifique logs do servidor para erros
3. Verifique permissões do usuário

### **Se a importação falhar:**
1. Verifique mensagem de erro específica
2. Verifique se o JSON está válido (cole no JSONLint)
3. Verifique se a versão é "1.0"
4. Verifique logs do servidor para detalhes

---

## ✅ GARANTIAS DE FUNCIONAMENTO

Após as correções aplicadas, a funcionalidade garante:

1. ✅ **Validação completa** antes de aplicar configurações
2. ✅ **Rollback automático** se erro ocorrer
3. ✅ **Dados sempre válidos** (sem corrupção)
4. ✅ **Segurança** (validação de permissões, sanitização)
5. ✅ **UX clara** (feedback em tempo real, mensagens específicas)
6. ✅ **Robustez** (tratamento de erros, logs detalhados)

---

**Documentação criada em:** 2024-01-15
**Versão:** 1.0
**Status:** Completo e Funcional ✅

