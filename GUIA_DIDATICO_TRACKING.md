# 📚 Guia Didático: Sistema de Tracking de Conversões

## 🎯 Visão Geral

Este guia explica **passo a passo** como configurar e usar o sistema de tracking de conversões (Purchase) do Meta Pixel.

---

## 📋 Índice

1. [Onde Cadastrar o Pixel do Facebook](#1-onde-cadastrar-o-pixel-do-facebook)
2. [Onde Configurar o Link de Entregável](#2-onde-configurar-o-link-de-entregável)
3. [Como Funciona o Tracking](#3-como-funciona-o-tracking)
4. [Fluxo Completo Passo a Passo](#4-fluxo-completo-passo-a-passo)
5. [Perguntas Frequentes](#5-perguntas-frequentes)

---

## 1. Onde Cadastrar o Pixel do Facebook

### ✅ Passo 1: Acessar Redirecionadores

1. No menu lateral, clique em **"Redirecionadores"**
2. Você verá a lista de seus pools de redirecionamento

### ✅ Passo 2: Editar Pool

1. Clique no botão **"Editar"** no pool que você quer configurar
2. Role até a seção **"Meta Pixel Configuration"**

### ✅ Passo 3: Configurar Meta Pixel

Na seção **"Meta Pixel Configuration"**, você precisa preencher:

1. **Ativar Meta Pixel Tracking** ✅
   - Marque o checkbox para ativar o tracking

2. **Pixel ID**
   - Cole o **Pixel ID** do seu Facebook Ads Manager
   - Exemplo: `123456789012345`

3. **Access Token**
   - Cole o **Access Token** do seu Facebook Ads Manager
   - Exemplo: `EAABsbCS1iHgBO...`

4. **Test Event Code** (opcional)
   - Use apenas para testes no Facebook Events Manager

5. **Eventos a Rastrear**
   - ✅ PageView (sempre ativo)
   - ✅ ViewContent (quando lead inicia conversa)
   - ✅ Purchase (quando lead acessa entregável)

6. **Cloaker** (opcional)
   - Configure se quiser proteger seu tráfego

### ✅ Passo 4: Salvar

Clique em **"Salvar"** para aplicar as configurações.

**📍 Localização:** `Redirecionadores → Editar Pool → Meta Pixel Configuration`

---

## 2. Onde Configurar o Link de Entregável

### ⚠️ IMPORTANTE: Pré-requisitos

**Para usar Meta Pixel, você PRECISA fazer ANTES:**
1. ✅ Criar/Configurar um Pool com Meta Pixel ativado (seção 1 acima)
2. ✅ Associar seu Bot ao Pool com Meta Pixel configurado
3. ✅ Depois configurar o Link de Acesso no Bot

**Se o bot NÃO estiver associado a um pool com Meta Pixel, o banner azul NÃO aparecerá!**

### ✅ Passo 1: Associar Bot ao Pool (Obrigatório para Meta Pixel)

**⚠️ IMPORTANTE:** Para que o Meta Pixel funcione, você **DEVE** associar o bot a um pool com Meta Pixel configurado.

1. Acesse: **Redirecionadores** → **Editar Pool**
2. Vá para: **Bots do Pool**
3. Clique em **Adicionar Bot**
4. Selecione seu bot
5. Clique em **Salvar**

**Sem esta associação, o Meta Pixel NÃO funcionará para este bot!**

### ✅ Passo 3: Configurar Link de Acesso

Na seção **"Link de Acesso"** do bot:

#### 🔵 Se Meta Pixel está ATIVO (bot associado a pool com pixel configurado):

Você verá um **banner azul** informando:
- ✅ Meta Pixel Ativo (Pool: Nome do Pool)
- ✅ O link de entrega será gerado automaticamente quando o pagamento for confirmado
- ✅ Este campo será usado como **redirecionamento final** após o Purchase disparar

**O que você deve fazer:**
- Cole o link para onde o lead será redirecionado **APÓS** acessar o entregável
- Exemplo: `https://t.me/+seugrupo` ou `https://seusite.com/area-membros`

**Como funciona:**
1. Lead paga → Sistema gera link `/delivery/<token>` automaticamente
2. Lead recebe link `/delivery/<token>` no Telegram
3. Lead acessa → Purchase disparado → Redireciona para o link que você configurou aqui

#### ⚪ Se Meta Pixel NÃO está ativo (banner azul NÃO aparece):

Isso significa que:
- Bot **NÃO** está associado a um pool com Meta Pixel configurado
- OU o pool associado não tem Meta Pixel ativado

**O que você deve fazer:**
- Configure o link direto que será enviado ao lead
- Exemplo: `https://t.me/+seugrupo`
- **Importante:** Para usar Meta Pixel, você precisa associar o bot a um pool com Meta Pixel configurado primeiro

### ✅ Passo 4: Mensagens (Opcional)

Configure as mensagens que serão enviadas:
- **Mensagem de Pagamento Aprovado**: Enviada quando pagamento é confirmado
- **Mensagem de Pagamento Pendente**: Enviada quando pagamento está aguardando

**📍 Localização:** `Bots → [Seu Bot] → Aba "Entregável" → Link de Acesso`

---

## 3. Como Funciona o Tracking

### 🔄 Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│ 1. LEAD CLICA NO ANÚNCIO DO FACEBOOK                        │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. REDIRECIONA PARA: /go/{slug}?grim={value}&fbclid={id}    │
│    ✅ Cloaker valida                                          │
│    ✅ PageView disparado (Meta Pixel)                         │
│    ✅ Dados salvos no Redis (tracking_token)                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. LEAD É REDIRECIONADO PARA TELEGRAM                        │
│    ✅ Bot inicia conversa                                     │
│    ✅ ViewContent disparado (se configurado)                  │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. LEAD COMPRA (PIX PAGO)                                    │
│    ✅ Webhook confirma pagamento                              │
│    ✅ Sistema gera delivery_token único                       │
│    ✅ Link /delivery/<token> enviado ao lead                  │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. LEAD RECEBE LINK NO TELEGRAM                              │
│    Link: https://app.grimbots.online/delivery/abc123...      │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. LEAD ACESSA O LINK                                        │
│    ✅ Página /delivery/<token> carrega                        │
│    ✅ Purchase disparado (Meta Pixel)                         │
│    ✅ Matching perfeito com PageView (mesmo event_id)         │
│    ✅ Redireciona para link configurado no bot                │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. LEAD ACESSA PRODUTO/ENTREGÁVEL                            │
│    Link final: https://t.me/+seugrupo (ou o que você configurou)
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Fluxo Completo Passo a Passo

### 📍 Passo 1: Configurar Pool com Meta Pixel

1. Acesse: **Redirecionadores** → **Editar Pool**
2. Role até: **Meta Pixel Configuration**
3. Preencha:
   - ✅ Ativar Meta Pixel Tracking
   - Pixel ID: `123456789012345`
   - Access Token: `EAABsbCS1iHgBO...`
   - ✅ Purchase Event (marcar)
4. Clique em **Salvar**

### 📍 Passo 2: Associar Bot ao Pool

1. Acesse: **Redirecionadores** → **Editar Pool**
2. Vá para: **Bots do Pool**
3. Clique em **Adicionar Bot**
4. Selecione seu bot
5. Clique em **Salvar**

### 📍 Passo 3: Configurar Link de Entregável no Bot

1. Acesse: **Bots** → **[Seu Bot]**
2. Vá para aba: **Entregável**
3. No campo **Link de Acesso**, cole:
   - `https://t.me/+seugrupo` (seu grupo/canal)
   - OU `https://seusite.com/area-membros` (sua área de membros)
4. Clique em **Salvar**

### 📍 Passo 4: Usar no Facebook Ads

1. No Facebook Ads Manager, configure sua campanha
2. Na **URL de Destino**, coloque:
   ```
   https://app.grimbots.online/go/{slug}
   ```
   (Substitua `{slug}` pelo slug do seu pool, ex: `red1`)

3. Nos **Parâmetros de URL**, coloque:
   ```
   grim={seu_valor_grim}&utm_source=FB&utm_campaign={{campaign.name}}|{{campaign.id}}&utm_medium={{adset.name}}|{{adset.id}}&utm_content={{ad.name}}|{{ad.id}}&utm_term={{placement}}
   ```

### 📍 Passo 5: O Que Acontece Quando Lead Compra

1. **Lead paga PIX** → Webhook confirma pagamento
2. **Sistema gera link único**: `/delivery/abc123def456...`
3. **Link enviado ao lead** via Telegram
4. **Lead clica no link** → Página carrega
5. **Purchase disparado** automaticamente (Meta Pixel)
6. **Lead redirecionado** para o link que você configurou no bot

---

## 5. Perguntas Frequentes

### ❓ Onde eu cadastro o Pixel ID?

**Resposta:** 
- Acesse: **Redirecionadores** → **Editar Pool** → **Meta Pixel Configuration**
- Cole o Pixel ID e Access Token do Facebook Ads Manager

### ❓ Onde eu coloco o link do meu entregável?

**Resposta:**
- Acesse: **Bots** → **[Seu Bot]** → **Aba "Entregável"** → **Link de Acesso**
- Cole o link (ex: `https://t.me/+seugrupo`)

**Importante:** Se Meta Pixel está ativo, este link será usado como **redirecionamento final** após o Purchase disparar.

### ❓ Como o Purchase é disparado?

**Resposta:**
- Purchase **NÃO** é disparado quando o pagamento é confirmado
- Purchase **É** disparado quando o lead **acessa o link de entrega** (`/delivery/<token>`)
- Isso garante que Purchase = conversão REAL (lead acessou produto)

### ❓ O que acontece quando lead acessa `/delivery/<token>`?

**Resposta:**
1. Sistema valida o token
2. Busca dados do tracking no Redis (fbclid, cookies, etc.)
3. Dispara Purchase com matching perfeito (mesmo `event_id` do PageView)
4. Redireciona para o link configurado no bot

### ❓ Preciso fazer algo na página de entregável?

**Resposta:**
**NÃO!** A página de entregável é gerada automaticamente pelo sistema. Você não precisa criar ou configurar nada.

O sistema:
- ✅ Gera o link `/delivery/<token>` automaticamente
- ✅ Cria a página HTML automaticamente
- ✅ Dispara Purchase automaticamente
- ✅ Redireciona automaticamente

Você só precisa:
- ✅ Configurar o Pixel no Pool
- ✅ Configurar o link final no Bot

### ❓ Como sei se está funcionando?

**Resposta:**
1. **Facebook Events Manager:**
   - Verifique se PageView aparece quando lead clica no anúncio
   - Verifique se Purchase aparece quando lead acessa entregável
   - Verifique se eventos têm mesmo `event_id` (matching perfeito)

2. **Logs do Sistema:**
   - Procure por: `✅ Delivery - Renderizando página`
   - Procure por: `✅ Purchase marcado como enviado`

### ❓ E se o lead não acessar o link de entrega?

**Resposta:**
- Purchase **NÃO** será disparado (isso é correto!)
- Purchase só dispara quando lead realmente acessa o produto
- Isso garante tracking preciso: Purchase = conversão REAL

### ❓ Posso usar sem Meta Pixel?

**Resposta:**
**SIM!** Se você não configurar Meta Pixel:
- O sistema funciona normalmente
- Link de entregável é enviado diretamente (sem página intermediária)
- Não há tracking de Purchase

---

## 📊 Resumo Visual

### ✅ Configuração Necessária

```
┌─────────────────────────────────────────┐
│ 1. POOL (Redirecionadores)              │
│    └─ Meta Pixel Configuration          │
│       ├─ Pixel ID                        │
│       ├─ Access Token                    │
│       └─ ✅ Purchase Event               │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 2. BOT (Bots → [Seu Bot])               │
│    └─ Aba "Entregável"                   │
│       └─ Link de Acesso                   │
│          (Link final após Purchase)      │
└─────────────────────────────────────────┘
```

### ✅ Fluxo Automático

```
Lead Paga
    ↓
Sistema Gera: /delivery/<token>
    ↓
Link Enviado ao Lead
    ↓
Lead Acessa Link
    ↓
Purchase Disparado (Automático)
    ↓
Redireciona para Link Configurado
```

---

## 🎯 Checklist de Configuração

Use este checklist para garantir que tudo está configurado:

- [ ] **Pool criado** em Redirecionadores
- [ ] **Meta Pixel configurado** no Pool (Pixel ID + Access Token)
- [ ] **Purchase Event ativado** no Pool
- [ ] **Bot associado** ao Pool
- [ ] **Link de Acesso configurado** no Bot (link final)
- [ ] **Campanha do Facebook** usando URL: `https://app.grimbots.online/go/{slug}`
- [ ] **Parâmetros de URL** configurados no Facebook (grim + UTMs)

---

## 🔍 Verificação Rápida

### ✅ Está funcionando se:

1. **PageView aparece** no Facebook Events Manager quando lead clica no anúncio
2. **Purchase aparece** no Facebook Events Manager quando lead acessa entregável
3. **Eventos têm mesmo `event_id`** (matching perfeito)
4. **Lead é redirecionado** para o link configurado após acessar entregável

### ❌ Problemas comuns:

1. **Purchase não aparece:**
   - Verifique se Purchase Event está ativado no Pool
   - Verifique se Pixel ID e Access Token estão corretos
   - Verifique se lead realmente acessou o link de entrega

2. **Lead não é redirecionado:**
   - Verifique se Link de Acesso está configurado no Bot
   - Verifique se link está válido (teste manualmente)

3. **Matching não funciona:**
   - Verifique se PageView foi disparado (lead clicou no anúncio)
   - Verifique se mesmo pool está sendo usado

---

## 📞 Suporte

Se tiver dúvidas:
1. Verifique este guia novamente
2. Verifique os logs do sistema
3. Verifique o Facebook Events Manager

---

**Última atualização:** 2025-01-18  
**Versão:** 1.0.0

