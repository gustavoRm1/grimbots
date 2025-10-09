# Bot Manager SaaS

Sistema SaaS completo para gerenciamento de bots do Telegram com painel web em tempo real, integração com gateways de pagamento e geração automática de PIX.

## Funcionalidades

- **Painel Web**: Dashboard em tempo real com estatísticas
- **Gerenciamento de Bots**: Adicionar, configurar e controlar bots via token do Telegram
- **Configuração Visual**: Mensagens, botões, order bump, downsells
- **Geração de PIX**: Integração real com SyncPay, PushynPay e Paradise
- **Automação**: Envio automático de acesso após confirmação de pagamento
- **Tempo Real**: WebSocket para atualizações instantâneas

## Tecnologias

- Backend: Flask, SQLAlchemy, Flask-SocketIO, APScheduler
- Frontend: TailwindCSS, Alpine.js, Socket.IO Client
- Database: SQLite (dev) / PostgreSQL (prod)
- Deploy: Docker, Gunicorn + Eventlet

## Instalação Rápida

### Windows

```bash
executar.bat
```

### Linux/Mac

```bash
chmod +x start.sh
./start.sh
```

### Manual

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar (Windows)
venv\Scripts\activate

# Ativar (Linux/Mac)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Inicializar banco de dados
python init_db.py

# Executar
python app.py
```

## Primeiro Acesso

1. Acesse: `http://localhost:5000`
2. Login padrão:
   - Email: `admin@botmanager.com`
   - Senha: `admin123`
3. **Altere a senha imediatamente!**

## Uso

### 1. Configurar Gateway de Pagamento

- Acesse: Configurações → Gateways
- Configure SyncPay (Client ID + Client Secret)
- Sistema verifica automaticamente

### 2. Criar Bot no Telegram

- Abra @BotFather no Telegram
- `/newbot` → Copie o token

### 3. Adicionar Bot no Sistema

- Dashboard → "Adicionar Bot"
- Cole o token
- Sistema valida automaticamente

### 4. Configurar Bot

- Clique em "Configurar"
- **Boas-vindas**: Mensagem de texto
- **Botões**: Adicione botões com preços
- **Acesso**: Configure link de entrega
- Salve as configurações

### 5. Iniciar Bot

- Dashboard → "Iniciar"
- Aguarde status "Online"
- Bot está funcionando!

### 6. Testar

- Telegram → Seu bot
- Digite: `/start`
- Clique no botão de compra
- Recebe PIX Copia e Cola + QR Code

## Estrutura do Projeto

```
grpay/
├── app.py              # Aplicação Flask principal
├── bot_manager.py      # Gerenciador de bots + Polling
├── models.py           # Models do banco de dados
├── config.py           # Configurações
├── init_db.py          # Inicialização do banco
├── wsgi.py             # Entry point para Gunicorn
├── requirements.txt    # Dependências
├── Dockerfile          # Imagem Docker
├── docker-compose.yml  # Orquestração
├── executar.bat        # Script de execução Windows
├── static/             # CSS e JavaScript
├── templates/          # Templates HTML
└── instance/           # Banco de dados SQLite
```

## API Endpoints

### Autenticação
- `POST /register` - Criar conta
- `POST /login` - Login
- `GET /logout` - Logout

### Bots
- `GET /api/bots` - Listar bots
- `POST /api/bots` - Criar bot
- `POST /api/bots/<id>/start` - Iniciar bot
- `POST /api/bots/<id>/stop` - Parar bot
- `DELETE /api/bots/<id>` - Deletar bot

### Configuração
- `GET /api/bots/<id>/config` - Obter configuração
- `PUT /api/bots/<id>/config` - Atualizar configuração

### Gateways
- `GET /api/gateways` - Listar gateways
- `POST /api/gateways` - Criar/atualizar gateway

### Webhooks
- `POST /webhook/telegram/<bot_id>` - Webhook do Telegram
- `POST /webhook/payment/<gateway>` - Webhook de pagamento

## Deploy em Produção

### Docker

```bash
docker-compose up -d
```

### VPS

```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
```

Configure Nginx como proxy reverso.

## Variáveis de Ambiente

Copie `.env.example` para `.env` e configure:

```env
SECRET_KEY=sua-chave-secreta-aqui
DATABASE_URL=sqlite:///saas_bot_manager.db
PORT=5000
```

Para produção com webhook:
```env
WEBHOOK_URL=https://seu-dominio.com
```

## Integração com Gateways

### SyncPay (Modo Produção)

O sistema está configurado para usar a API real da SyncPay:

```
Endpoint: https://api.syncpay.pro/v1/gateway/api/
Autenticação: Basic Auth (Base64)
```

**Quando lead clica no botão:**
1. Sistema gera PIX via API real da SyncPay
2. Envia código PIX + QR Code para o cliente
3. Salva pagamento no banco (status: pending)
4. Aguarda webhook de confirmação

**Quando pagamento é confirmado:**
1. Gateway envia webhook
2. Sistema atualiza status para "paid"
3. Incrementa estatísticas
4. **Envia link de acesso automaticamente**

## Troubleshooting

### Bot não responde ao /start

- Verifique se o bot está com status "Online" no painel
- Reinicie o bot (Parar → Aguardar 3s → Iniciar)

### PIX não é gerado (modo simulação)

- Verifique credenciais do gateway no painel
- Logs mostram: "PIX REAL gerado" = credenciais OK
- Logs mostram: "MODO SIMULAÇÃO" = credenciais incorretas ou erro na API

### Logs

Os logs mostram claramente:
- `📨 NOVA MENSAGEM RECEBIDA` = Bot recebeu comando
- `⭐ COMANDO /START` = Processando /start
- `🔘 CLIQUE NO BOTÃO` = Cliente clicou para comprar
- `🎉 PIX REAL GERADO COM SUCESSO` = Credenciais SyncPay OK
- `⚠️ MODO SIMULAÇÃO` = Usando PIX fake (credenciais erradas ou fallback)

## Licença

Projeto proprietário.

---

**Bot Manager SaaS - Sistema profissional de gerenciamento de bots Telegram**
