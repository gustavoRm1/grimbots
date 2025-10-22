#!/bin/bash

# Script para implementar solução híbrida - mensagens de texto reiniciam funil
# Execute na VPS

echo "🔧 IMPLEMENTANDO SOLUÇÃO HÍBRIDA - MENSAGENS DE TEXTO REINICIAM FUNIL"
echo "=================================================================="

# 1. Backup
echo "📁 Fazendo backup do bot_manager.py..."
cp bot_manager.py bot_manager.py.backup.$(date +%Y%m%d_%H%M%S)

# 2. Commit da implementação
echo "💾 Commitando solução híbrida..."
git add bot_manager.py
git commit -m "SOLUCAO HIBRIDA: Mensagens de texto reiniciam funil com proteções

- Usuários podem digitar qualquer mensagem para reiniciar o funil
- Proteções implementadas:
  * Rate limiting (max 1 msg/minuto)
  * Não envia Meta Pixel ViewContent (evita duplicação)
  * Logs diferenciados para análise
- Melhora experiência do usuário
- Mantém integridade do tracking

Fixes: Usuários podem reiniciar funil com qualquer mensagem"

# 3. Push
echo "🚀 Enviando para repositório..."
git push origin main

# 4. Reiniciar serviço
echo "🔄 Reiniciando serviço..."
sudo systemctl restart grimbots

# 5. Verificar status
echo "✅ Verificando status do serviço..."
sudo systemctl status grimbots --no-pager -l

echo ""
echo "✅ SOLUÇÃO HÍBRIDA IMPLEMENTADA!"
echo "📋 Agora:"
echo "   ✅ Usuário digita /start → Recebe mensagem + Meta Pixel"
echo "   ✅ Usuário digita qualquer texto → Recebe mensagem (sem Meta Pixel)"
echo "   ✅ Rate limiting: máximo 1 mensagem por minuto"
echo "   ✅ Proteção contra spam e duplicação"
echo ""
echo "🎯 Teste:"
echo "   1. Digite /start no bot"
echo "   2. Digite 'oi' ou qualquer texto"
echo "   3. Digite outra mensagem rapidamente (deve ser bloqueada)"
echo ""
echo "📊 Monitore: tail -f logs/app.log | grep -E '(START|MENSAGEM DE TEXTO)'"
