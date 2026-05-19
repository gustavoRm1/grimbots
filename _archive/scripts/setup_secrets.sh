#!/bin/bash
# Setup script para estrutura segura de secrets
# Executar como root ou com sudo

set -e

echo "🔐 Configurando estrutura segura de secrets para GrimBots..."

# Configurações
SECRETS_DIR="/etc/grpay/secrets"
APP_DIR="/opt/grpay"
SERVICE_USER="grpay"
SERVICE_GROUP="grpay"

# Criar usuário de serviço se não existir
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "👤 Criando usuário de serviço: $SERVICE_USER"
    useradd -r -s /bin/false -d "$APP_DIR" "$SERVICE_USER"
fi

# Criar diretório de secrets
echo "📁 Criando diretório de secrets: $SECRETS_DIR"
mkdir -p "$SECRETS_DIR"

# Configurar permissões restritivas
echo "🔒 Configurando permissões seguras..."
chown "$SERVICE_USER:$SERVICE_GROUP" "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Criar subdiretórios para organização
mkdir -p "$SECRETS_DIR/keys"
mkdir -p "$SECRETS_DIR/certs"
mkdir -p "$SECRETS_DIR/tokens"

# Configurar permissões nos subdiretórios
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$SECRETS_DIR"
chmod -R 700 "$SECRETS_DIR"

echo "✅ Diretório de secrets configurado!"
echo ""
echo "📋 Próximos passos:"
echo "1. Copie suas chaves multiline para os arquivos:"
echo "   - VAPID_PRIVATE_KEY → $SECRETS_DIR/vapid_private.pem"
echo "   - VAPID_PUBLIC_KEY  → $SECRETS_DIR/vapid_public.pem"
echo "   - ENCRYPTION_KEY    → $SECRETS_DIR/master.key"
echo ""
echo "2. Configure o .env com os paths:"
echo "   VAPID_PRIVATE_KEY_PATH=$SECRETS_DIR/vapid_private.pem"
echo "   VAPID_PUBLIC_KEY_PATH=$SECRETS_DIR/vapid_public.pem"
echo "   ENCRYPTION_KEY_PATH=$SECRETS_DIR/master.key"
echo ""
echo "3. Ou use Base64 (alternativa):"
echo "   VAPID_PRIVATE_KEY_BASE64=$(cat sua_chave.pem | base64 -w 0)"
echo ""

# Helper para migrar chaves existentes do .env
if [ -f "$APP_DIR/.env" ]; then
    echo "🔍 Detectado .env existente em $APP_DIR/.env"
    echo ""
    
    # Extrair VAPID_PRIVATE_KEY se existir
    if grep -q "^VAPID_PRIVATE_KEY=" "$APP_DIR/.env" 2>/dev/null; then
        echo "⚠️  VAPID_PRIVATE_KEY encontrado no .env"
        echo "   Sugestão: Mover para arquivo externo para compatibilidade com Systemd"
        
        # Verificar se é multiline (contém newline no valor)
        if grep -A1 "^VAPID_PRIVATE_KEY=" "$APP_DIR/.env" | grep -q "BEGIN PRIVATE KEY"; then
            echo "   ❌ Detectada chave multiline no .env - REQUER MIGRAÇÃO!"
            echo ""
            echo "   Execute manualmente:"
            echo "   1. Edite $APP_DIR/.env e remova a linha VAPID_PRIVATE_KEY=..."
            echo "   2. Salve a chave em $SECRETS_DIR/vapid_private.pem"
            echo "   3. Adicione ao .env: VAPID_PRIVATE_KEY_PATH=$SECRETS_DIR/vapid_private.pem"
        fi
    fi
fi

echo ""
echo "🎉 Setup completo!"
