# 🔥 COMANDOS PARA CORRIGIR SCHEDULER

## 🚨 PROBLEMA IDENTIFICADO

```
Scheduler disponível: True
Scheduler rodando: False  ← ❌ CRÍTICO!
⚠️ APScheduler não iniciado neste processo (lock em uso)
```

**Lock file:** `/tmp/grimbots_scheduler.lock`

---

## 🔧 COMANDOS PARA EXECUTAR NO SERVIDOR

### **1. Verificar Lock File:**
```bash
# Verificar se lock existe e qual PID está nele
cat /tmp/grimbots_scheduler.lock 2>/dev/null
```

### **2. Verificar se Processo Existe:**
```bash
# Substituir <PID> pelo PID que aparece no lock file
ps -p <PID> -o pid,cmd

# Se não retornar nada, o processo não existe (LOCK STALE)
```

### **3. Remover Lock Stale (SE processo não existe):**
```bash
rm -f /tmp/grimbots_scheduler.lock
echo "✅ Lock removido!"
```

### **4. Executar Script Completo (Recomendado):**
```bash
cd ~/grimbots
chmod +x scripts/verificar_scheduler_lock.sh
./scripts/verificar_scheduler_lock.sh
```

### **5. Reiniciar Aplicação:**
```bash
# Escolher um dos comandos abaixo (conforme seu setup):

# Opção 1: systemd
systemctl restart grimbots

# Opção 2: PM2
pm2 restart all

# Opção 3: Script customizado
./restart-app.sh

# Opção 4: Gunicorn direto (se usar manualmente)
pkill -f gunicorn
# Depois iniciar novamente conforme seu setup
```

### **6. Verificar Após Restart:**
```bash
python3 << 'EOF'
from app import app, bot_manager
with app.app_context():
    print(f"Scheduler disponível: {bot_manager.scheduler is not None}")
    if bot_manager.scheduler:
        print(f"Scheduler rodando: {bot_manager.scheduler.running}")
        if bot_manager.scheduler.running:
            print("✅ SCHEDULER FUNCIONANDO!")
            jobs = bot_manager.scheduler.get_jobs()
            upsell_jobs = [j for j in jobs if 'upsell' in j.id.lower()]
            print(f"Total jobs: {len(jobs)}")
            print(f"Jobs upsell: {len(upsell_jobs)}")
        else:
            print("❌ AINDA NÃO ESTÁ RODANDO - Verificar logs")
    else:
        print("❌ SCHEDULER NÃO DISPONÍVEL - Verificar inicialização")
EOF
```

---

## 📊 RESULTADO ESPERADO APÓS CORREÇÃO

```
Scheduler disponível: True
Scheduler rodando: True  ← ✅ DEVE APARECER TRUE!
Total jobs: X (número > 3)
Jobs upsell: Y (número > 0 se há upsells configurados)
```

---

## 🎯 CAUSA DO PROBLEMA

O scheduler usa um lock file (`/tmp/grimbots_scheduler.lock`) para garantir que apenas UM processo execute jobs agendados. 

**O que pode ter acontecido:**
1. Processo anterior morreu mas não removeu o lock
2. Lock ficou "stale" (órfão)
3. Novo processo não consegue adquirir lock porque arquivo ainda existe

**Solução:**
- Remover lock stale (se processo não existe)
- Reiniciar aplicação para scheduler iniciar corretamente

---

## ⚠️ IMPORTANTE

**NÃO remova o lock se o processo ainda estiver rodando!** Isso pode causar duplicação de jobs.

Sempre verifique com `ps -p <PID>` antes de remover.

---

**Execute os comandos acima e compartilhe o resultado!**

