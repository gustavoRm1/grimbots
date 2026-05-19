#!/bin/bash
# Script de teste para validar Server-Side Parameter Builder

echo "🧪 TESTANDO PARAMETER BUILDER"
echo "================================"
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ ERRO: Execute este script do diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar se função existe
echo "1️⃣ Verificando se função process_meta_parameters existe..."
python3 << 'EOF'
try:
    from utils.meta_pixel import process_meta_parameters
    print("✅ Função process_meta_parameters encontrada!")
    
    # Testar função com dados simulados
    print("   Testando função com dados simulados...")
    result = process_meta_parameters(
        request_cookies={
            '_fbc': 'fb.1.1234567890.IwAR1234567890',
            '_fbp': 'fb.1.1234567890.1234567890',
            '_fbi': '192.168.1.1'
        },
        request_args={'fbclid': 'IwAR1234567890'},
        request_headers={'X-Forwarded-For': '192.168.1.2'},
        request_remote_addr='192.168.1.3'
    )
    
    print("✅ Teste da função OK!")
    print(f"   fbc: {result.get('fbc', 'None')[:50] if result.get('fbc') else 'None'}")
    print(f"   fbc_origin: {result.get('fbc_origin', 'None')}")
    print(f"   fbp: {result.get('fbp', 'None')[:30] if result.get('fbp') else 'None'}")
    print(f"   fbp_origin: {result.get('fbp_origin', 'None')}")
    print(f"   client_ip_address: {result.get('client_ip_address', 'None')}")
    print(f"   ip_origin: {result.get('ip_origin', 'None')}")
    
    # Validar resultados
    if result.get('fbc'):
        print("   ✅ fbc retornado corretamente")
    else:
        print("   ⚠️ fbc não retornado (pode ser normal se não tiver fbclid)")
    
    if result.get('fbp'):
        print("   ✅ fbp retornado corretamente")
    else:
        print("   ⚠️ fbp não retornado")
    
    if result.get('client_ip_address'):
        print("   ✅ client_ip_address retornado corretamente")
    else:
        print("   ⚠️ client_ip_address não retornado")
        
except ImportError as e:
    print(f"❌ ERRO: Função não encontrada - {e}")
except Exception as e:
    print(f"❌ ERRO ao testar função: {e}")
    import traceback
    traceback.print_exc()
EOF

echo ""
echo "2️⃣ Verificando logs recentes (últimos 500 linhas)..."
echo ""

# Verificar se logs existem
if [ ! -f "logs/gunicorn.log" ]; then
    echo "⚠️ Arquivo logs/gunicorn.log não encontrado"
    echo "   Verifique se o Gunicorn está rodando e gerando logs"
else
    # Buscar logs do Parameter Builder
    echo "   Buscando logs do Parameter Builder..."
    tail -500 logs/gunicorn.log | grep -E "PARAM BUILDER|Parameter Builder|fbc processado|fbp processado|client_ip processado" | tail -10
    
    if [ $? -eq 0 ]; then
        echo "   ✅ Logs do Parameter Builder encontrados!"
    else
        echo "   ⚠️ Nenhum log do Parameter Builder encontrado (pode ser normal se não houver eventos recentes)"
    fi
fi

echo ""
echo "3️⃣ Estatísticas dos últimos eventos (últimos 1000 linhas)..."
echo ""

