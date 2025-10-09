# Guia Rápido - Bot Manager SaaS

## Instalação (2 minutos)

### Windows
```bash
executar.bat
```

### Linux/Mac
```bash
chmod +x start.sh && ./start.sh
```

## Primeiro Acesso

1. Abra: `http://localhost:5000`
2. Login: `admin@botmanager.com` / `admin123`
3. **Altere a senha!**

## Configuração (5 passos)

### 1. Configure Gateway
- Configurações → Gateways → SyncPay
- Insira Client ID e Secret
- Salve

### 2. Crie Bot no Telegram
- @BotFather → `/newbot`
- Copie o token

### 3. Adicione Bot
- Dashboard → "Adicionar Bot"
- Cole o token

### 4. Configure Bot
- Clique em "Configurar"
- Mensagem de boas-vindas
- Adicione botão com preço
- Configure link de acesso
- Salve

### 5. Inicie o Bot
- Dashboard → "Iniciar"
- Status: "Online" ✅

## Teste

1. Telegram → Seu bot
2. Digite: `/start`
3. Clique no botão
4. **Recebe PIX!**

## Logs

```
Bot 1 online e aguardando mensagens...
============================================================
NOVA MENSAGEM RECEBIDA!
============================================================
De: João | Mensagem: '/start'
COMANDO /START - Enviando mensagem de boas-vindas...
Mensagem /start enviada com 1 botao(oes)
============================================================

============================================================
CLIQUE NO BOTAO: buy_19.97_Produto
Cliente: João
============================================================
Produto: Produto | Valor: R$ 19.97
Gateway: SYNCPAY
Gerando PIX via SyncPay API...
SyncPay respondeu com sucesso!
PIX REAL GERADO COM SUCESSO!    <- Credenciais OK!
PIX ENVIADO!
============================================================
```

## Interpretação de Logs

| Log | Significado |
|-----|-------------|
| `PIX REAL GERADO COM SUCESSO` | Credenciais SyncPay corretas - PIX verdadeiro |
| `MODO SIMULACAO - PIX FAKE` | Credenciais incorretas - PIX de teste |

## Próximos Passos

1. Configure webhook no painel da SyncPay: `https://seu-dominio.com/webhook/payment/syncpay`
2. Faça deploy em produção
3. Comece a vender!

---

Para documentação completa, veja `README.md`
