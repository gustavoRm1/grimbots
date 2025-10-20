# 🔧 **MUDANÇA DE MARCA: APX → GRIM**

## 🎯 **OBJETIVO**

Trocar todos os valores padrão de `apx` para `grim` para dar identidade própria ao GrimBots e não parecer cópia de outros sistemas.

---

## 📋 **ARQUIVOS MODIFICADOS**

### **1. Backend (Python)**

#### **`models.py`**
```python
# ANTES
meta_cloaker_param_name = db.Column(db.String(20), default='apx')

# DEPOIS
meta_cloaker_param_name = db.Column(db.String(20), default='grim')
```

#### **`app.py`** (3 ocorrências)
```python
# ANTES
'meta_cloaker_param_name': pool.meta_cloaker_param_name or 'apx'
pool.meta_cloaker_param_name = data['meta_cloaker_param_name'].strip() or 'apx'
bot.meta_cloaker_param_name = data.get('meta_cloaker_param_name', 'apx')

# DEPOIS
'meta_cloaker_param_name': pool.meta_cloaker_param_name or 'grim'
pool.meta_cloaker_param_name = data['meta_cloaker_param_name'].strip() or 'grim'
bot.meta_cloaker_param_name = data.get('meta_cloaker_param_name', 'grim')
```

#### **`migrate_meta_pixel_to_pools.py`**
```python
# ANTES
("meta_cloaker_param_name", "VARCHAR(20) DEFAULT 'apx'"),

# DEPOIS
("meta_cloaker_param_name", "VARCHAR(20) DEFAULT 'grim'"),
```

---

### **2. Frontend (HTML/JS)**

#### **`templates/redirect_pools.html`** (4 ocorrências)

**Placeholder do input:**
```html
<!-- ANTES -->
<input placeholder="apx">

<!-- DEPOIS -->
<input placeholder="grim">
```

**Placeholder do valor:**
```html
<!-- ANTES -->
<input placeholder="ohx9lury">

<!-- DEPOIS -->
<input placeholder="xyz123abc">
```

**Exemplo na documentação:**
```html
<!-- ANTES -->
<code>apx=ohx9lury</code>

<!-- DEPOIS -->
<code>grim=xyz123abc</code>
```

**Variável JavaScript:**
```javascript
// ANTES
metaPixelConfig: {
    meta_cloaker_param_name: 'apx',
}

// DEPOIS
metaPixelConfig: {
    meta_cloaker_param_name: 'grim',
}
```

---

### **3. Documentação**

#### **`META_PIXEL_V2_DEPLOY.md`** (2 ocorrências)
```markdown
<!-- ANTES -->
Parâmetro: apx = ohx9lury
Parâmetros de URL (com Cloaker):
apx=ohx9lury&utm_source=facebook&utm_campaign=teste

<!-- DEPOIS -->
Parâmetro: grim = xyz123abc
Parâmetros de URL (com Cloaker):
grim=xyz123abc&utm_source=facebook&utm_campaign=teste
```

#### **`FINAL_META_PIXEL_V2.md`**
```markdown
<!-- ANTES -->
Parâmetro: apx = [ohx9lury]

<!-- DEPOIS -->
Parâmetro: grim = [xyz123abc]
```

---

## 🎨 **NOVA INTERFACE**

### **Modal de Configuração**

```
╔══════════════════════════════════════════════════╗
║  🛡️ Cloaker + AntiClone            [✓]          ║
║                                                  ║
║  Parâmetro: [grim        ]                       ║
║  Valor:     [xyz123abc   ]                       ║
║                                                  ║
║  Use nos Parâmetros de URL:                      ║
║  grim=xyz123abc                                  ║
╚══════════════════════════════════════════════════╝
```

---

## 📊 **EXEMPLO PRÁTICO**

### **ANTES (ApexVips Style)**
```
URL do Site:
https://seudominio.com/go/meta1

Parâmetros de URL:
apx=ohx9lury&utm_source=facebook
```

### **DEPOIS (GrimBots Style)**
```
URL do Site:
https://seudominio.com/go/meta1

Parâmetros de URL:
grim=xyz123abc&utm_source=facebook
```

---

## 🚀 **COMO USAR**

### **1. Configurar Pool**
```
Redirecionadores → Editar Pool → Meta Pixel

🛡️ Cloaker + AntiClone: ✓ ATIVO
Parâmetro: grim
Valor: xyz123abc (gerado automaticamente ou customizado)
```

### **2. Configurar Meta Ads**
```
URL do Site:
https://seudominio.com/go/seu-pool

Parâmetros de URL:
grim=xyz123abc&utm_source=facebook&utm_campaign=teste&fbclid={{fbclid}}
```

### **3. Resultado**
```
✅ TRÁFEGO REAL (do anúncio):
   /go/seu-pool?grim=xyz123abc&fbclid=ABC123
   → Redirect para bot ✅

❌ ACESSO DIRETO (sem parâmetro):
   /go/seu-pool
   → Página de erro 403 ❌

❌ PARÂMETRO ERRADO:
   /go/seu-pool?grim=ERRADO
   → Página de erro 403 ❌
```

---

## ✅ **VALIDAÇÃO**

### **Checklist de Mudanças**

- [x] `models.py` - default='grim'
- [x] `app.py` - 3 ocorrências alteradas
- [x] `migrate_meta_pixel_to_pools.py` - default='grim'
- [x] `templates/redirect_pools.html` - 4 ocorrências alteradas
- [x] `META_PIXEL_V2_DEPLOY.md` - 2 ocorrências alteradas
- [x] `FINAL_META_PIXEL_V2.md` - 1 ocorrência alterada

### **Banco de Dados**

```sql
-- Novos pools criados após migração terão automaticamente:
SELECT meta_cloaker_param_name FROM redirect_pools;
-- Resultado: 'grim'

-- Pools existentes mantêm valor antigo até serem editados
-- (comportamento esperado)
```

---

## 🎯 **VANTAGENS DA MUDANÇA**

### **1. Identidade Própria**
```
❌ ANTES: apx (igual ApexVips)
✅ DEPOIS: grim (marca própria GrimBots)
```

### **2. Branding**
```
✅ Nome do sistema: GrimBots
✅ Parâmetro personalizado: grim
✅ Coerência de marca
```

### **3. Diferenciação**
```
✅ Não parece cópia
✅ Identidade visual própria
✅ Profissionalismo
```

---

## 📝 **NOTAS IMPORTANTES**

### **⚠️ Pools Existentes**
- Pools já criados **mantêm** o valor antigo (`apx`)
- Ao editar, podem trocar para `grim` manualmente
- Sistema aceita qualquer nome de parâmetro

### **✅ Novos Pools**
- Terão `grim` como padrão
- Valor gerado automaticamente ao ativar cloaker
- Usuário pode customizar livremente

### **🔧 Flexibilidade**
- Sistema aceita qualquer nome: `grim`, `apx`, `secure`, `check`, etc.
- Usuário pode personalizar como preferir
- Apenas o padrão mudou de `apx` para `grim`

---

## 🎉 **RESULTADO FINAL**

**GrimBots agora tem identidade própria!**

✅ Parâmetro padrão: `grim` (não `apx`)
✅ Exemplos atualizados na documentação
✅ Interface atualizada
✅ Migração atualizada
✅ Coerência de marca

**Sistema profissional com branding próprio!** 🚀

---

*Mudança implementada em: 2025-10-20*
*Versão: 2.0*

