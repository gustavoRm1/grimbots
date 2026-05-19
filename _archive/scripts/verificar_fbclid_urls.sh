#!/bin/bash
# Script para verificar se URLs de redirect têm fbclid

echo "🔍 VERIFICANDO SE URLs TÊM fbclid"
echo "=================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ ERRO: Execute este script do diretório raiz do projeto (onde está app.py)"
    exit 1
fi

echo "1️⃣ Verificando logs recentes por fbclid (últimos 500 linhas)..."
echo ""

# Buscar ocorrências de fbclid nos logs
FBCLID_ENCONTRADOS=$(tail -500 logs/gunicorn.log 2>/dev/null | grep -c "fbclid" 2>/dev/null || echo "0")
FBCLID_PARAM_BUILDER=$(tail -500 logs/gunicorn.log 2>/dev/null | grep -c "fbclid encontrado nos args" 2>/dev/null || echo "0")
FBCLID_NAO_ENCONTRADO=$(tail -500 logs/gunicorn.log 2>/dev/null | grep -c "fbclid não encontrado nos args" 2>/dev/null || echo "0")

# Normalizar variáveis
FBCLID_ENCONTRADOS=$(printf '%s' "${FBCLID_ENCONTRADOS}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
FBCLID_PARAM_BUILDER=$(printf '%s' "${FBCLID_PARAM_BUILDER}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")
FBCLID_NAO_ENCONTRADO=$(printf '%s' "${FBCLID_NAO_ENCONTRADO}" | tr -d ' \n\r' | grep -oE '^[0-9]+$' || echo "0")

echo "   📊 Estatísticas:"
echo "      Total de ocorrências de 'fbclid' nos logs: ${FBCLID_ENCONTRADOS}"
echo "      fbclid encontrado pelo Parameter Builder: ${FBCLID_PARAM_BUILDER}"
echo "      fbclid NÃO encontrado: ${FBCLID_NAO_ENCONTRADO}"
echo ""

if [ "${FBCLID_PARAM_BUILDER}" -gt 0 ] 2>/dev/null; then
    echo "   ✅ URLs COM fbclid detectadas!"
    echo ""
    echo "   Últimas ocorrências:"
    tail -500 logs/gunicorn.log 2>/dev/null | grep "fbclid encontrado nos args" | tail -5 | sed 's/^/      /'
elif [ "${FBCLID_NAO_ENCONTRADO}" -gt 0 ] 2>/dev/null; then
    echo "   ⚠️ URLs SEM fbclid detectadas!"
    echo ""
    echo "   Últimas ocorrências:"
    tail -500 logs/gunicorn.log 2>/dev/null | grep "fbclid não encontrado nos args" | tail -5 | sed 's/^/      /'
else
    echo "   ⚠️ Nenhuma ocorrência de fbclid encontrada nos logs recentes"
    echo "   Isso pode significar que:"
    echo "      - URLs não têm fbclid"
    echo "      - Ou eventos ainda não foram processados"
fi

echo ""
echo "2️⃣ Verificando logs do Parameter Builder (últimas 30 ocorrências)..."
echo ""

# Buscar logs detalhados do Parameter Builder
PARAM_BUILDER_LOGS=$(tail -1000 logs/gunicorn.log 2>/dev/null | grep -E "PARAM BUILDER.*fbc|PARAM BUILDER.*fbclid" | tail -10)

if [ -n "${PARAM_BUILDER_LOGS}" ]; then
    echo "   Últimos logs do Parameter Builder relacionados a fbc/fbclid:"
    echo "${PARAM_BUILDER_LOGS}" | sed 's/^/      /'
else
    echo "   ⚠️ Nenhum log do Parameter Builder relacionado a fbc/fbclid encontrado"
fi

echo ""
echo "3️⃣ Verificando eventos PageView recentes..."
echo ""

# Buscar eventos PageView recentes
PAGEVIEW_RECENTES=$(tail -200 logs/gunicorn.log 2>/dev/null | grep "META PAGEVIEW.*PageView -" | tail -5)

if [ -n "${PAGEVIEW_RECENTES}" ]; then
    echo "   Últimos eventos PageView:"
    echo "${PAGEVIEW_RECENTES}" | sed 's/^/      /'
    
    # Contar quantos têm fbc
    PAGEVIEW_COM_FBC=$(echo "${PAGEVIEW_RECENTES}" | grep -c "fbc processado pelo Parameter Builder\|fbc REAL confirmado" 2>/dev/null || echo "0")
    PAGEVIEW_SEM_FBC=$(echo "${PAGEVIEW_RECENTES}" | grep -c "fbc NÃO retornado\|fbc ausente" 2>/dev/null || echo "0")
    
    echo ""
    echo "   📊 Dos últimos 5 eventos:"
    echo "      Com fbc: ${PAGEVIEW_COM_FBC}"
    echo "      Sem fbc: ${PAGEVIEW_SEM_FBC}"
else
    echo "   ⚠️ Nenhum evento PageView recente encontrado"
fi

echo ""
echo "=================================="
echo "✅ Verificação concluída!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "   1. Se URLs não têm fbclid: Adicionar fbclid nas URLs de redirect do Meta Ads"
echo "   2. Se fbclid está presente mas fbc não está sendo gerado: Verificar Client-Side Parameter Builder"
echo "   3. Executar: tail -f logs/gunicorn.log | grep -E 'PARAM BUILDER|fbclid' para ver logs em tempo real"
echo ""

