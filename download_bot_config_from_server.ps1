# Script PowerShell para baixar bot_config.html do servidor
# Execute: .\download_bot_config_from_server.ps1

$SERVER_USER = "root"
$SERVER_HOST = "app.grimbots.online"
$SERVER_PATH = "/root/grimbots/templates/bot_config.html"
$LOCAL_PATH = "templates\bot_config.html"

Write-Host "📥 Baixando bot_config.html do servidor" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Criar diretório se não existir
if (-not (Test-Path "templates")) {
    New-Item -ItemType Directory -Path "templates" | Out-Null
}

# Backup do arquivo local se existir
if (Test-Path $LOCAL_PATH) {
    $BACKUP_FILE = "$LOCAL_PATH.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $LOCAL_PATH $BACKUP_FILE
    Write-Host "💾 Backup local: $BACKUP_FILE" -ForegroundColor Yellow
}

# Baixar do servidor usando scp
Write-Host "⬇️  Baixando de $SERVER_USER@$SERVER_HOST..." -ForegroundColor Cyan

try {
    # Usar scp (requer OpenSSH instalado no Windows)
    $scpCommand = "scp $SERVER_USER@${SERVER_HOST}:$SERVER_PATH $LOCAL_PATH"
    Invoke-Expression $scpCommand
    
    if ($LASTEXITCODE -eq 0) {
        $LINES = (Get-Content $LOCAL_PATH | Measure-Object -Line).Lines
        Write-Host "✅ Arquivo baixado com sucesso!" -ForegroundColor Green
        Write-Host "📊 Linhas: $LINES" -ForegroundColor Green
        Write-Host ""
        
        if ($LINES -lt 1000) {
            Write-Host "⚠️  ATENÇÃO: Arquivo parece incompleto ($LINES linhas)" -ForegroundColor Yellow
            Write-Host "   O arquivo completo deve ter ~5000+ linhas" -ForegroundColor Yellow
        } else {
            Write-Host "✅ Arquivo parece completo" -ForegroundColor Green
        }
    } else {
        Write-Host "❌ Erro ao baixar" -ForegroundColor Red
        Write-Host ""
        Write-Host "💡 Alternativa: Use um cliente SFTP (WinSCP, FileZilla) para baixar:" -ForegroundColor Yellow
        Write-Host "   Host: $SERVER_HOST" -ForegroundColor Yellow
        Write-Host "   User: $SERVER_USER" -ForegroundColor Yellow
        Write-Host "   Path: $SERVER_PATH" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Erro: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Certifique-se de que:" -ForegroundColor Yellow
    Write-Host "   1. OpenSSH está instalado (Add-WindowsCapability -Online -Name OpenSSH.Client)" -ForegroundColor Yellow
    Write-Host "   2. Você tem acesso SSH ao servidor" -ForegroundColor Yellow
    Write-Host "   3. Ou use um cliente SFTP (WinSCP, FileZilla)" -ForegroundColor Yellow
    exit 1
}

