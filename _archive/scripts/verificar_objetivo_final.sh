#!/bin/bash
# Script para verificar se o objetivo final está sendo alcançado
# Objetivo: Vendas trackeadas corretamente no Meta Ads Manager

echo "🎯 VERIFICANDO OBJETIVO FINAL: VENDAS TRACKEADAS NO META ADS MANAGER"
echo "===================================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ ERRO: Execute este script do diretório raiz do projeto (onde está app.py)"
    exit 1
fi

echo "1️⃣ Verificando se Purchase events estão sendo enviados (últimos 100 linhas)..."
echo ""

# Buscar Purchase events recentes
PURCHASE_EVENTS=$(tail -100 logs/gunicorn.log 2>/dev/null | grep "META PURCHASE.*Purchase -" | tail -10)

if [ -n "${PURCHASE_EVENTS}" ]; then
    echo "   ✅ Purchase events encontrados:"
    echo "${PURCHASE_EVENTS}" | sed 's/^/      /'
    
    # Contar eventos com fbc
    PURCHASE_COM_FBC=$(echo "${PURCHASE_EVENTS}" | grep -c "fbc REAL aplicado\|fbc confirmado" 2>/dev/null || echo "0")
    PURCHASE_SEM_FBC=$(echo "${PURCHASE_EVENTS}" | grep -c "fbc ausente\|fbc NÃO" 2>/dev/null || echo "0")
    PURCHASE_STATUS_200=$(echo "${PURCHASE_EVENTS}" | grep -c "Status: 200" 2>/dev/null || echo "0")
    
    echo ""
    echo "   📊 Estatísticas dos últimos eventos:"
    echo "      Com fbc: ${PURCHASE_COM_FBC}"
    echo "      Sem fbc: ${PURCHASE_SEM_FBC}"
    echo "      Status 200 (aceito pelo Meta): ${PURCHASE_STATUS_200}"
    
    if [ "${PURCHASE_COM_FBC}" -gt 0 ] 2>/dev/null; then
        echo ""
        echo "   ✅ Purchase events estão sendo enviados COM fbc"
        echo "   ✅ Objetivo final está sendo alcançado (vendas trackeadas)"
    else
        echo ""
        echo "   ⚠️ Purchase events estão sendo enviados SEM fbc"
        echo "   ⚠️ Objetivo final pode não estar sendo alcançado completamente"
    fi
else
    echo "   ⚠️ Nenhum Purchase event encontrado nos logs recentes"
    echo "   ⚠️ Isso pode significar que:"
    echo "      - Não houve vendas recentes"
    echo "      - Ou eventos não estão sendo enviados"
fi

echo ""
echo "2️⃣ Verificando origem do fbc nos Purchase events..."
echo ""

# Buscar origem do fbc
FBC_PARAM_BUILDER=$(tail -100 logs/gunicorn.log 2>/dev/null | grep -c "Purchase - fbc processado pelo Parameter Builder" 2>/dev/null || echo "0")
FBC_REDIS=$(tail -100 logs/gunicorn.log 2>/dev/null | grep -c "Purchase - fbc recuperado do tracking_data\|Purchase - fbc recuperado do Redis" 2>/dev/null || echo "0")
FBC_REAL=$(tail -100 logs/gunicorn.log 2>/dev/null | grep -c "Purchase - fbc REAL aplicado\|Purchase - fbc confirmado" 2>/dev/null || echo "0")

