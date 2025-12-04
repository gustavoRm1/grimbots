# 🔄 Sincronização bot_config.html

## 📋 Workflow Completo

### 1️⃣ **BAIXAR DO SERVIDOR** (quando começar a trabalhar)
```bash
bash sync_from_server.sh
```
- Baixa a versão atual do servidor
- Faz backup automático da versão local (se existir)
- Pronto para editar no Cursor

### 2️⃣ **EDITAR LOCALMENTE**
- Edite no Cursor normalmente
- Faça as mudanças necessárias
- Teste mentalmente/valide

### 3️⃣ **ENVIAR PARA O SERVIDOR** (quando terminar)
```bash
bash sync_to_server.sh
```
- Envia sua versão local para o servidor
- Faz backup automático no servidor antes de sobrescrever
- Depois reinicie o Flask no servidor

### 4️⃣ **REINICIAR NO SERVIDOR** (após enviar)
```bash
# No servidor
sudo systemctl restart grimbots
# ou
sudo supervisorctl restart grimbots
```

## ⚙️ Configuração

Edite os scripts se necessário:
- `SERVER_USER`: usuário SSH (padrão: `root`)
- `SERVER_HOST`: hostname do servidor (padrão: `app.grimbots.online`)
- `SERVER_PATH`: caminho no servidor (padrão: `/root/grimbots/templates/bot_config.html`)

## 🛡️ Proteção no Servidor

O servidor está configurado com `skip-worktree`, então:
- ✅ O arquivo não será sobrescrito por `git pull`
- ✅ Suas edições locais podem ser enviadas via SCP normalmente
- ✅ O servidor sempre usa a versão que você enviar

## 📝 Exemplo de Uso

```bash
# 1. Começar trabalho: baixar do servidor
bash sync_from_server.sh

# 2. Editar no Cursor
# ... fazer edições ...

# 3. Terminar: enviar para servidor
bash sync_to_server.sh

# 4. No servidor: reiniciar Flask
ssh root@app.grimbots.online "sudo systemctl restart grimbots"
```

## ✅ Vantagens

- 🚀 Simples e direto
- 💾 Backup automático
- 🔄 Sincronização garantida
- 🛡️ Servidor protegido de git pull

