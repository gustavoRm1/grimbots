# 🔍 DIAGNÓSTICO - Gunicorn falhando continuamente

## Comandos para diagnosticar o problema

```bash
# 1. Ver logs completos do erro (últimas 100 linhas)
sudo journalctl -u grimbots -n 100 --no-pager

# 2. Ver logs com mais contexto (últimas 200 linhas)
sudo journalctl -u grimbots -n 200 --no-pager | tail -100

# 3. Ver logs desde o último boot
sudo journalctl -u grimbots --since "10 minutes ago" --no-pager

# 4. Verificar status do serviço
sudo systemctl status grimbots.service

# 5. Tentar iniciar manualmente para ver erro completo
cd /root/grimbots
source venv/bin/activate
gunicorn -w 1 -k eventlet -c gunicorn_config.py wsgi:app

# 6. Verificar se há processos duplicados
ps aux | grep gunicorn

# 7. Parar todos os processos Gunicorn
pkill -f gunicorn

# 8. Verificar se há erros de importação
cd /root/grimbots
source venv/bin/activate
python -c "from app import app; print('✅ App importado com sucesso')"

# 9. Verificar se há problemas com ENCRYPTION_KEY
cd /root/grimbots
source venv/bin/activate
python -c "from utils.encryption import encrypt, decrypt; print('✅ ENCRYPTION_KEY OK')"

# 10. Verificar configuração do Gunicorn
cat gunicorn_config.py
```

## Possíveis causas

1. **Erro de importação** - Algum módulo não está sendo importado corretamente
2. **ENCRYPTION_KEY** - Problema com a chave de criptografia
3. **Porta em uso** - Porta 5000 já está em uso
4. **Dependências faltando** - Alguma biblioteca não instalada
5. **Erro de sintaxe** - Erro no código Python
6. **Permissões** - Problema de permissões de arquivo

## Solução rápida

```bash
# 1. Parar serviço
sudo systemctl stop grimbots

# 2. Parar todos os processos Gunicorn
pkill -f gunicorn

# 3. Verificar logs completos
sudo journalctl -u grimbots -n 200 --no-pager

# 4. Tentar iniciar manualmente
cd /root/grimbots
source venv/bin/activate
gunicorn -w 1 -k eventlet -c gunicorn_config.py wsgi:app
```

