# 🚀 GUIA RÁPIDO: CRIAR INSTÂNCIA LXD VIA WEB

**Como criar e configurar uma nova instância no LXD via interface web**

---

## 📦 **1. CRIAR NOVA INSTÂNCIA VIA WEB**

### **Passo 1: Acessar interface web**
- Abra o navegador na sua VPS (ex: `https://IP_DA_VPS:8443`)
- Faça login na interface LXD

### **Passo 2: Criar instância**
1. Clique em **"Instances"** no menu lateral
2. Clique no botão **"Create instance"** ou **"+"**
3. Selecione **"Image"** como origem
4. Clique em **"Select base image"**

### **Passo 3: Escolher imagem**
- **Distribution:** Ubuntu
- **Release:** 22.04 LTS
- **Variant:** jammy
- **Type:** all
- **Source:** Ubuntu
- Clique **"Select"**

### **Passo 4: Configurar instância**
- **Instance name:** `grimbots`
- **Description:** `Container para o projeto grimbots`
- **Base Image:** Ubuntu jammy 22.04 (já preenchido)
- **Instance type:** Container (já selecionado)
- **Profiles:** default (já selecionado)

### **Passo 5: Criar**
- Clique **"Create and start"**
- Aguarde 2-3 minutos para criação

---

## 🔍 **2. VERIFICAR SE FOI CRIADA**

### **Via interface web:**
1. Vá em **"Instances"**
2. Procure por `grimbots`
3. Status deve estar **"Running"**

### **Via terminal (se tiver acesso SSH):**
```bash
# Listar todas instâncias (EXECUTAR NA VPS, NÃO DENTRO DO CONTAINER)
lxc list

# Ver detalhes da instância grimbots (EXECUTAR NA VPS, NÃO DENTRO DO CONTAINER)
lxc info grimbots
```

**⚠️ IMPORTANTE:** Estes comandos `lxc` são executados **NA VPS HOST**, não dentro do container!

---

## 🔌 **3. ENTRAR NA INSTÂNCIA**

### **Via interface web:**
1. Clique na instância `grimbots`
2. Vá na aba **"Console"**
3. Clique **"Open console"**
4. Aguarde carregar o terminal

### **Via SSH (se configurado):**
```bash
# Entrar como root (EXECUTAR NA VPS, NÃO DENTRO DO CONTAINER)
lxc exec grimbots -- bash

# Agora você está DENTRO do container
# Prompt vai mudar para: root@grimbots:~#
```

**⚠️ IMPORTANTE:** O comando `lxc exec` é executado **NA VPS HOST**, não dentro do container!

---

## ⚙️ **4. CONFIGURAR A INSTÂNCIA (DENTRO)**

### **4.1 - Atualizar sistema:**
```bash
apt update && apt upgrade -y
```

### **4.2 - Instalar ferramentas básicas:**
```bash
apt install -y curl wget git unzip nano
```

### **4.3 - Instalar Docker:**
```bash
# Baixar script de instalação
curl -fsSL https://get.docker.com -o get-docker.sh

# Executar instalação
sh get-docker.sh

# Iniciar Docker
systemctl start docker
systemctl enable docker

# Verificar
docker --version
```

### **4.4 - Instalar Docker Compose:**
```bash
# Baixar Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Dar permissão de execução
chmod +x /usr/local/bin/docker-compose

# Verificar
docker-compose --version
```

### **4.5 - Instalar Nginx:**
```bash
apt install -y nginx

# Iniciar
systemctl start nginx
systemctl enable nginx

# Verificar status
systemctl status nginx
```
*Pressione `q` para sair*

### **4.6 - Instalar Certbot (SSL):**
```bash
apt install -y certbot python3-certbot-nginx
```

---

## 📁 **5. ENVIAR ARQUIVOS PARA A INSTÂNCIA**

### **5.1 - Da VPS host para a instância:**
```bash
# Sair da instância primeiro
exit

# Copiar arquivo individual
lxc file push /caminho/arquivo.zip grpay/root/

# Copiar pasta inteira
lxc file push -r /caminho/pasta grpay/root/
```

