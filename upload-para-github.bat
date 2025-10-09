@echo off
echo.
echo ============================================================
echo  UPLOAD PARA GITHUB - grimbots
echo ============================================================
echo.

REM Verificar se Git esta instalado
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Git nao esta instalado!
    echo.
    echo SOLUCAO:
    echo 1. Acesse: https://git-scm.com/download/win
    echo 2. Baixe e instale o Git
    echo 3. Reinicie o PowerShell
    echo 4. Execute este script novamente
    echo.
    pause
    exit /b 1
)

echo [OK] Git detectado!
echo.

REM Verificar se ja esta inicializado
if exist ".git" (
    echo [INFO] Repositorio Git ja existe, limpando...
    rmdir /s /q .git
)

echo [1/7] Inicializando repositorio Git...
git init
echo.

echo [2/7] Configurando usuario Git...
echo.
set /p git_name="Digite seu nome: "
set /p git_email="Digite seu email: "
git config user.name "%git_name%"
git config user.email "%git_email%"
echo [OK] Usuario configurado!
echo.

echo [3/7] Adicionando arquivos...
git add .
echo [OK] Arquivos adicionados!
echo.

echo Verificando arquivos que serao enviados...
echo.
git status --short
echo.
echo IMPORTANTE: Verifique se NAO aparecem:
echo   - .env
echo   - venv/
echo   - instance/*.db
echo.
pause

echo [4/7] Criando commit...
git commit -m "Initial commit: Bot Manager SaaS - Sistema completo" -m "" -m "Sistema SaaS completo para gestao de bots Telegram" -m "" -m "Funcionalidades:" -m "- Painel web com autenticacao" -m "- Integracao real com SyncPay (PIX)" -m "- Split Payment automatico (R$ 0,75/venda)" -m "- Order Bumps personalizados" -m "- Downsells agendados" -m "- Sistema de Remarketing" -m "- Gamificacao com 29 badges" -m "- Ranking publico com podio" -m "- Painel administrativo" -m "- Dashboard tempo real (WebSocket)" -m "- Analytics com Chart.js" -m "" -m "Tecnologias:" -m "- Backend: Python 3.11, Flask, SQLAlchemy" -m "- Frontend: TailwindCSS, Alpine.js" -m "- Database: PostgreSQL (prod) / SQLite (dev)" -m "- Deploy: Docker + Docker Compose" -m "" -m "Documentacao completa em /docs"
echo [OK] Commit criado!
echo.

echo [5/7] Renomeando branch para main...
git branch -M main
echo [OK] Branch main criada!
echo.

echo [6/7] Conectando ao repositorio GitHub...
git remote add origin https://github.com/gustavoRm1/grimbots.git
echo [OK] Repositorio remoto configurado!
echo.

echo [7/7] Enviando codigo para GitHub...
echo.
echo ============================================================
echo  AUTENTICACAO NECESSARIA
echo ============================================================
echo.
echo O Git vai pedir suas credenciais do GitHub:
echo.
echo Username: gustavoRm1
echo Password: Use um Personal Access Token (NAO a senha)
echo.
echo COMO CRIAR UM TOKEN:
echo 1. Acesse: https://github.com/settings/tokens
echo 2. Clique: "Generate new token" -^> "Classic"
echo 3. Nome: "Bot Manager - Local"
echo 4. Marque: [X] repo (todos os subitens)
echo 5. Clique: "Generate token"
echo 6. COPIE o token (aparece so 1 vez!)
echo 7. Cole aqui como senha
echo.
pause

git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo  SUCESSO! PROJETO NO GITHUB!
    echo ============================================================
    echo.
    echo Acesse: https://github.com/gustavoRm1/grimbots
    echo.
    echo VERIFIQUE:
    echo [OK] README.md aparece na pagina principal
    echo [OK] Pasta /docs com documentacao
    echo [OK] .gitignore e env.example
    echo.
    echo NAO DEVE APARECER:
    echo [X] .env (credenciais)
    echo [X] venv/ (ambiente virtual)
    echo [X] instance/*.db (banco de dados)
    echo.
    echo Se .env aparecer, veja: docs\GITHUB_SETUP.md
    echo para remover do historico e trocar credenciais!
    echo.
) else (
    echo.
    echo ============================================================
    echo  ERRO AO FAZER PUSH
    echo ============================================================
    echo.
    echo Possiveis problemas:
    echo.
    echo 1. CREDENCIAIS INCORRETAS
    echo    - Certifique-se de usar um Personal Access Token
    echo    - Senha comum nao funciona mais no GitHub
    echo.
    echo 2. TOKEN SEM PERMISSOES
    echo    - O token precisa ter permissao "repo"
    echo.
    echo 3. REPOSITORIO JA TEM CONTEUDO
    echo    - Se ja subiu antes, use: git push -f origin main
    echo.
    echo Solucao detalhada: docs\GITHUB_SETUP.md
    echo.
)

pause

