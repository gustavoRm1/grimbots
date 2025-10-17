# 📡 GUIA RÁPIDO: REMARKETING GERAL

## 🎯 **O QUE É?**

Sistema que permite **enviar uma campanha de remarketing para VÁRIOS BOTS AO MESMO TEMPO**, economizando tempo e padronizando mensagens.

---

## 📍 **ONDE ESTÁ?**

**Dashboard → Seção "Meus Bots" → Botão "Remarketing Geral" (roxo)**

```
┌─────────────────────────────────────────────────┐
│  Meus Bots                                      │
│  3 bot(s) configurado(s)                        │
│                                                 │
│  [📡 Remarketing Geral]  [+ Adicionar Bot]     │
└─────────────────────────────────────────────────┘
```

---

## 🚀 **COMO USAR (5 PASSOS)**

### **1️⃣ Clique em "Remarketing Geral"**
Modal roxo será aberto

### **2️⃣ Selecione os bots**
Marque os checkboxes dos bots que receberão a campanha

```
┌────────────────────────────────────────┐
│ ☑️ Bot INSS (1.250 usuários)          │
│ ☑️ Bot FGTS (890 usuários)            │
│ ☐ Bot SIAPE (450 usuários)            │
└────────────────────────────────────────┘
```

### **3️⃣ Escreva a mensagem**
```
🔥 OFERTA RELÂMPAGO! 🔥

Aproveite 50% OFF nos próximos 30 minutos!

Link: https://t.me/produto
```

### **4️⃣ Configure filtros (opcional)**
- **Dias inativos:** 7 (apenas usuários que não interagem há 7 dias)
- **Excluir compradores:** ☑️ (não enviar para quem já comprou)
- **Mídia:** https://t.me/video (opcional)

### **5️⃣ Enviar**
Clique em "Enviar Remarketing" e confirme

---

## ✅ **RESULTADO ESPERADO**

```
┌──────────────────────────────────────────┐
│  ✅ Remarketing iniciado com sucesso!   │
│                                          │
│  📊 2.140 usuários serão impactados     │
│  🤖 2 bot(s) ativado(s)                 │
└──────────────────────────────────────────┘
```

---

## 🎨 **VISUAL DO BOTÃO**

**Cor:** Roxo claro (`#A78BFA`)
**Ícone:** 📡 Broadcast Tower
**Posição:** Ao lado do "+ Adicionar Bot"

```
┌────────────────────────────────────────────┐
│                                            │
│  [📡 Remarketing Geral]  [➕ Adicionar]   │
│    (roxo claro)            (dourado)       │
└────────────────────────────────────────────┘
```

---

## 🆚 **QUANDO USAR?**

### **Remarketing Geral (Multi-Bot):**
- ✅ Promoções globais (Black Friday, Natal)
- ✅ Avisos importantes para todos os bots
- ✅ Campanhas padronizadas

### **Remarketing Individual:**
- ✅ Mensagens específicas de 1 bot
- ✅ Produtos exclusivos de 1 nicho
- ✅ Testes A/B

---

## 🔒 **SEGURANÇA**

- ✅ Apenas **seus bots** podem ser selecionados
- ✅ Cooldown de **6 horas** entre campanhas
- ✅ **Confirmação obrigatória** antes de enviar

---

## 🎯 **EXEMPLO PRÁTICO**

**Cenário:** Black Friday com 50% OFF em todos os produtos

**Passo a passo:**
1. Clico em "Remarketing Geral"
2. Seleciono **todos os meus 5 bots**
3. Escrevo:
   ```
   🖤 BLACK FRIDAY! 🖤
   50% OFF em TUDO!
   Só até meia-noite! ⏰
   https://comprar.agora
   ```
4. Configuro:
   - Dias inativos: **3** (mais agressivo)
   - Excluir compradores: **NÃO** (quero reativar todos)
5. Clico em "Enviar Remarketing"
6. Confirmo
7. **Resultado:** 12.450 usuários impactados em 5 bots ✅

---

## 📊 **MÉTRICAS**

Após enviar, você verá:
- **Total de usuários:** Soma de todos os bots
- **Bots ativados:** Quantos bots tinham usuários elegíveis

Exemplo:
```
📊 3.890 usuários serão impactados
🤖 4 bot(s) ativado(s)
```

Isso significa:
- **Bot 1:** 1.200 usuários
- **Bot 2:** 950 usuários
- **Bot 3:** 880 usuários
- **Bot 4:** 860 usuários
- **Bot 5:** 0 usuários (ignorado)

---

## ❌ **VALIDAÇÕES**

O sistema impede:
- ❌ Enviar sem selecionar bots
- ❌ Enviar sem mensagem
- ❌ Selecionar bots de outros usuários
- ❌ Enviar para bots sem usuários elegíveis

---

## 🚀 **DEPLOY**

Para ativar na VPS:
```bash
cd /root/grimbots
git pull origin main
sudo systemctl restart grimbots
```

**Ou via Cursor Source Control:**
1. Commit
2. Push
3. VPS: `git pull && sudo systemctl restart grimbots`

---

## 🏆 **BENEFÍCIOS**

1. ⚡ **Velocidade:** 1 clique para múltiplos bots
2. 🎯 **Precisão:** Segmentação avançada
3. 📊 **Métricas:** Visualize o impacto em tempo real
4. 🔒 **Segurança:** Apenas seus bots, com cooldown
5. 🎨 **UX:** Interface intuitiva e profissional

---

**🎯 PRONTO PARA USAR! APROVEITE O REMARKETING GERAL! 📡**

