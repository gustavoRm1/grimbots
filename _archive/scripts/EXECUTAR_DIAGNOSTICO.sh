#!/bin/bash
# 🔥 EXECUTAR DIAGNÓSTICO - Versão simplificada
# Execute: bash EXECUTAR_DIAGNOSTICO.sh

echo "=========================================="
echo "🔍 DIAGNÓSTICO META PURCHASE TRACKING"
echo "=========================================="
echo ""

# Verificar se está no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Erro: Execute este script no diretório do projeto (~/grimbots)"
    exit 1
fi

# Executar script Python (usa SQLAlchemy - não precisa de senha)
echo "✅ Executando diagnóstico via Python..."
echo ""

python3 diagnostico_meta_purchase.py

echo ""
echo "✅ Diagnóstico completo!"
echo ""
echo "📋 Se quiser salvar em arquivo:"
echo "   python3 diagnostico_meta_purchase.py > diagnostico_output.txt 2>&1"
echo ""

