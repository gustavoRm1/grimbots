# 🚀 COMANDOS PARA SUBIR NA VPS - BOT CONFIG V2.0

## ✅ **ALTERAÇÕES FEITAS:**

### **1. Padrão de Botões Dourado:**
- ✅ Todos os botões principais: Dourado (`var(--brand-gold-500)`)
- ✅ Botões de precificação (ativo): Dourado
- ✅ Botões de precificação (inativo): Cinza

### **2. Tipo de Mídia:**
- ✅ Downsells: Radio buttons amarelos (mudado de azul)
- ✅ Todas as abas: Padrão consistente

### **3. Nomenclatura:**
- ✅ "Produtos" → "Botões"

### **4. Remarketing:**
- ✅ Interface completa integrada
- ✅ Cores padronizadas (amarelo)

### **5. Configurações:**
- ✅ Trocar token com aviso crítico
- ✅ Opacidade corrigida

---

## 🖥️ **COMANDOS NA VPS:**

### **Opção 1: Comando Único**
```bash
cd /root/grimbots && sudo systemctl stop grimbots && git pull origin main && sudo systemctl start grimbots && sudo systemctl status grimbots
```

### **Opção 2: Passo a Passo**
```bash
# 1. Ir para pasta
cd /root/grimbots

# 2. Parar serviço
sudo systemctl stop grimbots

# 3. Atualizar código
git pull origin main

# 4. Iniciar serviço
sudo systemctl start grimbots

# 5. Verificar status
sudo systemctl status grimbots
```

---

## ⚠️ **IMPORTANTE - CACHE DO NAVEGADOR:**

Se após subir você ainda ver cores antigas (azul nos botões), faça:

### **No Navegador:**
1. Abrir DevTools (F12)
2. Clicar com botão direito no ícone de recarregar
3. Selecionar **"Limpar cache e recarregar forçado"**

**Ou use:**
- **Chrome/Edge:** `Ctrl + Shift + R`
- **Firefox:** `Ctrl + F5`

---

## 🔍 **VERIFICAR SE APLICOU:**

### **Bot Config deve estar:**
- ✅ Botões principais: Dourado
- ✅ Precificação (ativo): Dourado
- ✅ Precificação (inativo): Cinza
- ✅ Radio buttons mídia: Amarelo (não azul)
- ✅ Badge "ATIVO": Verde visível
- ✅ Aviso trocar token: Vermelho visível

---

## 📦 **ARQUIVOS ALTERADOS:**

- ✅ `templates/bot_config_v2.html` (1597 linhas)
  - CSS atualizado (linhas 171-248)
  - Downsells: Botões de mídia amarelos
  - Remarketing: Interface completa
  - Configurações: Aviso crítico

---

## 🚀 **COMANDO FINAL:**

```bash
cd /root/grimbots && sudo systemctl stop grimbots && git pull origin main && sudo systemctl start grimbots && sudo systemctl status grimbots
```

**Depois limpe o cache do navegador!** (Ctrl + Shift + R)

---

**🏆 PRONTO PARA SUBIR! TUDO DOURADO E PADRONIZADO! 🟡**

