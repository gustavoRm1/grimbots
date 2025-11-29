# 🔍 COMANDOS PARA VERIFICAR UPSELLS NO SERVIDOR

## 📋 Execute no servidor Linux (SSH):

### **1. Navegar até o diretório:**
```bash
cd ~/grimbots
```

### **2. Dar permissão ao script:**
```bash
chmod +x scripts/verificar_webhook_upsells.sh
```

### **3. Executar script completo:**
```bash
./scripts/verificar_webhook_upsells.sh
```

---

## 🔍 COMANDOS MANUAIS (Alternativa)

Se o script não funcionar, execute estes comandos manualmente:

### **A. Verificar Jobs Falhados:**
```bash
rq failed --queue webhook
```

### **B. Verificar Logs de Webhook:**
```bash
# Tentar diferentes arquivos de log:
grep -E "(process_webhook_async|UPSELLS|WEBHOOK.*paid)" logs/error.log | tail -50
grep -E "(process_webhook_async|UPSELLS|WEBHOOK.*paid)" logs/app.log | tail -50
grep -E "(process_webhook_async|UPSELLS|WEBHOOK.*paid)" gunicorn.log | tail -50

# Ou buscar em todos os logs:
find logs -name "*.log" -exec grep -H "UPSELLS\|process_webhook_async" {} \; | tail -50
```

### **C. Verificar Scheduler (Python):**
```bash
python3 << 'EOF'
from app import app, bot_manager
with app.app_context():
    print(f"Scheduler disponível: {bot_manager.scheduler is not None}")
    if bot_manager.scheduler:
        print(f"Scheduler rodando: {bot_manager.scheduler.running}")
        jobs = bot_manager.scheduler.get_jobs()
        upsell_jobs = [j for j in jobs if 'upsell' in j.id.lower()]
        print(f"Total jobs: {len(jobs)}")
        print(f"Jobs upsell: {len(upsell_jobs)}")
        if upsell_jobs:
            print("\nPróximos 5 jobs upsell:")
            for job in upsell_jobs[:5]:
                print(f"  - {job.id}: {job.next_run_time}")
EOF
```

### **D. Verificar Último Pagamento PushynPay:**
```bash
python3 << 'EOF'
from app import app, db
from models import Payment
with app.app_context():
    last = Payment.query.filter_by(gateway_type='pushynpay').order_by(Payment.created_at.desc()).first()
    if last:
        print(f"Payment ID: {last.payment_id}")
        print(f"Status: {last.status}")
        print(f"Criado: {last.created_at}")
        print(f"Pago: {last.paid_at}")
        if last.bot and last.bot.config:
            print(f"Upsells enabled: {last.bot.config.upsells_enabled}")
            if last.bot.config.upsells_enabled:
                upsells = last.bot.config.get_upsells()
                print(f"Qtd upsells: {len(upsells) if upsells else 0}")
EOF
```

### **E. Verificar Jobs na Fila RQ:**
```bash
rq info webhook
```

---

## 🎯 O QUE VERIFICAR

### **Se encontrar jobs falhados:**
- Execute: `rq failed --queue webhook`
- Verifique o erro retornado
- Os logs mostrarão qual foi o problema

### **Se não encontrar logs:**
- Os logs podem estar sendo redirecionados para `journalctl` (systemd)
- Execute: `journalctl -u grimbots -n 100 | grep -E "(UPSELLS|WEBHOOK)"`

### **Se scheduler não está rodando:**
- Verifique se a aplicação foi reiniciada após as correções
- Execute: `systemctl restart grimbots` (ou o comando de restart apropriado)

---

## 📊 RESULTADO ESPERADO

Se tudo estiver funcionando, você deve ver:

```
✅ Scheduler disponível: True
✅ Scheduler rodando: True
✅ Jobs de upsell: X (número > 0 se há upsells agendados)
```

E nos logs:
```
🔍 [UPSELLS ASYNC] Verificando condições...
✅ [UPSELLS ASYNC] Condições atendidas!
📅 [UPSELLS ASYNC] Upsells agendados com sucesso!
```

---

**Execute os comandos acima no servidor e compartilhe os resultados!**

