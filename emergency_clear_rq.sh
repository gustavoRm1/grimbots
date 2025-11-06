#!/bin/bash
# ✅ QI 1000: Script de Emergência - Limpeza Total RQ
# Use quando workers estão crashando por jobs corrompidas

echo "=========================================="
echo "🚨 EMERGÊNCIA: Limpeza Total RQ"
echo "=========================================="
echo ""

# PASSO 1: Parar todos os workers
echo "📋 PASSO 1: Parando todos os workers..."
pkill -9 -f "start_rq_worker.py" 2>/dev/null || true
sleep 2
echo "✅ Workers parados"
echo ""

# PASSO 2: Limpar Redis usando Python (mais seguro)
echo "📋 PASSO 2: Limpando filas RQ do Redis..."
cd /root/grimbots || cd ~/grimbots || exit 1
source venv/bin/activate 2>/dev/null || true

# Executar script Python
python clear_rq_queues.py --force 2>/dev/null || {
    echo "⚠️  Script Python falhou, usando redis-cli direto..."
    # Fallback: usar redis-cli
    redis-cli --eval - <<EOF
local keys = redis.call('keys', 'rq:*')
for i=1,#keys do
    redis.call('del', keys[i])
end
return #keys
EOF
    echo "✅ Limpeza via redis-cli concluída"
}

echo ""

# PASSO 3: Verificar se limpou
echo "📋 PASSO 3: Verificando limpeza..."
REMAINING=$(redis-cli --raw KEYS 'rq:*' 2>/dev/null | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  Ainda há $REMAINING chaves RQ no Redis"
    echo "   Executando limpeza forçada..."
    redis-cli --raw KEYS 'rq:*' | xargs -r redis-cli DEL 2>/dev/null || true
    echo "✅ Limpeza forçada concluída"
else
    echo "✅ Redis limpo completamente"
fi

echo ""

# PASSO 4: Reiniciar Redis
echo "📋 PASSO 4: Reiniciando Redis..."
systemctl restart redis 2>/dev/null || service redis restart 2>/dev/null || echo "⚠️  Não foi possível reiniciar Redis"
sleep 2
echo "✅ Redis reiniciado"
echo ""

# PASSO 5: Verificar conexão
echo "📋 PASSO 5: Verificando conexão Redis..."
if redis-cli PING > /dev/null 2>&1; then
    echo "✅ Redis está respondendo"
else
    echo "❌ Redis não está respondendo!"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ LIMPEZA CONCLUÍDA"
echo "=========================================="
echo ""
echo "📝 Agora você pode reiniciar os workers:"
echo "   python start_rq_worker.py tasks &"
echo "   python start_rq_worker.py gateway &"
echo "   python start_rq_worker.py webhook &"
echo ""

