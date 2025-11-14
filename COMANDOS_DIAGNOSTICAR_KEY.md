# 🔍 DIAGNÓSTICO - ENCRYPTION_KEY

## Problema
A `ENCRYPTION_KEY` está sendo rejeitada como inválida, mesmo após as correções.

## ✅ EXECUTAR DIAGNÓSTICO

```bash
cd ~/grimbots
source venv/bin/activate
python3 scripts/diagnosticar_encryption_key.py
```

Este script irá:
1. ✅ Verificar se `ENCRYPTION_KEY` está no ambiente
2. ✅ Verificar se existe no `.env`
3. ✅ Extrair e limpar a chave
4. ✅ Validar o formato Fernet
5. ✅ Testar encriptação/desencriptação
6. ✅ Mostrar diagnóstico detalhado de problemas

---

## 🔍 VERIFICAÇÃO MANUAL

### 1. Verificar conteúdo do .env

```bash
cat .env | grep ENCRYPTION_KEY
```

**Resultado esperado:**
```
ENCRYPTION_KEY=9zyoXLwUS3CY4bzTqyB1NzdQWT3R3js7ehgXpssRK_Y=
```

### 2. Verificar se há caracteres invisíveis

```bash
cat .env | grep ENCRYPTION_KEY | od -c
```

### 3. Verificar tamanho da chave

```bash
grep ENCRYPTION_KEY .env | cut -d '=' -f2 | wc -c
```

**Resultado esperado:** 45 (44 chars da chave + 1 newline)

### 4. Testar chave manualmente

```bash
python3 << 'EOF'
from cryptography.fernet import Fernet
key = '9zyoXLwUS3CY4bzTqyB1NzdQWT3R3js7ehgXpssRK_Y='
try:
    fernet = Fernet(key.encode())
    print('✅ Chave válida')
    # Testar encriptação
    test = b"test"
    encrypted = fernet.encrypt(test)
    decrypted = fernet.decrypt(encrypted)
    if decrypted == test:
        print('✅ Teste de encriptação OK')
    else:
        print('❌ Teste de encriptação falhou')
except Exception as e:
    print(f'❌ Erro: {e}')
EOF
```

---

## 🚨 SOLUÇÃO SE A CHAVE ESTIVER CORROMPIDA

### 1. Gerar Nova Chave

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Atualizar .env

```bash
# Fazer backup
cp .env .env.backup

# Editar .env
nano .env
# Substituir a linha ENCRYPTION_KEY=... pela nova chave
```

### 3. Verificar

```bash
python3 scripts/diagnosticar_encryption_key.py
```

---

## 📋 CHECKLIST

- [ ] Executar script de diagnóstico
- [ ] Verificar se chave está no .env
- [ ] Verificar tamanho da chave (deve ser 44 chars)
- [ ] Verificar se há caracteres inválidos
- [ ] Testar chave manualmente
- [ ] Se corrompida, gerar nova chave
- [ ] Atualizar .env com nova chave
- [ ] Executar análise novamente

---

**Status:** 🔍 **Aguardando diagnóstico**  
**Próximo:** Executar script de diagnóstico para identificar o problema exato

