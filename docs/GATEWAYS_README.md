# 💳 GATEWAYS DE PAGAMENTO - GUIA COMPLETO

## 🎯 **GATEWAYS DISPONÍVEIS**

O sistema suporta **5 gateways de pagamento** totalmente integrados:

1. **SyncPay** - Gateway principal
2. **Pushyn Pay** - Backup e alternativa
3. **Paradise Pags** - Checkout customizável
4. **HooPay** - Solução completa
5. **WiinPay** - Simples e direto ✅ NOVO

---

## 📋 **CONFIGURAÇÃO POR GATEWAY**

### **1. SyncPay**
```json
{
  "gateway_type": "syncpay",
  "client_id": "seu-client-id",
  "client_secret": "seu-client-secret"
}
```

### **2. Pushyn Pay**
```json
{
  "gateway_type": "pushynpay",
  "api_key": "seu-token-pushyn"
}
```
📄 **Documentação:** `docs/pushynpay.md`

### **3. Paradise Pags**
```json
{
  "gateway_type": "paradise",
  "api_key": "sk_c3728b109649c7ab...",
  "product_hash": "prod_6c60b3dd3ae2c63e",
  "offer_hash": "e87f909afc",
  "store_id": "177"
}
```

**Como obter credenciais:**
1. Criar produto no Paradise → `product_hash`
2. Criar checkout → Pegar ID da URL → `offer_hash`
   - Exemplo: `https://vendasonlinedigital.store/c/e87f909afc`
   - Offer Hash: `e87f909afc`

📄 **Documentação:** `docs/paradise.md`

### **4. HooPay**
```json
{
  "gateway_type": "hoopay",
  "api_key": "d7c92c358a7ec4819ce7282ff2f3f70d",
  "organization_id": "5547db08-12c5-4de5-9592-90d38479745c"
}
```
📄 **Documentação:** `docs/hoopay.md`

### **5. WiinPay** ✅ NOVO
```json
{
  "gateway_type": "wiinpay",
  "api_key": "sua_api_key_wiinpay",
  "split_user_id": "1234567890"
}
```
📄 **Documentação:** `docs/wiinpay.md`

**Características:**
- ✅ API simples (apenas api_key)
- ✅ Split automático (percentual ou fixo)
- ✅ Webhook POST
- ⚠️ Valor mínimo: R$ 3,00

---

## 🔧 **COMO CONFIGURAR**

1. Acesse: `https://seu-dominio.com/settings`
2. Escolha o gateway
3. Preencha as credenciais
4. Clique em "Verificar e Salvar"
5. ✅ Gateway ativo!

---

## 📊 **COMPARAÇÃO TÉCNICA**

| Feature | SyncPay | Pushyn | Paradise | HooPay | WiinPay |
|---------|---------|--------|----------|--------|---------|
| **Setup** | Médio | Fácil | Difícil | Fácil | **Fácil** |
| **Campos** | 2 | 1 | 4 | 2 | 2 |
| **Split** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Webhook** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Consulta** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **QR Base64** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Valor Mín** | R$ 0,50 | R$ 1,00 | R$ 1,00 | R$ 1,00 | **R$ 3,00** |

---

## 🚀 **DEPLOY**

### **1. Atualizar código:**
```bash
cd /root/grimbots
git pull origin master
```

### **2. Executar migration:**
```bash
python3 migrate_add_gateway_fields.py
```

### **3. Reiniciar aplicação:**
```bash
systemctl restart grimbots.service
```

---

## 📁 **ARQUIVOS DO PROJETO**

```
grpay/
├── gateway_interface.py      # Interface base
├── gateway_syncpay.py         # SyncPay
├── gateway_pushyn.py          # Pushyn
├── gateway_paradise.py        # Paradise
├── gateway_hoopay.py          # HooPay
├── gateway_wiinpay.py         # WiinPay ✅ NOVO
├── gateway_factory.py         # Factory Pattern
├── migrate_add_wiinpay.py     # Migration WiinPay
├── models.py                  # Modelo Gateway
├── app.py                     # Endpoints
└── bot_manager.py             # Integração
```

---

## ✅ **STATUS**

- ✅ **5 gateways** integrados (WiinPay adicionado)
- ✅ Factory Pattern implementado
- ✅ Split payment funcionando
- ✅ Webhook + Consulta ativa
- ✅ Credenciais criptografadas
- ✅ Zero bugs conhecidos
- ✅ **PRODUCTION READY**

---

**Última atualização:** 16/10/2025

