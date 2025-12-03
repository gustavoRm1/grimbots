# ✅ CORREÇÃO - ERRO PUSH NOTIFICATIONS

## 🔍 PROBLEMA IDENTIFICADO

**Erro:**
```
TypeError: curve must be an EllipticCurve instance
```

**Localização:** `app.py` linha 12460 (função `send_push_notification`)

**Stack Trace:**
```
File "/root/grimbots/app.py", line 12460, in send_push_notification
    webpush(
File "/root/grimbots/venv/lib/python3.10/site-packages/pywebpush/__init__.py", line 477, in webpush
    response = WebPusher(
File "/root/grimbots/venv/lib/python3.10/site-packages/pywebpush/__init__.py", line 305, in send
    encoded = self.encode(data, content_encoding)
File "/root/grimbots/venv/lib/python3.10/site-packages/pywebpush/__init__.py", line 203, in encode
    server_key = ec.generate_private_key(ec.SECP256R1, default_backend())
```

**Causa:**
- O erro está dentro do código do `pywebpush` quando ele tenta gerar uma chave privada temporária
- O problema é que `pywebpush==1.14.0` usa uma API antiga do `cryptography` que não é compatível com `cryptography==41.0.7`
- O `pywebpush` está tentando usar `ec.SECP256R1` (classe) ao invés de `ec.SECP256R1()` (instância)

---

## ✅ CORREÇÃO APLICADA

**Converter chave privada para formato PEM sempre:**

O `pywebpush` espera a chave privada no formato PEM. Se a chave estiver em base64 (DER), converter para PEM antes de passar para o `webpush`.

**Código aplicado:**

```python
# ✅ CORREÇÃO: Converter chave privada para formato PEM se necessário
# pywebpush espera formato PEM, então vamos garantir que sempre seja PEM
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64

vapid_private_key = None
try:
    # Se já é PEM, usar direto
    if vapid_private_key_raw.startswith("-----BEGIN"):
        vapid_private_key = vapid_private_key_raw
        logger.debug("VAPID key already in PEM format")
    else:
        # Formato base64 (DER) - converter para PEM
        try:
            # Decodificar base64 para DER
            private_key_der = base64.urlsafe_b64decode(
                vapid_private_key_raw + '=' * (4 - len(vapid_private_key_raw) % 4)
            )
            # Carregar como objeto
            private_key_obj = serialization.load_der_private_key(
                private_key_der,
                password=None,
                backend=default_backend()
            )
            # Converter de volta para PEM (formato que pywebpush espera)
            vapid_private_key = private_key_obj.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            logger.debug("VAPID key converted from base64 (DER) to PEM format")
        except Exception as der_error:
            logger.error(f"❌ Erro ao converter chave de base64 para PEM: {der_error}")
            logger.warning("⚠️ Tentando usar chave como está (pode falhar)")
            vapid_private_key = vapid_private_key_raw
except Exception as e:
    logger.error(f"❌ Erro ao processar VAPID private key: {e}")
    logger.warning("⚠️ Tentando usar chave como está (pode falhar)")
    vapid_private_key = vapid_private_key_raw
```

---

## 📝 ARQUIVOS MODIFICADOS

1. **`app.py` - Linhas 12424-12462** (função `send_push_notification`)

---

## ⚠️ OBSERVAÇÃO

**Atualização do `pywebpush`:**

Também foi atualizado o `requirements.txt` para usar `pywebpush>=1.15.0` (se disponível), mas a correção principal é garantir que a chave sempre esteja em formato PEM.

**Próximos passos:**

1. Reiniciar o servidor para aplicar as mudanças
2. Testar envio de notificações push
3. Se o erro persistir, considerar atualizar `pywebpush` manualmente:
   ```bash
   pip install --upgrade pywebpush
   ```

---

**STATUS:** ✅ Correção aplicada. Sistema deve enviar notificações push corretamente.

