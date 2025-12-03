# ✅ CORREÇÃO - IPv6 NO PAGEVIEW

## 🔍 PROBLEMA IDENTIFICADO

**Meta está reclamando:**
- PageView: está recebendo IPv4
- Purchase: está recebendo IPv6 ✅ (já está funcionando)

**Recomendação Meta:**
> "Atualizar para IPv6 para eventos PageView. Alterar os endereços IPv4 dos eventos PageView para IPv6. Seu servidor está enviando endereços IP IPv4 pela API de Conversões, mas estamos recebendo endereços IP IPv6 pelo pixel Meta."

---

## ✅ SOLUÇÃO

**Aplicar mesma lógica do Purchase no PageView:**

1. **Converter IPv4 para IPv6 mapeado** quando possível
2. **Priorizar IPv6** do Cloudflare (CF-Connecting-IP pode ser IPv6)
3. **Usar mesmo formato** que Purchase usa

---

## 📝 MUDANÇAS NECESSÁRIAS

1. Criar função `normalize_ip_to_ipv6()` em `utils/ip_utils.py`
2. Modificar `get_user_ip()` para retornar IPv6 quando possível
3. Aplicar normalização no PageView antes de enviar

---

**STATUS:** Aguardando implementação.

