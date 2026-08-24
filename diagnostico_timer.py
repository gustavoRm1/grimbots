"""
DIAGNÓSTICO DEFINITIVO — Rodar NA VPS dentro da pasta do grimbots.
Mostra EXATAMENTE onde a cadeia do timer quebra.

USO: python diagnostico_timer.py
"""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("DIAGNÓSTICO TIMER — Grimbots Flow")
print("=" * 60)

# ─── 1. Redis connection ───
print("\n[1] REDIS CONNECTION")
try:
    from internal_logic.core.redis_manager import get_redis_connection
    rc = get_redis_connection()
    if rc:
        rc.ping()
        print(f"  ✅ Redis conectado: {rc}")
    else:
        print("  ❌ Redis connection retornou None")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ ERRO: {e}")
    sys.exit(1)

# ─── 2. Queue marathon ───
print("\n[2] MARATHON QUEUE")
try:
    from tasks_async import marathon_queue
    print(f"  ✅ marathon_queue: name={marathon_queue.name}")
    print(f"  connection: {marathon_queue.connection}")
    # Verificar se enqueue_in existe
    print(f"  enqueue_in existe: {hasattr(marathon_queue, 'enqueue_in')}")
except Exception as e:
    print(f"  ❌ ERRO: {e}")

# ─── 3. Jobs agendados no Redis ───
print("\n[3] JOBS AGENDADOS (ScheduledJobRegistry)")
try:
    from rq.registry import ScheduledJobRegistry
    registry = ScheduledJobRegistry(queue=marathon_queue)
    jobs = registry.get_job_ids()
    print(f"  Jobs no registry: {len(jobs)}")
    for jid in jobs[:5]:
        print(f"    - {jid}")
    if len(jobs) == 0:
        print("  ⚠️ NENHUM job agendado — timer não foi criado ou já foi consumido")
except Exception as e:
    print(f"  ❌ ERRO: {e}")

# ─── 4. Jobs na fila marathon (aguardando worker) ───
print("\n[4] FILA MARATHON (jobs prontos para worker)")
try:
    from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
    q_jobs = marathon_queue.get_job_ids()
    print(f"  Jobs na fila: {len(q_jobs)}")
    for jid in q_jobs[:5]:
        print(f"    - {jid}")
except Exception as e:
    print(f"  ❌ ERRO: {e}")

# ─── 5. Workers ativos ───
print("\n[5] WORKERS ATIVOS")
try:
    from rq.worker import Worker
    workers = Worker.all(connection=rc)
    print(f"  Workers: {len(workers)}")
    for w in workers:
        print(f"    - {w.name} | queues: {[q.name for q in w.queues]} | PID: {w.pid}")
    if len(workers) == 0:
        print("  ❌ NENHUM worker ativo!")
except Exception as e:
    print(f"  ❌ ERRO: {e}")

# ─── 6. flow_time_elapsed_fire importável? ───
print("\n[6] FLOW_TIME_ELAPSED_FIRE")
try:
    from tasks_async import flow_time_elapsed_fire
    print(f"  ✅ Importável: {flow_time_elapsed_fire}")
except Exception as e:
    print(f"  ❌ NÃO IMPORTÁVEL: {e}")

# ─── 7. Bot 126 config ───
print("\n[7] BOT 126 CONFIG")
try:
    from internal_logic.core.models import Bot, BotConfig
    b = Bot.query.get(126)
    if b and b.config:
        fs = b.config.get_flow_steps()
        print(f"  Steps: {len(fs)}")
        for s in fs:
            print(f"    {s['id']} ({s['type']}) conn={json.dumps(s.get('connections',{}))} conditions={len(s.get('conditions',[]))}")
        print(f"  start={b.config.flow_start_step_id}")
    else:
        print("  ❌ Bot 126 sem config")
except Exception as e:
    print(f"  ❌ ERRO: {e}")

# ─── 8. Redis keys de flow ───
print("\n[8] REDIS KEYS DE FLOW (bot 126)")
try:
    keys = rc.keys("*126*")
    flow_keys = [k.decode() if isinstance(k, bytes) else k for k in keys if "flow" in k or "gb:" in k]
    if flow_keys:
        for k in flow_keys[:10]:
            print(f"    {k}")
    else:
        print("  Nenhuma key de flow encontrada")
except Exception as e:
    print(f"  ❌ ERRO: {e}")

print("\n" + "=" * 60)
print("FIM DO DIAGNÓSTICO — me envie a saída COMPLETA")
print("=" * 60)
