# 📦 GUIA COMPLETO: SUBIR PROJETO NO GITHUB

## ⚠️ PRÉ-REQUISITOS

1. **Instalar Git**
   - Download: https://git-scm.com/download/win
   - Durante instalação: aceitar as opções padrão
   - Reiniciar PowerShell/CMD após instalação

2. **Criar conta no GitHub**
   - Acesse: https://github.com
   - Crie uma conta gratuita

---

## 🔒 SEGURANÇA: VERIFICAÇÕES APLICADAS

✅ **Credenciais hardcoded removidas**
- `PLATFORM_SPLIT_USER_ID` movido para variável de ambiente

✅ **`.gitignore` criado**
- Arquivos sensíveis não serão commitados:
  - `.env` (credenciais)
  - `venv/` (ambiente virtual)
  - `instance/*.db` (banco de dados)
  - `__pycache__/` (cache Python)
  - `*.log` (logs)

✅ **`env.example` criado**
- Template sem credenciais reais

**PROJETO SEGURO PARA GITHUB!** 🔐

---

## 🚀 PASSO A PASSO

### 1. Verificar Instalação do Git

```bash
# Abrir PowerShell/CMD
git --version
```

**Resultado esperado:** `git version 2.x.x`

Se não aparecer, instale: https://git-scm.com/download/win

---

### 2. Configurar Git (Primeira vez)

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu@email.com"
```

---

### 3. Inicializar Repositório Local

```bash
# Navegar até a pasta do projeto
cd C:\Users\grcon\Downloads\grpay

# Inicializar Git
git init

# Verificar status
git status
```

---

### 4. Adicionar Arquivos ao Staging

```bash
# Adicionar todos os arquivos (respeitando .gitignore)
git add .

# Verificar o que será commitado
git status
```

**Verificar se NÃO aparecem:**
- ❌ `.env`
- ❌ `venv/`
- ❌ `instance/saas_bot_manager.db`
- ❌ `__pycache__/`

**Devem aparecer:**
- ✅ `app.py`, `bot_manager.py`, `models.py`
- ✅ `requirements.txt`, `Dockerfile`
- ✅ `README.md`, `.gitignore`, `env.example`
- ✅ `templates/`, `static/`, `docs/`

---

### 5. Fazer o Primeiro Commit

```bash
git commit -m "Initial commit: Bot Manager SaaS - Sistema completo

- Sistema SaaS completo com painel web
- Integração real com SyncPay (PIX)
- Split Payment automático (comissão R$ 0,75/venda)
- Order Bumps personalizados
- Downsells agendados
- Sistema de Remarketing
- Gamificação com 29 badges
- Ranking público
- Painel administrativo
- Dashboard tempo real (WebSocket)
- Analytics com gráficos
- Docker + Docker Compose
- Documentação completa em /docs
- Guia de deploy passo a passo"
```

---

### 6. Criar Repositório no GitHub

#### Opção A: Via Interface Web (RECOMENDADO)

1. Acesse: https://github.com/new
2. Preencha:
   - **Repository name:** `bot-manager-saas`
   - **Description:** `Sistema SaaS completo para gestão de bots Telegram com PIX, gamificação e remarketing`
   - **Visibility:** 
     - ✅ **Private** (RECOMENDADO - código fica privado)
     - ⚠️ Public (código fica público para todos)
   - **NÃO marcar:** "Initialize with README" (já temos)
3. Clicar: **"Create repository"**

#### Opção B: Via GitHub CLI (Avançado)

```bash
gh repo create bot-manager-saas --private --source=. --remote=origin
```

---

### 7. Conectar Repositório Local ao GitHub

Após criar no GitHub, você verá uma página com comandos. Use:

```bash
# Adicionar origem remota (substituir SEU_USUARIO)
git remote add origin https://github.com/SEU_USUARIO/bot-manager-saas.git

# Renomear branch para main (padrão GitHub)
git branch -M main

