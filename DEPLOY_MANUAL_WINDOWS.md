# 🚀 DEPLOY MANUAL - WINDOWS PARA VPS

## ⚠️ **VOCÊ PRECISA FAZER DEPLOY!**

### **Arquivos Modificados:**
- ✅ `models.py` - Tratamento robusto de JSON
- ✅ `app.py` - Logging detalhado
- ✅ `templates/bot_config.html` - Console logs para debug

---

## 📋 **PASSO A PASSO (WINDOWS)**

### **1. COPIAR ARQUIVOS PARA VPS**

Você tem 2 opções:

#### **Opção A: Usar Git (Recomendado)**

Se você tem acesso ao Git Bash ou Git instalado:

```bash
# No Git Bash (Windows)
cd /c/Users/grcon/Downloads/grpay

# Adicionar arquivos
git add models.py app.py templates/bot_config.html

# Commit
git commit -m "Fix: Correção do bug de salvamento infinito"

# Push
git push origin main
```

Depois na VPS:
```bash
# Conectar na VPS
ssh root@157.173.116.134

# Navegar para o diretório
cd ~/grimbots

# Fazer pull
git pull origin main

# Reiniciar serviço
sudo systemctl restart grimbots

# Verificar logs
tail -f logs/app.log
```

---

#### **Opção B: Copiar Arquivos Manualmente (SCP/SFTP)**

Se você não tem Git, pode copiar os arquivos usando WinSCP ou similar:

1. **Abrir WinSCP** (ou FileZilla)
2. **Conectar na VPS:**
   - Host: `157.173.116.134`
   - User: `root`
   - Password: `(sua senha)`

3. **Copiar arquivos:**
   - `models.py` → `/root/grimbots/models.py`
   - `app.py` → `/root/grimbots/app.py`
   - `templates/bot_config.html` → `/root/grimbots/templates/bot_config.html`

4. **No terminal SSH da VPS:**
```bash
# Reiniciar serviço
sudo systemctl restart grimbots

# Verificar logs
tail -f logs/app.log
```

---

#### **Opção C: Copiar e Colar (Mais Trabalhoso)**

1. **Conectar na VPS via SSH:**
```bash
ssh root@157.173.116.134
```

2. **Editar cada arquivo:**

```bash
# Navegar para o diretório
cd ~/grimbots

# Backup dos arquivos originais
cp models.py models.py.backup
cp app.py app.py.backup
cp templates/bot_config.html templates/bot_config.html.backup

# Editar models.py
nano models.py
# (Cole o conteúdo novo do arquivo)
# Ctrl+O para salvar, Ctrl+X para sair

# Editar app.py
nano app.py
# (Cole o conteúdo novo do arquivo)
# Ctrl+O para salvar, Ctrl+X para sair

# Editar templates/bot_config.html
nano templates/bot_config.html
# (Cole o conteúdo novo do arquivo)
# Ctrl+O para salvar, Ctrl+X para sair
```

3. **Reiniciar serviço:**
```bash
sudo systemctl restart grimbots
tail -f logs/app.log
```

---

## 🧪 **TESTAR APÓS DEPLOY**

1. **Abrir navegador:**
   - Acessar: `https://app.grimbots.online/`

2. **Ir para configuração do bot:**
   - Selecionar um bot
   - Ir para "Configurações"

3. **Abrir console do navegador:**
   - Pressionar `F12`
   - Ir para aba "Console"

4. **Clicar em "Salvar Configurações"**

5. **Verificar logs no console:**
   ```
   🔄 Iniciando salvamento de configuração...
   📊 Dados a serem enviados: {...}
   📡 Resposta recebida: 200 OK
   📊 Dados da resposta: {...}
   ✅ Configurações salvas com sucesso!
   🏁 Finalizando salvamento...
   ```

6. **Verificar notificação:**
   - Deve aparecer: "✅ Configurações salvas!"

---

## ✅ **VERIFICAÇÃO DE SUCESSO**

### **Backend (Logs da VPS):**
```bash
tail -f logs/app.log
```

Deve mostrar:
```
🔄 Iniciando atualização de config para bot X
📊 Dados recebidos: [...]
🔘 Salvando N botões principais
✅ Botões principais salvos com sucesso
💾 Fazendo commit no banco de dados...
✅ Commit realizado com sucesso
✅ Configuração do bot X atualizada por user@email.com
```

### **Frontend (Console do Navegador):**
```
🔄 Iniciando salvamento de configuração...
📡 Resposta recebida: 200 OK
✅ Configurações salvas com sucesso!
```

---

## 🚨 **SE NÃO FUNCIONAR**

1. **Verificar logs de erro:**
```bash
tail -100 logs/app.log | grep ERROR
```

2. **Verificar status do serviço:**
```bash
sudo systemctl status grimbots
```

3. **Reiniciar serviço novamente:**
```bash
sudo systemctl restart grimbots
```

4. **Verificar se arquivos foram copiados:**
```bash
ls -la models.py app.py templates/bot_config.html
```

---

## 💡 **DICA PRO**

Se você usa **Visual Studio Code**, pode usar a extensão **Remote - SSH**:

1. Instalar extensão "Remote - SSH"
2. Conectar na VPS direto pelo VSCode
3. Editar arquivos diretamente na VPS
4. Reiniciar serviço pelo terminal integrado

---

# ✅ **RESUMO**

**SIM, VOCÊ PRECISA FAZER DEPLOY!**

**Arquivos modificados:**
- `models.py`
- `app.py`
- `templates/bot_config.html`

**Escolha uma das 3 opções acima e faça o deploy AGORA!** 🚀

