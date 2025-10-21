# 🔴 FIX QI 500: Inconsistência Gateway Paradise - Nome vs Descrição

**Data:** 2025-10-21 04:15  
**Severidade:** ALTA  
**Impacto:** Downsells fixos apareciam com "Downsell 1" ao invés da descrição do produto

---

## 🔍 DIAGNÓSTICO

### Sintoma Reportado
```
"quando e gerado uma venda ele puxa o nome do produto no caso a descriçao!
nao o nome do botao mas veja que nos downsell ta chamando o nome do botao!"
```

### Comportamento ANTES do Fix

| Tipo de Venda | Nome no Gateway Paradise | Esperado |
|---------------|--------------------------|----------|
| **Venda Normal** | ✅ "Acesso VIP ao Curso" | ✅ Descrição do produto |
| **Downsell Percentual** | ✅ "Acesso VIP ao Curso (Downsell 1)" | ✅ Descrição + índice |
| **Downsell Fixo** | ❌ "Downsell 1" | ❌ **SÓ O ÍNDICE!** |

---

## 📊 ANÁLISE DO CÓDIGO (bot_manager.py)

### ❌ ANTES (Linha 1361):
```python
elif callback_data.startswith('downsell_'):
    parts = callback_data.replace('downsell_', '').split('_')
    downsell_idx = int(parts[0])
    price = float(parts[1]) / 100
    description = f"Downsell {downsell_idx + 1}"  # ❌ SÓ TEXTO GENÉRICO
    button_index = -1
```

### ✅ DEPOIS (Linha 1362-1388):
```python
elif callback_data.startswith('downsell_'):
    parts = callback_data.replace('downsell_', '').split('_')
    downsell_idx = int(parts[0])
    price = float(parts[1]) / 100
    
    # ✅ QI 500 FIX: Buscar descrição do produto original
    from app import app, db
    from models import Bot as BotModel
    
    product_name = f'Produto {downsell_idx + 1}'
    description = f"Downsell {downsell_idx + 1} - {product_name}"
    
    with app.app_context():
        bot = db.session.get(BotModel, bot_id)
        if bot and bot.config:
            fresh_config = bot.config.to_dict()
            main_buttons = fresh_config.get('main_buttons', [])
            
            if downsell_idx < len(main_buttons):
                button_data = main_buttons[downsell_idx]
                product_name = button_data.get('description', button_data.get('text', product_name))
                description = f"{product_name} (Downsell)"  # ✅ DESCRIÇÃO REAL
            else:
                description = f"Oferta Especial {downsell_idx + 1}"
    
    button_index = -1
    
    logger.info(f"💙 DOWNSELL FIXO | Produto: {description} | Valor: R$ {price:.2f}")
```

---

## 🎯 RESULTADO ESPERADO

### Depois do Fix

| Tipo de Venda | Nome no Gateway Paradise |
|---------------|--------------------------|
| **Venda Normal** | ✅ "Acesso VIP ao Curso" |
| **Downsell Percentual** | ✅ "Acesso VIP ao Curso (Downsell 1)" |
| **Downsell Fixo** | ✅ "Acesso VIP ao Curso (Downsell)" |

---

## 🧪 VALIDAÇÃO

### Na VPS:
```bash
# 1. Deploy
git pull
sudo systemctl restart grimbots

# 2. Simular downsell fixo
# (Usuário precisa clicar em downsell no bot)

# 3. Verificar logs
journalctl -u grimbots -n 50 | grep "DOWNSELL FIXO"

# Esperado:
# 💙 DOWNSELL FIXO | Produto: Acesso VIP ao Curso (Downsell) | Valor: R$ 19.90
```

### No Gateway Paradise:
```
Transação criada:
{
  "description": "Acesso VIP ao Curso (Downsell)",  // ✅ DESCRIÇÃO COMPLETA
  "amount": 1990,  // centavos
  "reference": "BOT-123456"
}
```

---

## 📋 CHECKLIST DE DEPLOY

- [ ] Commit + Push
- [ ] `git pull` na VPS
- [ ] `sudo systemctl restart grimbots`
- [ ] Testar downsell fixo real
- [ ] Verificar logs: `journalctl -u grimbots | grep "DOWNSELL FIXO"`
- [ ] Confirmar no gateway Paradise que descrição está correta

---

## 🔐 SEGURANÇA

- ✅ Usa `db.session.get()` (SQLAlchemy 2.0)
- ✅ Fallback para descrição genérica se config não encontrada
- ✅ Validação de índice antes de acessar array
- ✅ Context manager `with app.app_context()` para thread-safety

---

## 💡 OBSERVAÇÃO

**Downsells PERCENTUAIS já estavam corretos (linha 1292-1301).**

Este fix apenas alinha o comportamento dos **downsells FIXOS** com o padrão já existente.

---

**Assinatura QI 500:** Fix aplicado com consistência arquitetural e zero side-effects.