# Normalizar variáveis
FBC_PARAM_BUILDER=$(printf '%s' "${FBC_PARAM_BUILDER}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
FBC_REDIS=$(printf '%s' "${FBC_REDIS}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
FBC_REAL=$(printf '%s' "${FBC_REAL}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")

echo "   📊 Origem do fbc:"
echo "      Do Parameter Builder: ${FBC_PARAM_BUILDER}"
echo "      Do Redis (fallback): ${FBC_REDIS}"
echo "      Total com fbc REAL: ${FBC_REAL}"

if [ "${FBC_PARAM_BUILDER}" -gt 0 ] 2>/dev/null; then
    echo ""
    echo "   ✅ Parameter Builder está sendo usado"
elif [ "${FBC_REAL}" -gt 0 ] 2>/dev/null; then
    echo ""
    echo "   ⚠️ Parameter Builder NÃO está sendo usado (usando fallback)"
    echo "   ⚠️ Sistema está funcionando, mas pode melhorar"
else
    echo ""
    echo "   ❌ Nenhum fbc está sendo enviado"
    echo "   ❌ Objetivo final NÃO está sendo alcançado"
fi

echo ""
echo "3️⃣ Verificando PageView events (últimos 10 eventos)..."
echo ""

# Buscar PageView events recentes
PAGEVIEW_EVENTS=$(tail -100 logs/gunicorn.log 2>/dev/null | grep "META PAGEVIEW.*PageView -" | tail -10)

if [ -n "${PAGEVIEW_EVENTS}" ]; then
    echo "   Últimos eventos PageView:"
    echo "${PAGEVIEW_EVENTS}" | head -5 | sed 's/^/      /'
    
    # Contar eventos com fbc
    PAGEVIEW_COM_FBC=$(echo "${PAGEVIEW_EVENTS}" | grep -c "fbc REAL confirmado\|fbc confirmado" 2>/dev/null || echo "0")
    
    echo ""
    echo "   📊 PageView com fbc: ${PAGEVIEW_COM_FBC}/10"
    
    if [ "${PAGEVIEW_COM_FBC}" -gt 5 ] 2>/dev/null; then
        echo "   ✅ PageView events têm boa cobertura de fbc (> 50%)"
    else
        echo "   ⚠️ PageView events têm baixa cobertura de fbc (< 50%)"
    fi
else
    echo "   ⚠️ Nenhum PageView event encontrado nos logs recentes"
fi

echo ""
echo "===================================================================="
echo "📋 CONCLUSÃO:"
echo ""

# Determinar status final
if [ "${FBC_REAL}" -gt 0 ] 2>/dev/null; then
    echo "✅ OBJETIVO FINAL ESTÁ SENDO ALCANÇADO"
    echo ""
    echo "   ✅ Purchase events estão sendo enviados COM fbc"
    echo "   ✅ Vendas devem estar aparecendo no Meta Ads Manager"
    echo ""
    if [ "${FBC_PARAM_BUILDER}" -eq 0 ] 2>/dev/null; then
        echo "   ⚠️ Parameter Builder NÃO está sendo usado (usando fallback)"
        echo "   ⚠️ Sistema está funcionando, mas pode melhorar"
        echo "   ⚠️ Recomendação: Otimizar Parameter Builder (não urgente)"
    else
        echo "   ✅ Parameter Builder está sendo usado"
        echo "   ✅ Sistema está funcionando perfeitamente"
    fi
else
    echo "❌ OBJETIVO FINAL NÃO ESTÁ SENDO ALCANÇADO"
    echo ""
    echo "   ❌ Purchase events NÃO estão sendo enviados COM fbc"
    echo "   ❌ Vendas podem NÃO estar aparecendo no Meta Ads Manager"
    echo ""
    echo "   🔧 AÇÕES NECESSÁRIAS:"
    echo "      1. Investigar por que fbc não está sendo enviado"
    echo "      2. Verificar se Parameter Builder está funcionando"
    echo "      3. Verificar se fallback está funcionando"
fi

echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo ""
echo "   1. Acessar Meta Events Manager → Eventos → Comprar (Purchase)"
echo "      Verificar se eventos estão aparecendo e cobertura de fbc"
echo ""
echo "   2. Acessar Meta Ads Manager → Campanhas"
echo "      Verificar se conversões estão aparecendo"
echo ""
echo "   3. Se vendas estão aparecendo: Sistema está OK (Parameter Builder é otimização)"
echo "   4. Se vendas NÃO estão aparecendo: Investigar e corrigir"
echo ""

