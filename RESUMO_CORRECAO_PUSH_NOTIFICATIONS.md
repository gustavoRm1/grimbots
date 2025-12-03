# ✅ CORREÇÃO - PUSH NOTIFICATIONS SEM SOM

## 🔍 PROBLEMA

**Erro:** `TypeError: curve must be an EllipticCurve instance`

O erro ocorre dentro do `pywebpush` quando ele tenta gerar uma chave privada internamente. O problema é uma incompatibilidade entre `pywebpush==1.14.0` e `cryptography==41.0.7`.

---

## ✅ SOLUÇÃO APLICADA

**Converter chave privada para formato PEM sempre:**

O `pywebpush` funciona melhor quando recebe a chave privada em formato PEM. Se a chave estiver em base64 (DER), converter para PEM antes de passar.

**Código aplicado em `app.py` (linhas 12424-12462):**
- Verifica se a chave já está em PEM (começa com "-----BEGIN")
- Se for base64, decodifica para DER, carrega como objeto, e converte para PEM
- Garante que o `webpush` sempre recebe a chave no formato correto

---

## 📝 PRÓXIMOS PASSOS

1. **Reiniciar o servidor:**
   ```bash
   systemctl restart grimbots
   ```

2. **Testar notificações push novamente**

3. **Se o erro persistir**, pode ser necessário atualizar o `pywebpush`:
   ```bash
   pip install --upgrade pywebpush
   ```

---

**STATUS:** ✅ Correção aplicada. Sistema deve enviar notificações push com som corretamente.