# Fazer push (enviar código)
git push -u origin main
```

**Na primeira vez**, Git pedirá autenticação:
- **Username:** seu usuário GitHub
- **Password:** use um **Personal Access Token** (não a senha)

---

### 8. Criar Personal Access Token

Se pedir senha:

1. Acesse: https://github.com/settings/tokens
2. Clicar: **"Generate new token"** → **"Classic"**
3. Configurar:
   - **Note:** `Bot Manager SaaS - Local`
   - **Expiration:** `90 days` (ou o que preferir)
   - **Scopes:** Marcar ✅ `repo` (todos os subitens)
4. Clicar: **"Generate token"**
5. **COPIAR O TOKEN** (aparece só 1 vez!)
6. Usar como senha no `git push`

**Salve o token em local seguro!**

---

### 9. Verificar Upload

Acesse: `https://github.com/SEU_USUARIO/bot-manager-saas`

Você deve ver:
- ✅ Todos os arquivos do projeto
- ✅ `README.md` renderizado na página principal
- ✅ Pasta `/docs` com documentação
- ✅ `.gitignore` e `env.example`

**NÃO deve aparecer:**
- ❌ `.env`
- ❌ Pasta `venv/`
- ❌ Banco de dados `.db`

---

## 🔄 COMANDOS ÚTEIS (Futuras Atualizações)

### Atualizar Código no GitHub

```bash
# Ver arquivos modificados
git status

# Adicionar mudanças
git add .

# Commit
git commit -m "Descrição das mudanças"

# Enviar para GitHub
git push
```

### Ver Histórico

```bash
git log --oneline
```

### Desfazer Mudanças Locais

```bash
# Desfazer arquivo específico
git checkout -- arquivo.py

# Desfazer tudo (CUIDADO!)
git reset --hard HEAD
```

---

## 📋 CHECKLIST FINAL

Antes de fazer push, verifique:

- [ ] Git instalado (`git --version`)
- [ ] Git configurado (nome e email)
- [ ] Repositório inicializado (`git init`)
- [ ] Arquivos adicionados (`git add .`)
- [ ] Commit criado (`git commit -m "..."`)
- [ ] Repositório criado no GitHub
- [ ] Repositório PRIVADO marcado ✅
- [ ] Remote configurado (`git remote add origin`)
- [ ] Push realizado (`git push -u origin main`)
- [ ] Verificado no GitHub (`.env` NÃO aparece)

---

## ❓ TROUBLESHOOTING

### Erro: "Git não reconhecido"
**Solução:** Instalar Git e reiniciar PowerShell

### Erro: "Authentication failed"
**Solução:** Usar Personal Access Token ao invés de senha

### Erro: "Remote already exists"
**Solução:**
```bash
git remote remove origin
git remote add origin https://github.com/SEU_USUARIO/bot-manager-saas.git
```

### Arquivo `.env` apareceu no GitHub
**⚠️ URGENTE - SOLUÇÃO:**
```bash
# Remover do histórico
git rm --cached .env
git commit -m "Remove .env from repository"
git push

# Trocar TODAS as credenciais do .env
# (porque já foram expostas)
```

---

## 🔐 CONFIGURAR VARIÁVEIS DE AMBIENTE NO GITHUB

Para deploy via GitHub Actions (futuro):

1. Acesse: `Settings` → `Secrets and variables` → `Actions`
2. Clicar: `New repository secret`
3. Adicionar cada variável do `.env`:
   - `SECRET_KEY`
   - `SYNCPAY_CLIENT_ID`
   - `SYNCPAY_CLIENT_SECRET`
   - `PLATFORM_SPLIT_USER_ID`
   - etc.

---

## 🎉 PRÓXIMOS PASSOS

Após subir no GitHub:

1. ✅ Código versionado e seguro
2. ✅ Backup na nuvem
3. ✅ Histórico de mudanças
4. 🚀 Pronto para deploy em servidor
5. 📦 Fácil de clonar em outro computador

---

**Precisa de ajuda?** Consulte:
- Git Docs: https://git-scm.com/doc
- GitHub Guides: https://guides.github.com

---

**🎊 PROJETO PRONTO PARA GITHUB!**

