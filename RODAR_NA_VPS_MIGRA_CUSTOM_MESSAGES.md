# 🚀 MIGRAÇÃO: Adicionar success_message e pending_message

## ❌ **PROBLEMA IDENTIFICADO**

O erro `500 Internal Server Error` acontece porque as colunas `success_message` e `pending_message` **NÃO EXISTEM** na tabela `bot_configs` do banco de dados na VPS!

---

## ✅ **SOLUÇÃO: RODAR MIGRAÇÃO NA VPS**

### **PASSO 1: Acessar VPS via SSH**

```bash
ssh root@SEU_IP_VPS
```

### **PASSO 2: Ir para o diretório do projeto**

```bash
cd /root/grimbots
```

### **PASSO 3: Criar arquivo de migração**

```bash
cat > migrate_fix_custom_messages.py << 'EOF'
"""
Migração: Adicionar campos success_message e pending_message em bot_configs
"""

import sqlite3
import os

def migrate():
    db_path = 'instance/grimbots.db'
    
    if not os.path.exists(db_path):
        print(f"ERRO: Banco de dados nao encontrado: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar colunas atuais
        cursor.execute("PRAGMA table_info(bot_configs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colunas atuais: {columns}")
        
        # Adicionar success_message
        if 'success_message' not in columns:
            print("Adicionando coluna success_message...")
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN success_message TEXT")
            print("OK: Coluna success_message adicionada!")
        else:
            print("Coluna success_message ja existe")
        
        # Adicionar pending_message
        if 'pending_message' not in columns:
            print("Adicionando coluna pending_message...")
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN pending_message TEXT")
            print("OK: Coluna pending_message adicionada!")
        else:
            print("Coluna pending_message ja existe")
        
        conn.commit()
        print("Migracao concluida com sucesso!")
        
        # Verificar novamente
        cursor.execute("PRAGMA table_info(bot_configs)")
        columns_after = [row[1] for row in cursor.fetchall()]
        print(f"Colunas apos migracao: {columns_after}")
        
    except Exception as e:
        print(f"ERRO: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
EOF
```

### **PASSO 4: Executar migração**

```bash
python migrate_fix_custom_messages.py
```

### **PASSO 5: Reiniciar serviço**

```bash
sudo systemctl restart grimbots
```

### **PASSO 6: Verificar logs**

```bash
sudo journalctl -u grimbots -f
```

---

## 🧪 **RESULTADO ESPERADO**

```
Colunas atuais: ['id', 'bot_id', 'welcome_message', 'welcome_media_url', ...]
Adicionando coluna success_message...
OK: Coluna success_message adicionada!
Adicionando coluna pending_message...
OK: Coluna pending_message adicionada!
Migracao concluida com sucesso!
Colunas apos migracao: ['id', 'bot_id', ..., 'success_message', 'pending_message']
```

---

## 🎯 **DEPOIS DA MIGRAÇÃO**

1. **Recarregue a página do bot config**
2. **Abra o Console (F12)**
3. **Deve aparecer:**
   ```
   📊 Response status: 200
   📦 Dados recebidos da API: { ... success_message: '...', pending_message: '...' }
   ✅ Config final carregado com sucesso!
   ```

---

## 🚀 **COMANDOS RESUMIDOS**

```bash
ssh root@SEU_IP_VPS
cd /root/grimbots
# Colar o script acima (cat > ...)
python migrate_fix_custom_messages.py
sudo systemctl restart grimbots
```

---

**✅ ISSO VAI RESOLVER O ERRO 500! 🎯**

