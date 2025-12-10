#!/bin/bash
# Script para corrigir VAPID_PRIVATE_KEY no .env (garantir que está em uma linha)
# Execute: bash fix_vapid_env.sh

set -e

echo "=========================================="
echo "  CORREÇÃO DE VAPID_PRIVATE_KEY NO .env"
echo "=========================================="
echo ""

if [ ! -f ".env" ]; then
    echo "❌ Arquivo .env não encontrado!"
    exit 1
fi

# Backup
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup criado"

# Verificar se VAPID_PRIVATE_KEY existe e tem múltiplas linhas
if grep -q "^VAPID_PRIVATE_KEY=" .env; then
    echo "🔍 Encontrado VAPID_PRIVATE_KEY no .env"
    
    # Remover linhas antigas de VAPID_PRIVATE_KEY (pode ter múltiplas linhas)
    python3 << 'PYEOF'
import re
from pathlib import Path

env_path = Path('.env')
if not env_path.exists():
    exit(1)

# Ler conteúdo
with open(env_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remover VAPID_PRIVATE_KEY antiga (pode ter múltiplas linhas)
# Pattern: VAPID_PRIVATE_KEY=... seguido de linhas que não começam com letra maiúscula e =
lines = content.split('\n')
new_lines = []
skip_next_lines = False
skip_until_next_var = False

for i, line in enumerate(lines):
    if line.strip().startswith('VAPID_PRIVATE_KEY='):
        # Encontrar início da chave privada
        skip_until_next_var = True
        # Pegar apenas a primeira parte (antes de qualquer quebra)
        if '=' in line:
            key_part = line.split('=', 1)[0] + '='
            # Se a linha contém \n literal, manter
            value_part = line.split('=', 1)[1] if '=' in line else ''
            if '\\n' in value_part:
                # Já está em formato correto
                new_lines.append(line)
                skip_until_next_var = False
            else:
                # Precisa ler até encontrar próxima variável
                skip_until_next_var = True
                continue
        else:
            skip_until_next_var = True
            continue
    elif skip_until_next_var:
        # Verificar se é próxima variável (linha que começa com LETRA_MAIÚSCULA=)
        if re.match(r'^[A-Z_][A-Z0-9_]*=', line.strip()):
            skip_until_next_var = False
            new_lines.append(line)
        # Caso contrário, ignorar (era continuação da chave privada)
        continue
    else:
        new_lines.append(line)

# Remover linhas vazias duplicadas
final_lines = []
for i, line in enumerate(new_lines):
    if i == 0 or not (line.strip() == '' and new_lines[i-1].strip() == ''):
        final_lines.append(line)

content = '\n'.join(final_lines)

# Se ainda não tem VAPID_PRIVATE_KEY correta, ler do private_key.pem
if 'private_key.pem' in Path('.').iterdir():
    with open('private_key.pem', 'r') as f:
        pem_content = f.read().strip()
    
    # Converter quebras de linha reais para \n literal
    pem_one_line = pem_content.replace('\n', '\\n')
    
    # Adicionar VAPID_PRIVATE_KEY corretamente
    if 'VAPID_PRIVATE_KEY=' not in content:
        content += f"\nVAPID_PRIVATE_KEY={pem_one_line}\n"
    else:
        # Substituir
        content = re.sub(
            r'VAPID_PRIVATE_KEY=.*',
            f'VAPID_PRIVATE_KEY={pem_one_line}',
            content,
            flags=re.DOTALL
        )

# Salvar
with open(env_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ VAPID_PRIVATE_KEY corrigida (formato de uma linha com \\n)")
PYEOF

else
    echo "⚠️ VAPID_PRIVATE_KEY não encontrada no .env"
    echo "   Execute INSTALL_VAPID_KEYS.sh primeiro"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ CORREÇÃO CONCLUÍDA!"
echo "=========================================="
echo ""
echo "📝 Verificar:"
echo "   grep VAPID_PRIVATE_KEY .env | head -c 100"
echo ""
echo "🔄 Próximo passo:"
echo "   ./restart-app.sh"
echo ""
