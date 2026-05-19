#!/bin/bash
# Script rápido para corrigir VAPID_PRIVATE_KEY no .env
# Garante que está em formato de uma linha com \n literal

if [ ! -f ".env" ]; then
    echo "❌ Arquivo .env não encontrado"
    exit 1
fi

# Backup
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Usar Python para corrigir
python3 << 'PYEOF'
import re
from pathlib import Path

env_path = Path('.env')
content = env_path.read_text(encoding='utf-8')

# Remover VAPID_PRIVATE_KEY antiga (pode estar em múltiplas linhas)
# Remover da linha que começa com VAPID_PRIVATE_KEY= até encontrar próxima variável ou fim
lines = content.split('\n')
new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # Se é VAPID_PRIVATE_KEY
    if line.strip().startswith('VAPID_PRIVATE_KEY='):
        # Pegar valor (pode ter \n literal ou quebras reais)
        key_part = line.split('=', 1)[0] + '='
        value_part = line.split('=', 1)[1] if '=' in line else ''
        
        # Se já tem \n literal, manter como está
        if '\\n' in value_part:
            new_lines.append(key_part + value_part)
        else:
            # Coletar valor completo até próxima variável
            value_parts = [value_part]
            i += 1
            while i < len(lines):
                next_line = lines[i]
                # Se próxima linha começa com letra maiúscula e =, parar
                if re.match(r'^[A-Z_][A-Z0-9_]*=', next_line.strip()):
                    break
                # Se é linha vazia ou comentário, também parar
                if next_line.strip() == '' or next_line.strip().startswith('#'):
                    break
                # Caso contrário, é continuação do valor
                value_parts.append(next_line)
                i += 1
            
            # Juntar todas as partes e converter quebras reais para \n literal
            full_value = '\n'.join(value_parts).strip()
            # Converter quebras reais para \n literal
            full_value = full_value.replace('\n', '\\n').replace('\r', '')
            new_lines.append(key_part + full_value)
            continue
    else:
        new_lines.append(line)
    
    i += 1

# Se ainda não tem VAPID_PRIVATE_KEY e existe private_key.pem, adicionar
if 'VAPID_PRIVATE_KEY=' not in '\n'.join(new_lines):
    pem_path = Path('private_key.pem')
    if pem_path.exists():
        pem_content = pem_path.read_text(encoding='utf-8').strip()
        pem_one_line = pem_content.replace('\n', '\\n')
        new_lines.append(f"VAPID_PRIVATE_KEY={pem_one_line}")

# Salvar
env_path.write_text('\n'.join(new_lines), encoding='utf-8')
print("✅ VAPID_PRIVATE_KEY corrigida no .env (formato de uma linha)")
PYEOF

echo ""
echo "✅ Correção aplicada! Agora execute:"
echo "   ./restart-app.sh"
echo ""
