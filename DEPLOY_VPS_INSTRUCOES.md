# 📋 INSTRUÇÕES DE DEPLOY - VPS

**Objetivo:** Deploy das correções de captura de dados demográficos

---

## 1️⃣ COMITAR MUDANÇAS (LOCAL - WINDOWS)

Abra o PowerShell ou Git Bash e execute:

```bash
# Ver o que mudou
git status

# Adicionar todos os arquivos modificados
git add .

# Commit com mensagem descritiva
git commit -m "feat: captura geolocalização e dados adicionais para analytics demográfico"

# Push para o GitHub
git push origin main
```

**Aguarde confirmação:**
```
Enumerating objects: X, done.
Counting objects: 100% (X/X), done.
Writing objects: 100% (X/X), done.
To https://github.com/gustavoRm1/grimbots.git
 * [new branch]      main -> main
```

---

## 2️⃣ FAZER DEPLOY NO VPS

Conecte-se na VPS via SSH:

```bash
ssh root@SEU_IP_VPS
```

### **Passos no VPS:**

```bash
# 1. Ir para o diretório do projeto
cd ~/grimbots

# 2. Fazer pull das mudanças
git pull origin main

# 3. Verificar se há mudanças
# (deve mostrar os arquivos modificados)
git log -1

# 4. Reiniciar o serviço
sudo systemctl restart grimbots

# 5. Verificar logs
sudo journalctl -u grimbots -f --lines=50
```

**✅ Pronto!** O sistema está atualizado e rodando.

---

## 3️⃣ VALIDAR FUNCIONAMENTO

### **Teste 1: Verificar se geolocalização está funcionando**

Crie uma venda de teste via bot e verifique os logs:

```bash
sudo journalctl -u grimbots -f | grep "Geolocalização"
```

**Deve aparecer:**
```
🌍 Geolocalização parseada: {'city': 'São Paulo', 'state': 'São Paulo', 'country': 'BR'}
📱 Device parseado: {'device_type': 'mobile', 'os_type': 'iOS', 'browser': 'Safari'}
```

### **Teste 2: Verificar no analytics**

1. Acesse: `https://SEU_DOMINIO.com/bots/{BOT_ID}/stats`
2. Verifique se os gráficos de **cidades**, **device** e **os** aparecem com dados

---

## 🔧 TROUBLESHOOTING

### **Erro: "git pull" diz "Already up to date"**

**Problema:** Push local não foi feito.

**Solução:**
```bash
# No WINDOWS, volte e faça:
git push origin main
```

Depois tente novamente no VPS.

---

### **Erro: "systemctl: command not found"**

**Problema:** Não está como root ou servidor não usa systemd.

**Solução:**
```bash
# Verificar se está como root
whoami
# Deve retornar: root

# Se não for root, entrar como root:
sudo su -
```

---

### **Erro: "Grimbots failed to restart"**

**Problema:** Erro de sintaxe no código.

**Solução:**
```bash
# Ver logs detalhados
sudo journalctl -u grimbots -n 100 --no-pager

# Verificar erro específico
# Procurar por "Error" ou "Exception"
```

---

## 📊 CHECKLIST FINAL

Após o deploy, verifique:

- [ ] `git pull origin main` executado
- [ ] `sudo systemctl restart grimbots` executado  
- [ ] Logs não mostram erros
- [ ] Venda de teste criada
- [ ] Analytics mostra dados geográficos
- [ ] Analytics mostra device/OS/Browser

---

**🎯 SE TUDO ESTÁ OK:** Sistema 100% funcional para gestor de tráfego!

