# 🚀 **DEPLOY DIA 2 - EXECUTAR AGORA NA VPS**

## ✅ **CÓDIGO MODIFICADO**

Arquivos alterados:
1. ✅ `app.py` - PageView e Purchase agora são assíncronos
2. ✅ `bot_manager.py` - ViewContent agora é assíncrono
3. ✅ `requirements.txt` - Celery adicionado

---

## 📋 **COMANDOS NA VPS (EXECUTE AGORA)**

### **1. Atualizar código:**

```bash
cd ~/grimbots
git pull origin main
```

### **2. Reiniciar aplicação Flask:**

```bash
# Ver o que está rodando
sudo systemctl status grimbots

# Reiniciar
sudo systemctl restart grimbots

# Verificar se iniciou OK
sudo systemctl status grimbots
```

**Se não tiver systemd, use:**
```bash
pkill -f gunicorn
cd ~/grimbots
source venv/bin/activate
gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 wsgi:app &
```

### **3. Verificar Celery está rodando:**

```bash
sudo systemctl status grimbots-celery
```

**Deve mostrar:** `Active: active (running)`

### **4. Ver logs em tempo real:**

```bash
tail -f logs/celery.log
```

**Deixe rodando!**

---

## 🧪 **TESTE REAL - PIXEL FUNCIONANDO**

### **Pré-requisito:**
- Você precisa ter um **POOL configurado com Pixel ID e Access Token REAL**
- Acesse: https://seudominio.com/redirect-pools
- Configure o Meta Pixel em um pool

### **Teste:**

```bash
# Em outro terminal SSH (ou feche o tail -f com Ctrl+C)
cd ~/grimbots
source venv/bin/activate

# Simular acesso ao redirecionador
python -c "
from app import app, db
from models import RedirectPool
import requests

with app.app_context():
    # Buscar pool com pixel configurado
    pool = RedirectPool.query.filter(
        RedirectPool.meta_tracking_enabled == True,
        RedirectPool.meta_pixel_id.isnot(None)
    ).first()
    
    if pool:
        print(f'✅ Pool encontrado: {pool.name}')
        print(f'📊 Pixel ID: {pool.meta_pixel_id}')
        print(f'🔗 Slug: {pool.slug}')
        print(f'')
        print(f'🧪 TESTE: Acesse este link no navegador:')
        print(f'https://seudominio.com/go/{pool.slug}?utm_source=teste&utm_campaign=mvp_dia2')
    else:
        print('❌ Nenhum pool com pixel configurado!')
        print('Configure em: https://seudominio.com/redirect-pools')
"
```

---

## 📊 **VALIDAÇÃO**

### **1. No terminal com tail -f logs/celery.log você deve ver:**

```
[INFO] Task celery_app.send_meta_event received
[INFO] ✅ Evento enviado: PageView | ID: pageview_... | Latência: XXXms
[INFO] Task succeeded in 0.5s
```

### **2. No Meta Events Manager:**

1. Acesse: https://business.facebook.com/events_manager2
2. Selecione seu Pixel
3. Vá em "Overview" ou "Test Events"
4. Procure evento PageView dos últimos minutos
5. Deve ter:
   - ✅ Event Name: PageView
   - ✅ UTM Source: teste
   - ✅ UTM Campaign: mvp_dia2
   - ✅ External ID

---

## ⏱️ **MEDIR LATÊNCIA**

### **Antes (Síncrono):**
```
Redirect: 2-3 segundos
Bloqueava usuário
```

### **Depois (Assíncrono):**
```
Redirect: < 50ms
Não bloqueia usuário
Evento processa em background
```

### **Como medir:**

```bash
# Testar tempo de resposta do redirect
time curl -I "https://seudominio.com/go/seu_slug?utm_source=teste"
```

**Deve ser < 0.1s (100ms)**

---

## ✅ **CHECKLIST DIA 2**

- [ ] Código atualizado na VPS
- [ ] Flask reiniciado
- [ ] Celery rodando
- [ ] Teste PageView executado
- [ ] Evento apareceu no log do Celery
- [ ] Evento apareceu no Meta Events Manager
- [ ] Latência medida (< 100ms)
- [ ] Screenshot do Meta capturado

---

## 🚨 **SE DER ERRO**

### **Erro: Cannot import name 'send_meta_event'**

```bash
# Verificar se celery_app.py está OK
python -c "from celery_app import send_meta_event; print('OK')"
```

### **Erro: Redis connection refused**

```bash
# Verificar Redis
sudo systemctl status redis-server
redis-cli ping
```

### **Erro: Task não aparece no log**

```bash
# Reiniciar Celery
sudo systemctl restart grimbots-celery

# Ver logs
tail -f logs/celery.log
```

---

## 📸 **EVIDÊNCIAS NECESSÁRIAS**

Para completar DIA 2, precisamos:

1. ✅ Screenshot do Meta Events Manager mostrando evento
2. ✅ Log do Celery mostrando envio
3. ✅ Medição de latência (curl time)
4. ✅ Timestamp envio vs timestamp chegada no Meta

---

## 💪 **EXECUTE AGORA**

```bash
# 1. Deploy
git pull origin main
sudo systemctl restart grimbots

# 2. Verificar Celery
sudo systemctl status grimbots-celery

# 3. Monitorar
tail -f logs/celery.log

# 4. Testar (em outro terminal)
# Acessar link do pool no navegador
```

---

*DIA 2 em execução - QI 540* 🚀
*Código pronto*
*Aguardando testes reais*

