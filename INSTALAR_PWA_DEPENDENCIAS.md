# 📦 Instalação de Dependências para PWA Push Notifications

## 🎯 Dependências Necessárias

### 1. pywebpush (Enviar Push Notifications)
```bash
pip install pywebpush
```

### 2. py-vapid (Gerar chaves VAPID - opcional, se quiser gerar no código)
```bash
pip install py-vapid
```

## 🔑 Configuração de Chaves VAPID

As chaves VAPID são necessárias para autenticar o servidor ao enviar push notifications.

### Gerar chaves VAPID:

**Opção 1: Via py-vapid (Python)**
```bash
python -c "from py_vapid import Vapid01; v = Vapid01(); v.generate_keys(); print('Public:', v.public_key.public_bytes_raw().hex()); print('Private:', v.private_key.private_bytes_raw().hex())"
```

**Opção 2: Via Node.js (web-push)**
```bash
npx web-push generate-vapid-keys
```

### Adicionar ao .env:

```env
# Chaves VAPID (formato hex ou base64)
VAPID_PUBLIC_KEY=sua_chave_publica_aqui
VAPID_PRIVATE_KEY=sua_chave_privada_aqui
VAPID_EMAIL=admin@grimbots.com  # Email de contato para VAPID
```

## 📋 Migration do Banco

Execute a migration para criar a tabela:

```bash
python migrate_add_push_subscription.py
```

## ✅ Verificação

1. Acesse o dashboard no mobile
2. O navegador deve solicitar permissão de notificações
3. Verifique no console do navegador se o Service Worker foi registrado
4. Verifique no banco se a subscription foi salva:
   ```sql
   SELECT * FROM push_subscriptions WHERE is_active = true;
   ```

## 🚀 Teste

Após configurar, faça uma venda e verifique se a notificação push é recebida mesmo com o app fechado (ou em background).

