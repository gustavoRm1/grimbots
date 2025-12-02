# 🔍 ERRO IDENTIFICADO: Importar/Exportar Bot

## ❌ PROBLEMA ENCONTRADO

### **Linha 1803-1808: Conflito no Radio Button**

```html
<input type="radio" 
       :value="bot.id"
       x-model="selectedExportBot"
       @change="selectedExportBot = bot"
       class="w-4 h-4"
       style="accent-color: var(--brand-gold-500);">
```

### **ANÁLISE DO ERRO:**

**Problema 1: Conflito entre `x-model` e `@change`**
- `x-model="selectedExportBot"` está fazendo binding bidirecional
- `:value="bot.id"` define o valor do radio como `bot.id` (número)
- `@change="selectedExportBot = bot"` tenta setar o objeto completo `bot`

**Resultado:**
- O Alpine.js tenta fazer `selectedExportBot = bot.id` (via x-model)
- Mas o `@change` tenta fazer `selectedExportBot = bot` (objeto)
- Isso cria um conflito: `selectedExportBot` fica como `bot.id` (número)
- Quando `exportBot()` tenta acessar `this.selectedExportBot.id`, dá erro porque `selectedExportBot` é um número, não um objeto

**Problema 2: Função `exportBot()` espera objeto**
```javascript
async exportBot() {
    if (!this.selectedExportBot) {  // ✅ OK
        return;
    }
    // ...
    const response = await fetch(`/api/bots/${this.selectedExportBot.id}/export`);
    // ❌ ERRO: selectedExportBot.id é undefined se selectedExportBot for um número
}
```

---

## ✅ SOLUÇÃO

### **Opção 1: Remover `x-model` e usar apenas `@change` (RECOMENDADO)**

```html
<input type="radio" 
       :value="bot.id"
       :checked="selectedExportBot?.id === bot.id"
       @change="selectedExportBot = bot"
       class="w-4 h-4"
       style="accent-color: var(--brand-gold-500);">
```

### **Opção 2: Usar `@click` no label (MAIS SIMPLES)**

```html
<label @click="selectedExportBot = bot" ...>
    <input type="radio" 
           :checked="selectedExportBot?.id === bot.id"
           class="w-4 h-4"
           style="accent-color: var(--brand-gold-500);">
    ...
</label>
```

### **Opção 3: Usar `x-model` com ID e buscar objeto depois**

```html
<input type="radio" 
       :value="bot.id"
       x-model="selectedExportBotId"
       class="w-4 h-4">
```

E na função:
```javascript
async exportBot() {
    const botId = this.selectedExportBotId;
    const bot = this.bots.find(b => b.id === botId);
    if (!bot) return;
    // usar bot.id
}
```

---

## 🎯 CORREÇÃO APLICADA

Vou usar a **Opção 2** (mais simples e direta):

