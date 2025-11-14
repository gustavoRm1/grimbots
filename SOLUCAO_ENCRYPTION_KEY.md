# 🔧 SOLUÇÃO - ERRO ENCRYPTION_KEY
## Como resolver o erro de ENCRYPTION_KEY

**Erro:** `RuntimeError: ENCRYPTION_KEY não configurada!`

---

## ⚡ SOLUÇÃO RÁPIDA

### Opção 1: Usar Script Direto (Recomendado)
```bash
cd ~/grimbots
source venv/bin/activate
python scripts/verificar_transacoes_umbrella_direto.py
```

**Este script não depende do app.py e acessa o banco diretamente.**

---

### Opção 2: Configurar ENCRYPTION_KEY

#### 1. Verificar se existe no .env
```bash
grep ENCRYPTION_KEY .env
```

#### 2. Se não existir, gerar uma nova
```bash
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
```

#### 3. Carregar no ambiente
```bash
export ENCRYPTION_KEY=$(grep ENCRYPTION_KEY .env | cut -d '=' -f2)
```

#### 4. Executar script
```bash
python scripts/verificar_transacoes_umbrella.py
```

---

## 🚀 RECOMENDAÇÃO

**Use o script direto** (`verificar_transacoes_umbrella_direto.py`) que:
- ✅ Não depende do app.py
- ✅ Acessa o banco diretamente
- ✅ Não precisa de ENCRYPTION_KEY
- ✅ Mais rápido e simples

---

**Status:** ✅ **Solução Pronta**  
**Próximo:** Executar `verificar_transacoes_umbrella_direto.py`

