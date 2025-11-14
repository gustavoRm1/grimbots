# 🔍 COMANDOS PARA VALIDAR LOGS - PATCH V4.1

## ✅ OPÇÃO 1: Verificar se arquivo de log existe

```bash
# Verificar se o arquivo existe
ls -lh logs/gunicorn.log

# Se não existir, verificar outros locais
ls -lh logs/*.log
ls -lh *.log
```

## ✅ OPÇÃO 2: Usar journalctl (logs do systemd)

```bash
# Ver últimos redirects
sudo journalctl -u grimbots -n 500 | grep -iE "\[META REDIRECT\]" | tail -5

# Ver últimos purchases
sudo journalctl -u grimbots -n 500 | grep -iE "\[META PURCHASE\]" | tail -5

# Verificar se fbc sintético foi gerado (NÃO DEVE APARECER)
sudo journalctl -u grimbots -n 1000 | grep -iE "fbc.*gerado.*fbclid" | tail -3
```

## ✅ OPÇÃO 3: Buscar em todos os logs

```bash
# Buscar em todos os arquivos .log
grep -r "\[META PURCHASE\]" logs/ 2>/dev/null | tail -5

# OU buscar em todo o diretório
find . -name "*.log" -type f -exec grep -l "\[META PURCHASE\]" {} \; | head -5
```

## ✅ OPÇÃO 4: Ver logs em tempo real

```bash
# Se usar systemd
sudo journalctl -u grimbots -f | grep -iE "\[META (REDIRECT|PURCHASE)\]"

# Se usar arquivo de log
tail -f logs/gunicorn.log 2>/dev/null | grep -iE "\[META (REDIRECT|PURCHASE)\]"
```

## ✅ OPÇÃO 5: Buscar sem caracteres especiais

```bash
# Buscar sem colchetes (mais simples)
tail -200 logs/gunicorn.log 2>/dev/null | grep -i "META PURCHASE" | tail -5

# OU buscar qualquer menção a "fbc"
tail -200 logs/gunicorn.log 2>/dev/null | grep -i "fbc" | tail -10
```

## ✅ OPÇÃO 6: Script Python para buscar logs

```bash
cd /root/grimbots
source venv/bin/activate
python -c "
import os
import re
from pathlib import Path

# Buscar arquivos de log
log_files = []
for log_file in Path('logs').glob('*.log'):
    log_files.append(log_file)
if not log_files:
    for log_file in Path('.').glob('*.log'):
        log_files.append(log_file)

if not log_files:
    print('❌ Nenhum arquivo .log encontrado')
    print('   Tentando journalctl...')
    import subprocess
    result = subprocess.run(['journalctl', '-u', 'grimbots', '-n', '500', '--no-pager'], 
                          capture_output=True, text=True)
    lines = result.stdout.split('\n')
    meta_lines = [l for l in lines if 'META PURCHASE' in l or 'META REDIRECT' in l]
    if meta_lines:
        print(f'✅ Encontradas {len(meta_lines)} linhas nos logs do systemd:')
        for line in meta_lines[-5:]:
            print(f'   {line[:150]}')
    else:
        print('❌ Nenhuma linha META encontrada nos logs')
else:
    print(f'✅ Encontrados {len(log_files)} arquivo(s) de log')
    for log_file in log_files:
        print(f'   Analisando: {log_file}')
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                meta_lines = [l for l in lines if 'META PURCHASE' in l or 'META REDIRECT' in l]
                if meta_lines:
                    print(f'   ✅ {len(meta_lines)} linhas encontradas')
                    for line in meta_lines[-3:]:
                        print(f'      {line.strip()[:150]}')
                else:
                    print(f'   ⚠️  Nenhuma linha META encontrada')
        except Exception as e:
            print(f'   ❌ Erro ao ler: {e}')
"
```

## 🎯 COMANDO MAIS SIMPLES (RECOMENDADO)

```bash
# Ver últimas 100 linhas do log e filtrar
tail -100 logs/gunicorn.log 2>/dev/null || sudo journalctl -u grimbots -n 100 --no-pager | grep -i "META"
```

## 📋 SE NADA FUNCIONAR

Execute este comando para ver onde estão os logs:

```bash
# Verificar onde o Gunicorn está escrevendo logs
ps aux | grep gunicorn | grep -v grep

# Verificar configuração do systemd
sudo systemctl status grimbots | head -20

# Verificar último erro do Gunicorn
sudo journalctl -u grimbots -n 50 --no-pager | tail -20
```

