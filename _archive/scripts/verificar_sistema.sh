#!/bin/bash
# Script de Verificação Pós-Deploy
# Valida se sistema está funcionando corretamente

echo "=========================================="
echo "  VERIFICAÇÃO DO SISTEMA - GRIMBOTS"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Contadores
PASSED=0
FAILED=0
WARNING=0

# Função de teste
test_check() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "Verificando $name... "
    
    if eval "$command" > /dev/null 2>&1; then
        if [ -n "$expected" ]; then
            result=$(eval "$command" 2>&1)
            if [[ "$result" == *"$expected"* ]]; then
                echo -e "${GREEN}✅ OK${NC}"
                ((PASSED++))
                return 0
            else
                echo -e "${YELLOW}⚠️  PARCIAL${NC}"
                ((WARNING++))
                return 1
            fi
        else
            echo -e "${GREEN}✅ OK${NC}"
            ((PASSED++))
            return 0
        fi
    else
        echo -e "${RED}❌ FALHOU${NC}"
        ((FAILED++))
        return 1
    fi
}

echo "🔍 VERIFICAÇÕES BÁSICAS"
echo "----------------------------------------"

# 1. Python
test_check "Python" "python --version"

# 2. Redis
test_check "Redis" "redis-cli ping" "PONG"

# 3. Diretório
test_check "Diretório do projeto" "test -f wsgi.py"

# 4. Ambiente virtual
test_check "Ambiente virtual" "test -d venv"

echo ""
echo "🔧 VERIFICAÇÕES DE CÓDIGO"
echo "----------------------------------------"

# 5. redis_manager.py
test_check "redis_manager.py existe" "test -f redis_manager.py"

# 6. redis_manager funciona
if test_check "redis_manager funciona" "python redis_manager.py"; then
    :
else
    echo "   Execute: python redis_manager.py (para ver erros)"
fi

# 7. Import correto no código
if grep -q "from redis_manager import get_redis_connection" bot_manager.py; then
    echo -e "Verificando imports... ${GREEN}✅ OK${NC}"
    ((PASSED++))
else
    echo -e "Verificando imports... ${RED}❌ FALHOU${NC}"
    echo "   Adicione: from redis_manager import get_redis_connection"
    ((FAILED++))
fi

echo ""
echo "⚙️  VERIFICAÇÕES DE SERVIÇOS"
echo "----------------------------------------"

# 8. Systemd grimbots.service
if sudo systemctl is-active --quiet grimbots 2>/dev/null; then
    echo -e "Verificando grimbots.service... ${GREEN}✅ RODANDO${NC}"
    ((PASSED++))
else
    echo -e "Verificando grimbots.service... ${RED}❌ PARADO${NC}"
    echo "   Execute: sudo systemctl start grimbots"
    ((FAILED++))
fi

# 9. RQ Workers
WORKER_COUNT=$(sudo systemctl status 'rq-worker@*' 2>/dev/null | grep -c "active (running)" || echo "0")
if [ "$WORKER_COUNT" -eq 11 ]; then
    echo -e "Verificando RQ Workers... ${GREEN}✅ 11/11 RODANDO${NC}"
    ((PASSED++))
elif [ "$WORKER_COUNT" -gt 0 ]; then
    echo -e "Verificando RQ Workers... ${YELLOW}⚠️  $WORKER_COUNT/11 RODANDO${NC}"
    echo "   Execute: sudo systemctl start 'rq-worker@*'"
    ((WARNING++))
else
    echo -e "Verificando RQ Workers... ${RED}❌ NENHUM RODANDO${NC}"
    echo "   Execute: sudo systemctl start 'rq-worker@*'"
    ((FAILED++))
fi

# 10. Porta 5000
if lsof -i:5000 > /dev/null 2>&1; then
    echo -e "Verificando porta 5000... ${GREEN}✅ EM USO${NC}"
    ((PASSED++))
else
    echo -e "Verificando porta 5000... ${RED}❌ LIVRE${NC}"
    echo "   Gunicorn não está escutando na porta 5000"
    ((FAILED++))
fi

echo ""
echo "🏥 VERIFICAÇÕES DE SAÚDE"
echo "----------------------------------------"

