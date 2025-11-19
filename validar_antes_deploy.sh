#!/bin/bash
# 🔍 SCRIPT DE VALIDAÇÃO - TRACKING META PIXEL
# Execute na VPS ANTES de fazer deploy
# Verifica se código está correto e sem erros

set -euo pipefail

echo "=========================================="
echo "  VALIDAÇÃO - TRACKING META PIXEL"
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

# Função de teste
test_check() {
    local name="$1"
    local command="$2"
    
    echo -n "🔍 $name... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ FALHOU${NC}"
        echo ""
        echo "Comando que falhou:"
        echo "  $command"
        echo ""
        echo "Output do erro:"
        eval "$command" 2>&1 | head -20
        echo ""
        ((FAILED++))
        return 1
    fi
}

# 1. Verificar sintaxe do Python
echo "📝 VERIFICAÇÃO DE SINTAXE"
echo "----------------------------------------"

test_check "Sintaxe app.py" "python -m py_compile app.py"
test_check "Sintaxe utils/tracking_service.py" "python -m py_compile utils/tracking_service.py"
test_check "Sintaxe utils/meta_pixel.py" "python -m py_compile utils/meta_pixel.py"
test_check "Sintaxe bot_manager.py" "python -m py_compile bot_manager.py"

echo ""

# 2. Verificar importação dos módulos
echo "📦 VERIFICAÇÃO DE IMPORTAÇÃO"
echo "----------------------------------------"

# Ativar venv se disponível
if [ -d "venv" ]; then
    source venv/bin/activate
fi

test_check "Import app" "python -c 'from app import app; print(\"✅ App importado\")'"
test_check "Import TrackingServiceV4" "python -c 'from utils.tracking_service import TrackingServiceV4; print(\"✅ TrackingServiceV4 importado\")'"
test_check "Import MetaPixelAPI" "python -c 'from utils.meta_pixel import MetaPixelAPI, normalize_external_id; print(\"✅ MetaPixelAPI importado\")'"
test_check "Import send_meta_pixel_pageview_event" "python -c 'from app import send_meta_pixel_pageview_event; print(\"✅ send_meta_pixel_pageview_event importado\")'"
test_check "Import send_meta_pixel_purchase_event" "python -c 'from app import send_meta_pixel_purchase_event; print(\"✅ send_meta_pixel_purchase_event importado\")'"

echo ""

# 3. Verificar funções específicas
echo "🔧 VERIFICAÇÃO DE FUNÇÕES"
echo "----------------------------------------"

test_check "TrackingServiceV4.save_tracking_token existe" "python -c 'from utils.tracking_service import TrackingServiceV4; ts = TrackingServiceV4(); assert hasattr(ts, \"save_tracking_token\"); print(\"✅ save_tracking_token existe\")'"
test_check "TrackingServiceV4.recover_tracking_data existe" "python -c 'from utils.tracking_service import TrackingServiceV4; ts = TrackingServiceV4(); assert hasattr(ts, \"recover_tracking_data\"); print(\"✅ recover_tracking_data existe\")'"
test_check "MetaPixelAPI._build_user_data existe" "python -c 'from utils.meta_pixel import MetaPixelAPI; assert hasattr(MetaPixelAPI, \"_build_user_data\"); print(\"✅ _build_user_data existe\")'"
test_check "normalize_external_id existe" "python -c 'from utils.meta_pixel import normalize_external_id; assert callable(normalize_external_id); print(\"✅ normalize_external_id existe\")'"

echo ""

# 4. Verificar campos críticos no código
echo "🔍 VERIFICAÇÃO DE CAMPOS CRÍTICOS"
echo "----------------------------------------"

