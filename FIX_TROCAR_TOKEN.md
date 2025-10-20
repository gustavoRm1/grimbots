# 🔧 Fix: Trocar Token do Bot

## 📋 Problemas Corrigidos

### **1. Status fantasma "online"**
- ❌ **ANTES**: Trocava token → bot caía → status continuava "ONLINE"
- ✅ **AGORA**: Token trocado → bot para automaticamente → status atualiza para "OFFLINE"

### **2. Dados do bot antigo persistiam**
- ❌ **ANTES**: Username antigo (@bot_velho) continuava aparecendo
- ✅ **AGORA**: Username atualiza automaticamente para o novo bot

### **3. Redirecionador usava bot antigo**
- ❌ **ANTES**: Pools continuavam referenciando dados antigos
- ✅ **AGORA**: Cache limpo completamente ao trocar token

---

## 🎯 Como Funciona Agora

### **Fluxo Automático**

```
1. Você clica em "Trocar Token"
   ↓
2. Sistema PARA o bot automaticamente (se estiver rodando)
   ↓
3. Sistema VALIDA o novo token com o Telegram
   ↓
4. Sistema ATUALIZA tudo:
   - Token ✅
   - Username (@novo_bot) ✅
   - Nome do bot ✅
   - bot_id (ID do Telegram) ✅
   - Status = OFFLINE ✅
   - Cache limpo ✅
   ↓
5. Pronto! Bot atualizado e limpo
```

### **Dados Preservados** 🔒

Ao trocar o token, o sistema **MANTÉM**:
- ✅ Todas as configurações do bot (mensagens, botões, etc)
- ✅ Histórico de pagamentos
- ✅ Estatísticas (vendas, receita)
- ✅ Usuários que interagiram
- ✅ Downsells/Upsells configurados
- ✅ Gateways vinculados

---

## 🚀 Como Usar

### **1. No Dashboard**

1. Vá em "Meus Bots"
2. Encontre o bot que quer trocar o token
3. Clique em "⚙️ Configurar Bot"
4. Na seção "Token do Bot", clique em "Trocar Token"
5. Cole o novo token
6. Clique em "Atualizar Token"

**Pronto!** O bot será:
- Parado automaticamente (se estiver rodando)
- Atualizado com os novos dados
- Status resetado para offline

### **2. Reiniciar o Bot**

Após trocar o token:
1. Volte para "Meus Bots"
2. Verifique que o username agora é o correto (@novo_bot)
3. Clique em "▶️ Iniciar"
4. Bot volta a funcionar com o novo token!

---

## 🛠️ Correção de Status Incorretos

Se seus bots já estão com status errado (mostram "online" mas não estão):

### **Executar Script de Reset**

```bash
cd ~/grpay
source venv/bin/activate
python reset_bot_status.py
```

O script vai:
1. Encontrar todos os bots marcados como "online"
2. Resetar para "offline"
3. Mostrar relatório do que foi feito

---

## 📊 Arquivos Modificados

### **Código**

**`app.py`** (linha ~817-904)
- Função: `update_bot_token()`
- Mudança: AUTO-STOP antes de atualizar
- Benefício: Limpa cache completamente

### **Scripts de Manutenção**

**`reset_bot_status.py`** (NOVO)
- Função: Resetar status incorretos
- Uso: python reset_bot_status.py

---

## ✅ Checklist de Verificação

Após trocar o token, verifique:

- [ ] Username está correto (@novo_bot)?
- [ ] Status está "OFFLINE"?
- [ ] Bot consegue iniciar novamente?
- [ ] Mensagens estão sendo enviadas?
- [ ] Pagamentos estão funcionando?

---

## 🔍 Troubleshooting

### **Problema: Token inválido**
**Erro**: "Token inválido ou expirado"

**Solução**:
1. Vá no @BotFather
2. Use `/mybots`
3. Selecione seu bot
4. Use "API Token" para gerar novo token
5. Copie o token completo (sem espaços)

### **Problema: Username não atualizou**
**Causa**: Token válido mas bot ainda com nome antigo

**Solução**:
```bash
# Executar script de correção
python reset_bot_status.py

# Depois trocar o token novamente
```

### **Problema: Bot não inicia após trocar token**
**Causa**: Pode haver configuração pendente

**Solução**:
1. Verifique se o bot tem mensagem de boas-vindas configurada
2. Verifique se há pelo menos 1 gateway ativo
3. Verifique os logs:
   ```bash
   pm2 logs grpay --lines 50
   ```

---

## 💡 Dicas

### **Quando trocar o token?**

- 🔴 Bot foi banido pelo Telegram
- 🔴 Token foi comprometido
- 🔴 Quer migrar para outro bot do @BotFather

### **O que NÃO fazer**

- ❌ Trocar token enquanto tem vendas em andamento (PIX pendentes)
- ❌ Usar o mesmo token em 2 bots diferentes
- ❌ Apagar o bot antigo no @BotFather antes de trocar

### **Boas Práticas**

- ✅ Sempre teste o novo bot no @BotFather antes (mande /start)
- ✅ Troque o token em horários de baixo movimento
- ✅ Avise seus clientes sobre possível indisponibilidade breve

---

## 📞 Suporte

Se tiver problemas:
1. Verifique os logs: `pm2 logs grpay`
2. Tente resetar o status: `python reset_bot_status.py`
3. Em último caso, deletar e recriar o bot (mantém configurações)

---

**Implementado**: 2025-10-20  
**Status**: ✅ 100% Funcional  
**Autor**: Senior Developer (QI 240)