# 11. Health check endpoint
HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health 2>/dev/null || echo "000")
if [ "$HEALTH_CODE" = "200" ]; then
    echo -e "Verificando /health... ${GREEN}✅ 200 OK${NC}"
    ((PASSED++))
    
    # Verificar componentes do health check
    HEALTH_RESPONSE=$(curl -s http://localhost:5000/health 2>/dev/null)
    
    # Database
    if echo "$HEALTH_RESPONSE" | grep -q '"database": "ok"'; then
        echo -e "  └─ Database... ${GREEN}✅ OK${NC}"
    else
        echo -e "  └─ Database... ${RED}❌ ERRO${NC}"
        ((WARNING++))
    fi
    
    # Redis
    if echo "$HEALTH_RESPONSE" | grep -q '"status": "healthy"'; then
        echo -e "  └─ Redis... ${GREEN}✅ OK${NC}"
    else
        echo -e "  └─ Redis... ${YELLOW}⚠️  ATENÇÃO${NC}"
        ((WARNING++))
    fi
    
    # RQ Workers
    if echo "$HEALTH_RESPONSE" | grep -q '"workers"'; then
        echo -e "  └─ RQ Workers... ${GREEN}✅ OK${NC}"
    else
        echo -e "  └─ RQ Workers... ${YELLOW}⚠️  ATENÇÃO${NC}"
        ((WARNING++))
    fi
    
elif [ "$HEALTH_CODE" = "503" ]; then
    echo -e "Verificando /health... ${RED}❌ 503 UNHEALTHY${NC}"
    echo "   Execute: curl http://localhost:5000/health | jq"
    ((FAILED++))
else
    echo -e "Verificando /health... ${RED}❌ $HEALTH_CODE${NC}"
    echo "   Endpoint não está acessível"
    ((FAILED++))
fi

echo ""
echo "📊 VERIFICAÇÕES DE PERFORMANCE"
echo "----------------------------------------"

# 12. Testar latência básica
echo -n "Testando latência... "
START_TIME=$(date +%s%N)
curl -s http://localhost:5000/health > /dev/null 2>&1
END_TIME=$(date +%s%N)
LATENCY=$(( (END_TIME - START_TIME) / 1000000 ))

if [ "$LATENCY" -lt 500 ]; then
    echo -e "${GREEN}✅ ${LATENCY}ms (excelente)${NC}"
    ((PASSED++))
elif [ "$LATENCY" -lt 1000 ]; then
    echo -e "${YELLOW}⚠️  ${LATENCY}ms (aceitável)${NC}"
    ((WARNING++))
else
    echo -e "${RED}❌ ${LATENCY}ms (lento)${NC}"
    ((FAILED++))
fi

# 13. Verificar logs recentes de erro
ERROR_COUNT=$(sudo journalctl -u grimbots --since "5 minutes ago" -p err 2>/dev/null | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "Verificando erros recentes... ${GREEN}✅ NENHUM (5 min)${NC}"
    ((PASSED++))
elif [ "$ERROR_COUNT" -lt 5 ]; then
    echo -e "Verificando erros recentes... ${YELLOW}⚠️  $ERROR_COUNT erros (5 min)${NC}"
    ((WARNING++))
else
    echo -e "Verificando erros recentes... ${RED}❌ $ERROR_COUNT erros (5 min)${NC}"
    echo "   Execute: sudo journalctl -u grimbots -p err -n 20"
    ((FAILED++))
fi

echo ""
echo "=========================================="
echo "  RESULTADOS"
echo "=========================================="
echo ""

TOTAL=$((PASSED + FAILED + WARNING))
echo "Total de verificações: $TOTAL"
echo -e "${GREEN}✅ Passou: $PASSED${NC}"
if [ "$WARNING" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Avisos: $WARNING${NC}"
fi
if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}❌ Falhou: $FAILED${NC}"
fi

echo ""

# Status geral
if [ "$FAILED" -eq 0 ] && [ "$WARNING" -eq 0 ]; then
    echo -e "${GREEN}✅ SISTEMA TOTALMENTE OPERACIONAL${NC}"
    echo ""
    echo "🎉 Parabéns! O sistema está funcionando perfeitamente."
    echo ""
    echo "Próximos passos:"
    echo "  1. Executar testes de carga: locust -f locustfile.py --headless -u 50 -r 10 -t 60s"
    echo "  2. Monitorar por 24-48h"
    echo "  3. Validar métricas de performance"
    echo "  4. Iniciar Fase 2 (PostgreSQL)"
    exit 0
elif [ "$FAILED" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  SISTEMA OPERACIONAL COM AVISOS${NC}"
    echo ""
    echo "O sistema está funcionando, mas há pontos de atenção."
    echo "Revise os avisos acima antes de prosseguir."
    exit 0
else
    echo -e "${RED}❌ SISTEMA COM PROBLEMAS${NC}"
    echo ""
    echo "Corrija os erros acima antes de prosseguir."
    echo ""
    echo "Comandos úteis:"
    echo "  sudo systemctl status grimbots"
    echo "  sudo journalctl -u grimbots -n 50"
    echo "  curl http://localhost:5000/health | jq"
    exit 1
fi

