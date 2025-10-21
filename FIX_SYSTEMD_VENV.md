# 🚨 FIX CRÍTICO: SYSTEMD PRECISA USAR VENV

## **PROBLEMA:**
Systemd está executando `python3` do sistema (sem Flask instalado) ao invés do venv.

## **SOLUÇÃO:**

### **PASSO 1: Verificar o arquivo de serviço**
```bash
sudo cat /etc/systemd/system/grimbots.service
```

### **PASSO 2: Editar o serviço**
```bash
sudo nano /etc/systemd/system/grimbots.service
```

**Conteúdo CORRETO:**
```ini
[Unit]
Description=Grimbots Flask Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/grimbots
Environment="PATH=/root/grimbots/venv/bin:/usr/bin"
ExecStart=/root/grimbots/venv/bin/gunicorn --config gunicorn_config.py wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**PONTOS CRÍTICOS:**
- ✅ `Environment="PATH=/root/grimbots/venv/bin:/usr/bin"` - Define PATH com venv
- ✅ `ExecStart=/root/grimbots/venv/bin/gunicorn` - Usa gunicorn do venv
- ✅ `WorkingDirectory=/root/grimbots` - Diretório correto

### **PASSO 3: Recarregar systemd**
```bash
sudo systemctl daemon-reload
```

### **PASSO 4: Reiniciar serviço**
```bash
sudo systemctl restart grimbots
```

### **PASSO 5: Verificar status**
```bash
sudo systemctl status grimbots
```

**Saída esperada:**
```
● grimbots.service - Grimbots Flask Application
   Loaded: loaded (/etc/systemd/system/grimbots.service; enabled)
   Active: active (running) since...
```

### **PASSO 6: Verificar logs**
```bash
sudo journalctl -u grimbots -f
```

**Deve ver:**
```
✅ Gamificação V2.0 carregada
✅ SECRET_KEY validada
✅ CORS configurado
```

---

## **ALTERNATIVA (Se não funcionar):**

Usar `gunicorn` diretamente com caminho absoluto:

```bash
# Parar serviço
sudo systemctl stop grimbots

# Rodar manualmente para testar
cd /root/grimbots
source venv/bin/activate
gunicorn --config gunicorn_config.py wsgi:app

# Se funcionar, Ctrl+C e ajustar systemd
```