if [ -f "logs/gunicorn.log" ]; then
    # ✅ Contar eventos (garantir que variáveis sejam números)
    TOTAL_PAGEVIEW=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "META PAGEVIEW.*PageView -" 2>/dev/null || echo "0")
    PAGEVIEW_FBC=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "PageView - fbc processado pelo Parameter Builder" 2>/dev/null || echo "0")
    PAGEVIEW_FBC_REAL=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "PageView - fbc REAL confirmado\|PageView - fbc confirmado" 2>/dev/null || echo "0")
    PAGEVIEW_FBC_AUSENTE=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "PageView - fbc NÃO retornado pelo Parameter Builder" 2>/dev/null || echo "0")
    
    TOTAL_PURCHASE=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "META PURCHASE.*Purchase -" 2>/dev/null || echo "0")
    PURCHASE_FBC=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "Purchase - fbc processado pelo Parameter Builder" 2>/dev/null || echo "0")
    PURCHASE_FBC_REAL=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "Purchase - fbc REAL aplicado" 2>/dev/null || echo "0")
    PURCHASE_FBC_AUSENTE=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -c "Purchase - fbc ausente ou ignorado\|Purchase - fbc NÃO retornado pelo Parameter Builder" 2>/dev/null || echo "0")
    
    # ✅ Normalizar variáveis (remover espaços/newlines e garantir que sejam números)
    TOTAL_PAGEVIEW=$(printf '%s' "${TOTAL_PAGEVIEW}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    PAGEVIEW_FBC=$(printf '%s' "${PAGEVIEW_FBC}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    PAGEVIEW_FBC_REAL=$(printf '%s' "${PAGEVIEW_FBC_REAL}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    PAGEVIEW_FBC_AUSENTE=$(printf '%s' "${PAGEVIEW_FBC_AUSENTE}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    
    TOTAL_PURCHASE=$(printf '%s' "${TOTAL_PURCHASE}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    PURCHASE_FBC=$(printf '%s' "${PURCHASE_FBC}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    PURCHASE_FBC_REAL=$(printf '%s' "${PURCHASE_FBC_REAL}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    PURCHASE_FBC_AUSENTE=$(printf '%s' "${PURCHASE_FBC_AUSENTE}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
    
    echo "   📊 PageView:"
    echo "      Total: ${TOTAL_PAGEVIEW}"
    echo "      Com fbc (Parameter Builder): ${PAGEVIEW_FBC}"
    echo "      Com fbc REAL confirmado: ${PAGEVIEW_FBC_REAL}"
    echo "      Com fbc ausente: ${PAGEVIEW_FBC_AUSENTE}"
    if [ "${TOTAL_PAGEVIEW}" -gt 0 ] 2>/dev/null && [ -n "${TOTAL_PAGEVIEW}" ]; then
        # ✅ Garantir que valores sejam números antes de calcular
        if [ "${PAGEVIEW_FBC}" -ge 0 ] 2>/dev/null && [ "${TOTAL_PAGEVIEW}" -gt 0 ] 2>/dev/null; then
            PAGEVIEW_COVERAGE=$(echo "scale=1; ${PAGEVIEW_FBC}*100/${TOTAL_PAGEVIEW}" 2>/dev/null | bc 2>/dev/null | tr -d ' \n\r' || echo "0")
            # ✅ Garantir que PAGEVIEW_COVERAGE seja um número válido
            PAGEVIEW_COVERAGE=$(echo "${PAGEVIEW_COVERAGE}" | grep -oE '[0-9]+\.?[0-9]*' | head -1 || echo "0")
            echo "      Cobertura: ${PAGEVIEW_COVERAGE}%"
            
            # ✅ Comparar usando bc (mais seguro)
            COVERAGE_NUM=$(echo "${PAGEVIEW_COVERAGE}" | grep -oE '[0-9]+\.?[0-9]*' | head -1 || echo "0")
            if [ -n "${COVERAGE_NUM}" ] && command -v bc >/dev/null 2>&1; then
                if (( $(echo "${COVERAGE_NUM} > 50" | bc -l 2>/dev/null || echo "0") )); then
                    echo "      ✅ Cobertura EXCELENTE (> 50%)"
                elif (( $(echo "${COVERAGE_NUM} > 20" | bc -l 2>/dev/null || echo "0") )); then
                    echo "      ⚠️ Cobertura ACEITÁVEL (20-50%)"
                else
                    echo "      ❌ Cobertura BAIXA (< 20%)"
                fi
            fi
        else
            echo "      Cobertura: 0%"
            echo "      ⚠️ Não foi possível calcular cobertura"
        fi
    else
        echo "      Cobertura: N/A (nenhum evento)"
    fi
    
    echo ""
    echo "   📊 Purchase:"
    echo "      Total: ${TOTAL_PURCHASE}"
    echo "      Com fbc (Parameter Builder): ${PURCHASE_FBC}"
    echo "      Com fbc REAL aplicado: ${PURCHASE_FBC_REAL}"
    echo "      Com fbc ausente: ${PURCHASE_FBC_AUSENTE}"
        if [ "${TOTAL_PURCHASE}" -gt 0 ] 2>/dev/null && [ -n "${TOTAL_PURCHASE}" ]; then
            # ✅ Garantir que valores sejam números antes de calcular
            if [ "${PURCHASE_FBC_REAL}" -ge 0 ] 2>/dev/null && [ "${TOTAL_PURCHASE}" -gt 0 ] 2>/dev/null; then
                PURCHASE_COVERAGE=$(echo "scale=1; ${PURCHASE_FBC_REAL}*100/${TOTAL_PURCHASE}" 2>/dev/null | bc 2>/dev/null | tr -d ' \n\r' || echo "0")
                # ✅ Garantir que PURCHASE_COVERAGE seja um número válido
                PURCHASE_COVERAGE=$(echo "${PURCHASE_COVERAGE}" | grep -oE '[0-9]+\.?[0-9]*' | head -1 || echo "0")
                echo "      Cobertura: ${PURCHASE_COVERAGE}%"
                
                # ✅ Comparar usando bc (mais seguro)
                COVERAGE_NUM=$(echo "${PURCHASE_COVERAGE}" | grep -oE '[0-9]+\.?[0-9]*' | head -1 || echo "0")
                if [ -n "${COVERAGE_NUM}" ] && command -v bc >/dev/null 2>&1; then
                    if (( $(echo "${COVERAGE_NUM} > 50" | bc -l 2>/dev/null || echo "0") )); then
                        echo "      ✅ Cobertura EXCELENTE (> 50%)"
                    elif (( $(echo "${COVERAGE_NUM} > 20" | bc -l 2>/dev/null || echo "0") )); then
                        echo "      ⚠️ Cobertura ACEITÁVEL (20-50%)"
                    else
                        echo "      ❌ Cobertura BAIXA (< 20%)"
                    fi
                fi
            else
                echo "      Cobertura: 0%"
                echo "      ⚠️ Não foi possível calcular cobertura"
            fi
        else
            echo "      Cobertura: N/A (nenhum evento)"
        fi
else
    echo "   ⚠️ Arquivo logs/gunicorn.log não encontrado"
fi

echo ""
echo "4️⃣ Verificando origem do fbc nos últimos eventos..."
echo ""

if [ -f "logs/gunicorn.log" ]; then
    FBC_COOKIE=$(tail -1000 logs/gunicorn.log | grep -c "fbc processado.*origem: cookie" 2>/dev/null || echo "0")
    FBC_GENERATED=$(tail -1000 logs/gunicorn.log | grep -c "fbc processado.*origem: generated_from_fbclid" 2>/dev/null || echo "0")
    
    echo "   fbc do cookie: ${FBC_COOKIE} eventos"
    echo "   fbc gerado (fbclid): ${FBC_GENERATED} eventos"
fi

echo ""
echo "================================"
echo "✅ Teste concluído!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "   1. Acesse Meta Events Manager → Eventos → Comprar (Purchase)"
echo "   2. Verifique seção 'Parâmetros compartilhados' → 'ID do clique (fbc)'"
echo "   3. Deve aparecer cobertura > 50% (aguarde 24-48h se acabou de implementar)"
echo ""

