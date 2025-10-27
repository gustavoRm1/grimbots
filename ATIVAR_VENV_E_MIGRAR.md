# 🚀 Como Ativar Venv e Executar Migration

## **Opção 1: Windows (PowerShell)**

```powershell
# 1. Ativar venv
.\venv\Scripts\Activate.ps1

# 2. Executar migration
python migrate_add_demographic_fields.py

# 3. Reiniciar serviço (no VPS)
sudo systemctl restart grimbots
```

## **Opção 2: Linux/VPS (Bash)**

```bash
# 1. Navegar até diretório do projeto
cd /root/grimbots

# 2. Ativar venv
source venv/bin/activate

# 3. Executar migration
python migrate_add_demographic_fields.py

# 4. Reiniciar serviço
sudo systemctl restart grimbots

# 5. Verificar status
sudo systemctl status grimbots
```

## **Opção 3: Script Automático (Linux)**

Criar arquivo `executar_migration.sh`:

```bash
#!/bin/bash
cd /root/grimbots
source venv/bin/activate
python migrate_add_demographic_fields.py
sudo systemctl restart grimbots
echo "✅ Migration executada e serviço reiniciado!"
```

Tornar executável e executar:

```bash
chmod +x executar_migration.sh
./executar_migration.sh
```

