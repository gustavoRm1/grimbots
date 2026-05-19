#!/bin/bash

echo "🔄 Executando migration: add_flow_start_step_id.py"
echo ""

python3 migrations/add_flow_start_step_id.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration executada com sucesso!"
    echo ""
    echo "📋 Próximos passos:"
    echo "   1. Verifique se o campo flow_start_step_id foi adicionado"
    echo "   2. Reinicie a aplicação se necessário"
else
    echo ""
    echo "❌ Erro ao executar migration!"
    exit 1
fi

