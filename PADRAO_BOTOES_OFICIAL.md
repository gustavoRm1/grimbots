# 🎯 PADRÃO OFICIAL DE BOTÕES - APROVADO

## ✅ **PADRÃO ÚNICO ESTABELECIDO:**

### **CSS OFICIAL:**
```css
/* Botões de Ação - IDÊNTICO ao Dashboard */
.btn-action {
    display: inline-flex;
    align-items: center;
    padding: 0.5rem 1rem;
    border: 1px solid transparent;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: #111827;
    background-image: linear-gradient(to right, var(--brand-gold-500), var(--brand-gold-700));
    cursor: pointer;
    transition: all 0.15s ease;
}

.btn-action:hover {
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.btn-action i {
    margin-right: 0.5rem;
}
```

---

## 🎨 **CORES EXATAS:**

### **Gradiente Dourado:**
```css
background-image: linear-gradient(to right, 
    var(--brand-gold-500),  /* #FFB800 */
    var(--brand-gold-700)   /* #DAA520 */
);
```

### **Texto:**
```css
color: #111827;  /* Cinza escuro (quase preto) */
```

### **Sombra (Hover):**
```css
box-shadow: 
    0 20px 25px -5px rgba(0, 0, 0, 0.1),
    0 10px 10px -5px rgba(0, 0, 0, 0.04);
```

---

## 📋 **USO PADRÃO:**

### **Template HTML:**
```html
<button @click="action()" class="btn-action btn-action-primary">
    <i class="fas fa-icon"></i>
    Texto do Botão
</button>
```

### **Variantes (TODAS IGUAIS):**
```html
<!-- Primary (Ação Principal) -->
<button class="btn-action btn-action-primary">
    <i class="fas fa-save"></i>
    Salvar Configurações
</button>

<!-- Success (Adicionar/Criar) -->
<button class="btn-action btn-action-success">
    <i class="fas fa-plus"></i>
    Adicionar Botão
</button>

<!-- Info (Links/Informação) -->
<button class="btn-action btn-action-info">
    <i class="fas fa-plus"></i>
    Adicionar Link
</button>
```

**⚠️ IMPORTANTE:** Todas as variantes (primary, success, info) usam a MESMA COR DOURADA!

---

## 🚫 **NÃO USAR:**

### **❌ Evitar:**
```css
/* NÃO usar cores diferentes */
background: green;
background: blue;
background: purple;

/* NÃO usar HEX direto de yellow-600/700 */
background: #D97706;  /* Fica laranja! */
background: #B45309;  /* Fica laranja! */

/* NÃO usar gradientes de outras cores */
from-emerald-500
from-trust-500
```

### **✅ SEMPRE usar:**
```css
background-image: linear-gradient(to right, 
    var(--brand-gold-500), 
    var(--brand-gold-700)
);
```

**Motivo:** As variáveis CSS garantem o dourado correto (#FFB800 → #DAA520)

---

## 📊 **APLICAÇÕES ATUAIS:**

| Botão | Localização | Classe | Status |
|-------|-------------|--------|--------|
| **Salvar Configurações** | Header | `btn-action-primary` | ✅ |
| **Adicionar Botão** | Tab Botões | `btn-action-success` | ✅ |
| **Adicionar Link** | Tab Botões | `btn-action-info` | ✅ |
| **Adicionar Primeiro Botão** | Empty State | `btn-action-success` | ✅ |
| **Nova Campanha** | Tab Remarketing | `btn-action-success` | ✅ |
| **Criar Primeira Campanha** | Empty State | `btn-action-success` | ✅ |
| **Criar Campanha** | Modal | `btn-action-success` | ✅ |

---

## 🎯 **REGRAS DE CONSISTÊNCIA:**

### **1. Sempre usar classe base:**
```html
class="btn-action btn-action-VARIANTE"
```

### **2. Sempre incluir ícone:**
```html
<i class="fas fa-icon"></i>
```

### **3. Ícone sempre com margin-right automático:**
```css
.btn-action i { margin-right: 0.5rem; }
```

### **4. Nunca sobrescrever cores:**
```html
<!-- ❌ ERRADO -->
<button class="btn-action btn-action-primary bg-blue-500">

<!-- ✅ CORRETO -->
<button class="btn-action btn-action-primary">
```

### **5. Usar variantes semânticas:**
- **primary:** Ação principal/crítica
- **success:** Adicionar/Criar
- **info:** Links/Informação

---

## 🔧 **ESPECIFICAÇÕES TÉCNICAS:**

### **Dimensões:**
```css
padding: 0.5rem 1rem;        /* 8px 16px */
border-radius: 0.5rem;       /* 8px */
font-size: 0.875rem;         /* 14px */
gap: 8px;                    /* entre ícone e texto */
```

### **Tipografia:**
```css
font-weight: 600;            /* semibold */
color: #111827;              /* gray-900 */
```

### **Transição:**
```css
transition: all 0.15s ease;
```

### **Hover:**
```css
transform: translateY(-2px);  /* Opcional - não no dashboard original */
box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 
            0 10px 10px -5px rgba(0, 0, 0, 0.04);
```

---

## 🏆 **CHECKLIST DE VALIDAÇÃO:**

Antes de criar um novo botão, verificar:

- [ ] Usa classe base `.btn-action`
- [ ] Usa variante semântica (primary/success/info)
- [ ] Tem ícone Font Awesome
- [ ] Usa `var(--brand-gold-500)` e `var(--brand-gold-700)`
- [ ] NUNCA usa HEX direto (#D97706, #B45309)
- [ ] Texto é descritivo e claro
- [ ] Padding: `0.5rem 1rem`
- [ ] Border-radius: `0.5rem`
- [ ] Color: `#111827`

---

## 📦 **ARQUIVO DE REFERÊNCIA:**

**Localização:** `templates/bot_config_v2.html` (linhas 171-215)

**Variáveis CSS:** `static/css/brand-colors-v2.css`
- `--brand-gold-500`: `#FFB800`
- `--brand-gold-700`: `#DAA520`

---

## 🎯 **RESUMO EXECUTIVO:**

### **COR OFICIAL DOS BOTÕES:**
🟡 **DOURADO** (`var(--brand-gold-500)` → `var(--brand-gold-700)`)

### **NÃO É:**
- ❌ Laranja
- ❌ Amarelo puro
- ❌ Verde
- ❌ Azul

### **É:**
- ✅ **DOURADO** (gold)
- ✅ Igual ao Dashboard
- ✅ Variáveis CSS do sistema
- ✅ Gradiente suave

---

## 🚀 **COMANDO PARA SUBIR:**

```bash
cd /root/grimbots
git pull origin main
sudo systemctl restart grimbots
```

---

**🏆 PADRÃO OFICIAL ESTABELECIDO E DOCUMENTADO! DOURADO PURO! 🟡**

**Documento oficial:** `PADRAO_BOTOES_OFICIAL.md`

