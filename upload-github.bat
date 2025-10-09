@echo off
echo.
echo ============================================================
echo  UPLOAD AUTOMATICO PARA GITHUB
echo ============================================================
echo.

REM Verificar se Git esta instalado
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Git nao esta instalado!
    echo.
    echo Por favor, instale Git primeiro:
    echo https://git-scm.com/download/win
    echo.
    echo Apos instalar, execute este script novamente.
    echo.
    pause
    exit /b 1
)

echo [OK] Git detectado!
echo.

REM Verificar se ja esta inicializado
if exist ".git" (
    echo [INFO] Repositorio Git ja inicializado
) else (
    echo [1/6] Inicializando repositorio Git...
    git init
    echo [OK] Repositorio inicializado!
    echo.
)

echo [2/6] Adicionando arquivos ao staging...
git add .
echo [OK] Arquivos adicionados!
echo.

echo [3/6] Criando commit...
git commit -m "Initial commit: Bot Manager SaaS - Sistema completo de gestao de bots Telegram" -m "- Sistema SaaS completo com painel web" -m "- Integracao real com SyncPay (PIX)" -m "- Split Payment automatico (comissao R$ 0,75/venda)" -m "- Order Bumps personalizados por botao" -m "- Downsells agendados" -m "- Sistema de Remarketing completo" -m "- Gamificacao com 29 badges" -m "- Ranking publico com podio" -m "- Painel administrativo" -m "- Dashboard em tempo real (WebSocket)" -m "- Analytics com graficos Chart.js" -m "- Docker + Docker Compose" -m "- Documentacao completa em /docs" -m "- Guia de deploy passo a passo"
echo [OK] Commit criado!
echo.

echo [4/6] Renomeando branch para main...
git branch -M main
echo [OK] Branch renomeada!
echo.

echo ============================================================
echo  IMPORTANTE: CONFIGURE O REPOSITORIO REMOTO
echo ============================================================
echo.
echo Antes de continuar, voce precisa:
echo.
echo 1. Acessar: https://github.com/new
echo 2. Nome do repositorio: bot-manager-saas
echo 3. MARCAR: Private (recomendado)
echo 4. NAO marcar: "Initialize with README"
echo 5. Clicar: Create repository
echo.
echo Apos criar, o GitHub mostrara a URL do repositorio.
echo Exemplo: https://github.com/SEU_USUARIO/bot-manager-saas.git
echo.
set /p repo_url="Cole a URL do repositorio aqui: "

if "%repo_url%"=="" (
    echo.
    echo [ERRO] URL nao fornecida!
    echo Execute o script novamente quando tiver a URL.
    pause
    exit /b 1
)

echo.
echo [5/6] Conectando ao repositorio remoto...
git remote remove origin 2>nul
git remote add origin %repo_url%
echo [OK] Repositorio remoto configurado!
echo.

echo [6/6] Enviando codigo para GitHub...
echo.
echo ATENCAO: Voce precisara autenticar no GitHub.
echo Username: seu usuario do GitHub
echo Password: use um Personal Access Token (nao a senha)
echo.
echo Se nao tiver um token, crie em:
echo https://github.com/settings/tokens
echo (Marque: repo - Full control)
echo.
pause

git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo  SUCESSO! PROJETO NO GITHUB!
    echo ============================================================
    echo.
    echo Acesse: %repo_url:~0,-4%
    echo.
    echo Verifique se NAO aparecem:
    echo   - .env (credenciais)
    echo   - venv/ (ambiente virtual)
    echo   - instance/*.db (banco de dados)
    echo.
    echo Se aparecerem, veja: docs\GITHUB_SETUP.md
    echo.
) else (
    echo.
    echo ============================================================
    echo  ERRO AO FAZER PUSH
    echo ============================================================
    echo.
    echo Possiveis causas:
    echo 1. Credenciais incorretas
    echo 2. URL do repositorio invalida
    echo 3. Sem permissao de acesso
    echo.
    echo Solucao: Veja docs\GITHUB_SETUP.md
    echo.
)

pause