test_check "client_ip em tracking_payload (app.py)" "grep -q \"'client_ip'.*user_ip\" app.py"
test_check "client_user_agent em tracking_payload (app.py)" "grep -q \"'client_user_agent'.*user_agent\" app.py"
test_check "client_ip em pageview_context (app.py)" "grep -q \"'client_ip'.*get_user_ip\" app.py"
test_check "client_user_agent em pageview_context (app.py)" "grep -q \"'client_user_agent'.*User-Agent\" app.py"
test_check "Preservação client_ip no merge (app.py)" "grep -q \"Preservando\|Usando client_ip\" app.py"
test_check "Preservação client_user_agent no merge (app.py)" "grep -q \"Preservando\|Usando client_user_agent\" app.py"
test_check "Campos críticos em TrackingServiceV4 (utils/tracking_service.py)" "grep -q \"critical_fields.*client_ip.*client_user_agent\" utils/tracking_service.py"

echo ""

# 5. Verificar Redis (se disponível)
echo "🔴 VERIFICAÇÃO DO REDIS"
echo "----------------------------------------"

if command -v redis-cli > /dev/null 2>&1; then
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis conectado${NC}"
        ((PASSED++))
        
        # Testar TrackingServiceV4
        echo -n "🔍 Testando TrackingServiceV4... "
        if python -c "
from utils.tracking_service import TrackingServiceV4
import uuid
ts = TrackingServiceV4()
test_token = uuid.uuid4().hex
test_payload = {
    'fbclid': 'test_fbclid_123',
    'fbp': 'fb.1.1234567890.1234567890',
    'client_ip': '192.168.1.100',
    'client_user_agent': 'Mozilla/5.0 Test',
    'pageview_event_id': 'test_pageview_123'
}
result = ts.save_tracking_token(test_token, test_payload, ttl=60)
assert result == True, 'Falha ao salvar'
recovered = ts.recover_tracking_data(test_token)
assert recovered.get('client_ip') == '192.168.1.100', 'client_ip não recuperado'
assert recovered.get('client_user_agent') == 'Mozilla/5.0 Test', 'client_user_agent não recuperado'
assert recovered.get('pageview_event_id') == 'test_pageview_123', 'pageview_event_id não recuperado'
print('✅ TrackingServiceV4 funcionando corretamente')
" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ OK${NC}"
            ((PASSED++))
        else
            echo -e "${RED}❌ FALHOU${NC}"
            echo ""
            echo "Teste manual do TrackingServiceV4:"
            python -c "
from utils.tracking_service import TrackingServiceV4
import uuid
ts = TrackingServiceV4()
test_token = uuid.uuid4().hex
test_payload = {
    'fbclid': 'test_fbclid_123',
    'fbp': 'fb.1.1234567890.1234567890',
    'client_ip': '192.168.1.100',
    'client_user_agent': 'Mozilla/5.0 Test',
    'pageview_event_id': 'test_pageview_123'
}
result = ts.save_tracking_token(test_token, test_payload, ttl=60)
print(f'Save result: {result}')
recovered = ts.recover_tracking_data(test_token)
print(f'Recovered: {recovered}')
print(f'client_ip: {recovered.get(\"client_ip\")}')
print(f'client_user_agent: {recovered.get(\"client_user_agent\")}')
print(f'pageview_event_id: {recovered.get(\"pageview_event_id\")}')
"
            ((FAILED++))
        fi
    else
        echo -e "${YELLOW}⚠️  Redis não está rodando (pode ser ignorado se não estiver em uso)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  redis-cli não encontrado (pode ser ignorado)${NC}"
fi

echo ""

# 6. Resumo final
echo "=========================================="
echo "  RESUMO FINAL"
echo "=========================================="
echo ""
echo "✅ Testes passados: $PASSED"
echo "❌ Testes falhados: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ TODOS OS TESTES PASSARAM!${NC}"
    echo ""
    echo "✅ O código está pronto para deploy!"
    echo ""
    echo "Próximos passos:"
    echo "  1. Fazer commit das alterações"
    echo "  2. Fazer push para origin/main"
    echo "  3. Na VPS: git pull origin main"
    echo "  4. Na VPS: ./restart-app.sh"
    echo ""
    exit 0
else
    echo -e "${RED}❌ ALGUNS TESTES FALHARAM!${NC}"
    echo ""
    echo "❌ CORRIJA OS ERROS ANTES DE FAZER DEPLOY!"
    echo ""
    echo "Verifique os erros acima e corrija o código."
    echo ""
    exit 1
fi

