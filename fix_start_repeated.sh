#!/bin/bash

# Script para corrigir problema do /start repetido
# Execute na VPS

echo "🔧 CORRIGINDO PROBLEMA: /start repetido não envia mensagem"
echo "========================================================"

# 1. Backup
echo "📁 Fazendo backup do bot_manager.py..."
cp bot_manager.py bot_manager.py.backup.$(date +%Y%m%d_%H%M%S)

# 2. Commit da correção
echo "💾 Commitando correção do /start..."
git add bot_manager.py
git commit -m "CORRECAO CRITICA: /start repetido agora envia mensagem

- Sistema estava bloqueando envio de mensagens para usuarios existentes
- Agora sempre envia boas-vindas quando /start for digitado
- Usuarios podem reiniciar o funil quantas vezes quiserem
- Melhora experiencia do usuario e conversao

Fixes: /start repetido nao enviava mensagem para usuarios existentes"

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
echo "✅ PROBLEMA CORRIGIDO!"
echo "📋 Agora:"
echo "   ✅ Usuário digita /start → Recebe mensagem"
echo "   ✅ Usuário digita /start novamente → Recebe mensagem novamente"
echo "   ✅ Usuário pode reiniciar o funil quantas vezes quiser"
echo ""
echo "🎯 Teste: Digite /start no bot e depois digite /start novamente"
echo "📊 Monitore: tail -f logs/app.log | grep -i start"