### **5.2 - Do seu computador para a instância:**

**Passo 1:** Enviar para VPS via WinSCP/SCP
```bash
# No seu Windows (PowerShell)
scp C:\Users\grcon\Downloads\grpay.zip root@IP_DA_VPS:/root/
```

**Passo 2:** Da VPS para instância LXD
```bash
# Na VPS
lxc file push /root/grpay.zip grpay/root/
```

---

## 🌐 **6. EXPOR PORTAS DA INSTÂNCIA**

### **Sintaxe:**
```bash
lxc config device add NOME_INSTANCIA NOME_DEVICE proxy \
  listen=tcp:0.0.0.0:PORTA_HOST \
  connect=tcp:127.0.0.1:PORTA_CONTAINER
```

### **Exemplo prático:**
```bash
# Expor porta 80 do container na porta 8080 da VPS
lxc config device add grpay http proxy \
  listen=tcp:0.0.0.0:8080 \
  connect=tcp:127.0.0.1:80

# Expor porta 443 do container na porta 8443 da VPS
lxc config device add grpay https proxy \
  listen=tcp:0.0.0.0:8443 \
  connect=tcp:127.0.0.1:443

# Verificar
lxc config show grpay
```

**Explicação:**
- Quando acessar `IP_DA_VPS:8080` → vai para porta `80` do container
- Quando acessar `IP_DA_VPS:8443` → vai para porta `443` do container

---

## 🔧 **7. COMANDOS DE GERENCIAMENTO**

### **Parar instância:**
```bash
lxc stop grpay
```

### **Iniciar instância:**
```bash
lxc start grpay
```

### **Reiniciar instância:**
```bash
lxc restart grpay
```

### **Deletar instância:**
```bash
# Para primeiro
lxc stop grpay

# Depois deleta
lxc delete grpay
```

---

## 💾 **8. BACKUP E RESTORE**

### **Criar snapshot (backup):**
```bash
# Criar backup
lxc snapshot grpay backup-2024-10-14

# Listar snapshots
lxc info grpay
```

### **Restaurar snapshot:**
```bash
lxc restore grpay backup-2024-10-14
```

### **Exportar instância completa:**
```bash
# Exportar para arquivo
lxc export grpay grpay-backup.tar.gz

# Importar em outra VPS
lxc import grpay-backup.tar.gz
```

---

## 📊 **9. MONITORAR RECURSOS**

### **Ver uso de recursos:**
```bash
# Todas instâncias
lxc list

# Detalhes de uma instância
lxc info grpay

# Estatísticas em tempo real
lxc monitor grpay
```

### **Ver processos:**
```bash
# Processos dentro da instância
lxc exec grpay -- ps aux

# Top dentro da instância
lxc exec grpay -- top
```

---

## 🔐 **10. LIMITES DE RECURSOS**

### **Definir limites:**
```bash
# Limitar CPU (2 cores)
lxc config set grpay limits.cpu 2

# Limitar RAM (2GB)
lxc config set grpay limits.memory 2GB

# Limitar disco (20GB)
lxc config device override grpay root size=20GB

# Ver configuração
lxc config show grpay
```

---

## 🌍 **11. CONFIGURAR REDE**

### **Ver IP da instância:**
```bash
lxc list grpay
```

### **Configurar IP fixo:**
```bash
lxc config device set grpay eth0 ipv4.address 10.x.x.100
```

---

## 📝 **EXEMPLO COMPLETO: CRIAR INSTÂNCIA GRPAY**

