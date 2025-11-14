# ✅ SOLUÇÃO - ENCRYPTION_KEY sendo cortada (perdendo `=` no final)

## 🔴 Problema Identificado

A `ENCRYPTION_KEY` estava sendo cortada quando terminava com `=`, causando erro:
```
RuntimeError: ENCRYPTION_KEY não configurada!
```

**Causa raiz:**
- O módulo `utils/encryption.py` é importado **ANTES** de `load_dotenv()` ser executado no `app.py`
- Quando `bot_manager.py` importa `gateway_factory.py` → `gateway_atomopay.py` → `utils.validators` → `utils.encryption`, o `ENCRYPTION_KEY` ainda não está no ambiente
- Alguns scripts usavam `cut -d '=' -f2` que pode perder o `=` final em alguns casos

## ✅ Solução Implementada

### 1. Correção em `utils/encryption.py`

O módulo agora **carrega o `.env` diretamente** antes de validar a `ENCRYPTION_KEY`:

```python
# ✅ CRÍTICO: Carregar .env diretamente aqui para garantir que ENCRYPTION_KEY
# seja lida corretamente, mesmo se este módulo for importado antes de load_dotenv()
# no app.py. Isso resolve o problema de chaves que terminam com '=' sendo cortadas.
if not os.environ.get('ENCRYPTION_KEY'):
    # Tentar carregar do .env manualmente
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)  # ✅ split('=', 1) preserva '=' no valor
                        if key.strip() == 'ENCRYPTION_KEY':
                            os.environ['ENCRYPTION_KEY'] = value.strip()
                            break
        except Exception as e:
            # Se falhar, continuar e deixar validação abaixo tratar
            pass
```

**Pontos críticos:**
- ✅ Usa `split('=', 1)` para preservar `=` no valor
- ✅ Carrega **antes** de qualquer validação
- ✅ Funciona mesmo se importado antes de `load_dotenv()`

### 2. Correção em `scripts/diagnostico_purchase_logs.py`

O script também carrega o `.env` antes de importar `app`:

```python
# ✅ CRÍTICO: Carregar .env ANTES de importar app (para ENCRYPTION_KEY)
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)  # ✅ split('=', 1) preserva '=' no valor
                    os.environ[key.strip()] = value.strip()
    except Exception as e:
        print(f"⚠️  Erro ao carregar .env: {e}")
```

## 📋 Verificação

### 1. Verificar se `.env` tem a chave completa:

```bash
cat .env | grep ENCRYPTION_KEY
```

**Deve mostrar:**
```
ENCRYPTION_KEY=9zyoXLwUS3CY4bzTqyB1NzdQWT3R3js7ehgXpssRK_Y=
```

**Importante:** A chave deve terminar com `=` (44 caracteres no total)

### 2. Verificar tamanho da chave:

```bash
grep ENCRYPTION_KEY .env | cut -d '=' -f2 | wc -c
```

**Deve retornar:** `45` (44 chars + 1 newline)

### 3. Testar importação:

```bash
cd /root/grimbots
source venv/bin/activate
python -c "from utils.encryption import encrypt, decrypt; print('✅ ENCRYPTION_KEY carregada corretamente')"
```

**Deve mostrar:** `✅ ENCRYPTION_KEY carregada corretamente`

### 4. Executar script de diagnóstico:

```bash
python scripts/diagnostico_purchase_logs.py
```

**Deve funcionar sem erro de ENCRYPTION_KEY**

## 🔧 Se ainda houver problema

### Opção 1: Regenerar ENCRYPTION_KEY

```bash
cd /root/grimbots
source venv/bin/activate
python utils/encryption.py
```

Isso gerará uma nova chave. **⚠️ ATENÇÃO:** Se você regenerar, todos os dados criptografados (credenciais de gateway) precisarão ser reconfigurados!

### Opção 2: Verificar formato do .env

```bash
# Ver caracteres especiais
cat .env | grep ENCRYPTION_KEY | od -c

# Verificar se há espaços extras
grep ENCRYPTION_KEY .env | cat -A
```

**Deve mostrar:** `ENCRYPTION_KEY=9zyoXLwUS3CY4bzTqyB1NzdQWT3R3js7ehgXpssRK_Y=$`

## ✅ Status

- [x] `utils/encryption.py` corrigido (carrega `.env` diretamente)
- [x] `scripts/diagnostico_purchase_logs.py` corrigido (carrega `.env` antes de importar)
- [x] Usa `split('=', 1)` para preservar `=` no valor
- [x] Funciona mesmo se importado antes de `load_dotenv()`

## 🚀 Próximos Passos

1. ✅ Fazer `git pull` na VPS
2. ✅ Testar importação: `python -c "from utils.encryption import encrypt; print('OK')"`
3. ✅ Executar script de diagnóstico: `python scripts/diagnostico_purchase_logs.py`
4. ✅ Verificar logs de Purchase: `sudo journalctl -u grimbots -n 500 | grep -i purchase`

