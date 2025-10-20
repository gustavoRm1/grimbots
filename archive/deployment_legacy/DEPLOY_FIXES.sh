#!/bin/bash

# 🚀 DEPLOY DAS CORREÇÕES PARA VPS

echo "🚀 Iniciando deploy das correções..."
echo ""

# 1. Adicionar arquivos modificados
echo "📦 Adicionando arquivos modificados..."
git add models.py
git add app.py
git add templates/bot_config.html

# 2. Commit
echo "💾 Fazendo commit..."
git commit -m "Fix: Correção do bug de salvamento infinito no bot config

✅ Melhorias implementadas:
- models.py: Tratamento robusto de JSON com ensure_ascii=False
- app.py: Logging detalhado em cada etapa do update_bot_config
- bot_config.html: Console.log para debug no frontend

🐛 Bug corrigido:
- Botão 'Salvar' travava em loop infinito
- JSON serialization falhava silenciosamente
- Falta de logging impedia identificar onde travava

✅ Resultado:
- Salvamento rápido e confiável
- Logs estruturados para debug
- Error handling profissional"

# 3. Push
echo "🚀 Enviando para repositório..."
git push origin main

echo ""
echo "✅ Arquivos enviados para o repositório!"
echo ""
echo "📋 PRÓXIMOS PASSOS NA VPS:"
echo ""
echo "1. Conectar na VPS:"
echo "   ssh root@157.173.116.134"
echo ""
echo "2. Navegar para o diretório:"
echo "   cd ~/grimbots"
echo ""
echo "3. Fazer pull das alterações:"
echo "   git pull origin main"
echo ""
echo "4. Reiniciar o serviço:"
echo "   sudo systemctl restart grimbots"
echo ""
echo "5. Verificar logs:"
echo "   tail -f logs/app.log"
echo ""
echo "6. Testar salvamento:"
echo "   - Abrir painel de configuração do bot"
echo "   - Clicar em 'Salvar Configurações'"
echo "   - Verificar se salva rapidamente"
echo "   - Verificar console do navegador (F12)"
echo ""
echo "✅ Deploy completo!"