```bash
# 1. Criar instância com limites
lxc launch ubuntu:22.04 grpay \
  -c limits.cpu=2 \
  -c limits.memory=2GB

# 2. Aguardar iniciar (10 segundos)
sleep 10

# 3. Verificar
lxc list grpay

# 4. Entrar na instância
lxc exec grpay -- bash

# 5. Atualizar sistema (DENTRO da instância)
apt update && apt upgrade -y

# 6. Instalar dependências
apt install -y curl wget git unzip nano

# 7. Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker

# 8. Instalar Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 9. Instalar Nginx
apt install -y nginx
systemctl start nginx
systemctl enable nginx

# 10. Instalar Certbot
apt install -y certbot python3-certbot-nginx

# 11. Verificar instalações
docker --version
docker-compose --version
nginx -v
certbot --version

# 12. Criar diretório do projeto
mkdir -p /root/grpay
cd /root/grpay

# 13. Sair da instância
exit

# 14. Copiar projeto da VPS para instância
lxc file push /root/grpay.zip grpay/root/grpay/

# 15. Entrar novamente
lxc exec grpay -- bash

# 16. Descompactar
cd /root/grpay
unzip grpay.zip

# 17. Criar snapshot (backup antes de rodar)
exit
lxc snapshot grpay antes-deploy

# 18. Expor portas
lxc config device add grpay http proxy listen=tcp:0.0.0.0:8080 connect=tcp:127.0.0.1:80
lxc config device add grpay https proxy listen=tcp:0.0.0.0:8443 connect=tcp:127.0.0.1:443

# 19. Pronto! Agora siga o deploy normal
```

---

## 🆘 **SOLUÇÃO DE PROBLEMAS**

### **Erro: "Instance not found"**
```bash
# Verificar nome correto
lxc list

# Criar se não existe
lxc launch ubuntu:22.04 grpay
```

### **Erro: "Container won't start"**
```bash
# Ver logs
lxc info grpay --show-log

# Forçar parar e reiniciar
lxc stop grpay --force
lxc start grpay
```

### **Erro: "Permission denied"**
```bash
# Executar comandos LXD com sudo
sudo lxc list
sudo lxc exec grpay -- bash
```

### **Porta já em uso:**
```bash
# Ver o que está usando a porta
lsof -i :8080

# Mudar porta do proxy
lxc config device remove grpay http
lxc config device add grpay http proxy listen=tcp:0.0.0.0:9080 connect=tcp:127.0.0.1:80
```

---

## 📚 **COMANDOS ÚTEIS DE REFERÊNCIA**

```bash
# Listar imagens disponíveis
lxc image list ubuntu:

# Listar apenas containers rodando
lxc list --format=compact

# Entrar e executar comando direto
lxc exec grpay -- ls -la /root

# Ver logs em tempo real
lxc console grpay

# Copiar arquivo DE dentro DA instância para VPS
lxc file pull grpay/root/backup.sql /root/backups/

# Renomear instância
lxc rename grpay grpay-old

# Clonar instância
lxc copy grpay grpay-clone
```

---

## ✅ **CHECKLIST DE CRIAÇÃO**

- [ ] 1. Criar instância: `lxc launch ubuntu:22.04 grpay`
- [ ] 2. Verificar: `lxc list`
- [ ] 3. Entrar: `lxc exec grpay -- bash`
- [ ] 4. Atualizar: `apt update && apt upgrade -y`
- [ ] 5. Instalar tools: `apt install -y curl wget git unzip nano`
- [ ] 6. Instalar Docker
- [ ] 7. Instalar Docker Compose
- [ ] 8. Instalar Nginx
- [ ] 9. Instalar Certbot
- [ ] 10. Criar snapshot inicial: `lxc snapshot grpay instalado`
- [ ] 11. Expor portas (se necessário)
- [ ] 12. Copiar projeto
- [ ] 13. Fazer deploy

---

## 🎯 **RESUMO RÁPIDO**

```bash
# Criar
lxc launch ubuntu:22.04 grpay

# Entrar
lxc exec grpay -- bash

# Configurar (dentro)
apt update && apt upgrade -y
apt install -y curl wget git unzip nano nginx certbot python3-certbot-nginx
curl -fsSL https://get.docker.com | sh
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Sair
exit

# Expor portas
lxc config device add grpay http proxy listen=tcp:0.0.0.0:8080 connect=tcp:127.0.0.1:80
lxc config device add grpay https proxy listen=tcp:0.0.0.0:8443 connect=tcp:127.0.0.1:443

# Pronto!
lxc list
```

---

**✍️ Guia criado especialmente para LXD - Canonical**

**Tempo total:** 20-30 minutos para configurar tudo

