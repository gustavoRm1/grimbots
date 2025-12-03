# 🔥 COMO EXECUTAR DIAGNÓSTICO NA VPS

## 📋 OPÇÃO 1: Script Python (RECOMENDADO - Mais fácil)

```bash
cd ~/grimbots
python3 diagnostico_meta_purchase.py > diagnostico_output.txt 2>&1
```

**Isso funciona porque o script Python usa SQLAlchemy (via Flask app), que já tem as credenciais configuradas.**

---

## 📋 OPÇÃO 2: Script Shell com variáveis de ambiente

```bash
cd ~/grimbots
export PGPASSWORD="123sefudeu"
export DB_NAME="grimbots"
export DB_USER="postgres"
export DB_HOST="localhost"
chmod +x diagnostico_meta_purchase.sh
./diagnostico_meta_purchase.sh > diagnostico_output.txt 2>&1
```

---

## 📋 OPÇÃO 3: Script Shell com arquivo .pgpass

```bash
# Criar arquivo .pgpass
echo "localhost:5432:grimbots:postgres:123sefudeu" > ~/.pgpass
chmod 600 ~/.pgpass

# Executar script
cd ~/grimbots
chmod +x diagnostico_meta_purchase.sh
./diagnostico_meta_purchase.sh > diagnostico_output.txt 2>&1
```

---

## ✅ RECOMENDAÇÃO

**Use a OPÇÃO 1 (Python)** - É mais fácil e usa as credenciais já configuradas no Flask.

Após executar, envie o arquivo `diagnostico_output.txt`.

