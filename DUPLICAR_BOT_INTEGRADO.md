# ✅ BOTÃO DUPLICAR BOT INTEGRADO NO DASHBOARD

## 🎯 **O QUE FOI FEITO:**

### **1. Botão "Duplicar" (Linha 433-436):**
```html
<button @click="openDuplicateBotModal(bot)" 
        class="flex-1 inline-flex justify-center items-center px-3 py-2 border text-xs font-semibold rounded-lg transition-all hover:bg-yellow-500 hover:bg-opacity-10" 
        style="border-color: var(--brand-gold-500); color: var(--brand-gold-500);">
    <i class="fas fa-clone mr-1"></i>
    Duplicar
</button>
```

**Localização:** Card de bot → Linha 3 → Entre "Iniciar/Parar" e "Deletar"

**Visual:**
- ✅ Borda dourada
- ✅ Texto dourado
- ✅ Ícone `fa-clone`
- ✅ Texto "Duplicar" visível
- ✅ Hover: Background dourado com opacidade

---

### **2. JavaScript Criado:**

#### **Função `openDuplicateBotModal(bot)`:**
```javascript
openDuplicateBotModal(bot) {
    this.botToDuplicate = bot;
    this.duplicateBotToken = '';
    this.duplicateBotName = '';
    this.showDuplicateBotModal = true;
}
```

**Ação:** Abre o modal e carrega os dados do bot a duplicar

---

#### **Função `duplicateBot()`:**
```javascript
async duplicateBot() {
    if (!this.duplicateBotToken.trim()) {
        alert('Digite o token do novo bot');
        return;
    }
    
    if (!confirm(`Duplicar o bot "${this.botToDuplicate.name}"?\n\nTodas as configurações serão copiadas.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/bots/${this.botToDuplicate.id}/duplicate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token: this.duplicateBotToken.trim(),
                name: this.duplicateBotName.trim()
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            this.showDuplicateBotModal = false;
            this.showNotification('✅ Bot duplicado com sucesso!');
            await this.refreshStats();
        } else {
            alert('Erro: ' + (data.error || 'Erro ao duplicar bot'));
        }
    } catch (error) {
        alert('Erro ao duplicar bot: ' + error.message);
    }
}
```

**Ação:**
1. Valida token
2. Confirma ação
3. Chama API `POST /api/bots/{id}/duplicate`
4. Fecha modal
5. Atualiza dashboard

---

### **3. Modal de Duplicar (Já existia - Linha 586-700):**

**Campos:**
- ✅ Token do novo bot (obrigatório)
- ✅ Nome do novo bot (opcional - gera automático)

**Preview do que será copiado:**
- ✅ Mensagem de boas-vindas
- ✅ Mídia (vídeo/foto)
- ✅ Botões de produtos
- ✅ Order Bumps configurados
- ✅ Downsells automáticos
- ✅ Link de acesso

---

## 📊 **LAYOUT DOS BOTÕES NO CARD:**

```
┌────────────────────────────────────────────────┐
│ 🤖 Bot Vendas INSS      @vendasinssbot        │
│                                    ● Online    │
├────────────────────────────────────────────────┤
│  Usuários | Vendas | Receita                  │
│    150    |   45   | R$ 1.234,56              │
├────────────────────────────────────────────────┤
│ [📊 Ver Estatísticas Detalhadas]              │ Linha 1
├────────────────────────────────────────────────┤
│ [⚙️ Configurar] [🔑] [📢 Remarketing]         │ Linha 2
├────────────────────────────────────────────────┤
│ [▶️ Iniciar] [📋 Duplicar] [🗑️]               │ Linha 3
└────────────────────────────────────────────────┘
```

---

## 🔧 **BACKEND (JÁ EXISTIA):**

### **API:**
```python
@app.route('/api/bots/<int:bot_id>/duplicate', methods=['POST'])
@login_required
def duplicate_bot(bot_id):
    """
    Duplica um bot com todas as configurações
    
    Body:
        - token: Token do novo bot (obrigatório)
        - name: Nome do novo bot (opcional)
    
    Copia:
        - welcome_message
        - welcome_media_url
        - welcome_media_type
        - main_buttons (com Order Bumps)
        - downsells
        - downsells_enabled
        - access_link
    """
```

**Validações:**
1. ✅ Token obrigatório
2. ✅ Token diferente do original
3. ✅ Token único no sistema
4. ✅ Token válido no Telegram
5. ✅ Atualiza username e bot_id automaticamente

---

## 🎯 **FLUXO COMPLETO:**

### **1. Usuário clica "Duplicar":**
```
Dashboard → Card do Bot → Botão "Duplicar"
↓
Modal abre
```

### **2. Usuário preenche:**
```
Token: 123456789:ABC...
Nome: Bot Vendas FGTS (opcional)
```

### **3. Usuário clica "Duplicar Bot":**
```
Confirmação aparece
↓
Usuário confirma
↓
API POST /api/bots/{id}/duplicate
↓
Novo bot criado com TODAS as configurações
↓
Modal fecha
↓
Dashboard atualiza
↓
Novo bot aparece na lista
```

---

## ✅ **CHECKLIST COMPLETO:**

### **Frontend:**
- [x] Botão "Duplicar" visível
- [x] Borda e texto dourado
- [x] Hover effect
- [x] Modal já existe
- [x] Função `openDuplicateBotModal()`
- [x] Função `duplicateBot()`
- [x] Validação de token
- [x] Confirmação
- [x] Notificação de sucesso
- [x] Refresh automático

### **Backend:**
- [x] API `/api/bots/<id>/duplicate`
- [x] Validação de token
- [x] Cópia de configurações
- [x] Criação de BotConfig
- [x] Retorna bot duplicado

---

## 🚀 **COMANDO PARA SUBIR:**

```bash
cd /root/grimbots
git pull origin main
sudo systemctl restart grimbots
```

---

## 🏆 **RESULTADO FINAL:**

### **Antes:**
```
❌ Botão sem função (não abria modal)
❌ Modal existia mas sem JavaScript
```

### **Depois:**
```
✅ Botão "Duplicar" com texto
✅ Borda dourada (padrão)
✅ Função JavaScript completa
✅ Modal abre corretamente
✅ API integrada
✅ Notificação de sucesso
✅ Dashboard atualiza
```

---

**🎯 DUPLICAR BOT 100% FUNCIONAL NO DASHBOARD! 🏆**

