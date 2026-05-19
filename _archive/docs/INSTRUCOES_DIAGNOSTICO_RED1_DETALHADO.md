# 🔥 INSTRUÇÕES - DIAGNÓSTICO POOL "red1" (DETALHADO)

## 📋 EXECUTAR NA VPS

```bash
cd ~/grimbots
export PGPASSWORD="123sefudeu"
chmod +x diagnostico_pool_red1_detalhado.sh
./diagnostico_pool_red1_detalhado.sh > diagnostico_red1_detalhado.txt 2>&1
cat diagnostico_red1_detalhado.txt
```

---

## 🔍 O QUE O SCRIPT VAI MOSTRAR

### **1. Payments de Hoje - Análise Detalhada**
- Total, com delivery_token, meta_purchase_sent (true/false/null)
- **Crítico:** Payments com delivery_token mas SEM purchase enviado
- **Crítico:** Payments sem delivery_token mas COM purchase enviado (inconsistência)

### **2. Payments Últimas 24H - Análise por Hora**
- Distribuição de payments por hora
- Identifica em qual hora houve mais problemas

### **3. Payments com Problema - Detalhado (TOP 100)**
- Lista completa dos payments problemáticos
- Verifica `tracking_token` e `bot_user.tracking_session_id`
- Identifica se dados de tracking estão corretos

### **4. Verificar Acesso ao /delivery**
- Quantos payments foram acessados no `/delivery`
- Se payment não foi acessado, purchase não pode ser enviado

### **5. Análise de Bot_User.Tracking_Session_ID**
- Verifica se `tracking_session_id` existe
- Verifica se é UUID (correto) ou gerado (errado)

### **6. Resumo Executivo Completo**
- Estatísticas consolidadas das últimas 24h
- Taxa de envio real

---

## 🎯 DADOS ESTRANHOS ENCONTRADOS

**No diagnóstico anterior:**
- Total payments HOJE: 9167
- Com delivery_token: 921
- Purchase enviado: 1567 ← **MAIOR que delivery_token!**

**Isso indica:**
1. Query pode estar filtrando errado (timezone)
2. Payments foram marcados ANTES de ter delivery_token
3. Ou há payments de outros pools sendo contados

---

**Execute o script detalhado e me envie o resultado!**

