# 🔥 INSTRUÇÕES PARA EXECUTAR DIAGNÓSTICO NA VPS

## ✅ OPÇÃO 1: Script Python (RECOMENDADO - Mais fácil)

O script Python usa SQLAlchemy do Flask, então **não precisa de senha do PostgreSQL**.

```bash
cd ~/grimbots
python3 diagnostico_meta_purchase.py > diagnostico_output.txt 2>&1
cat diagnostico_output.txt
```

**Isso vai mostrar todo o diagnóstico na tela e salvar em `diagnostico_output.txt`**

---

## ✅ OPÇÃO 2: Script Shell (se Python não funcionar)

```bash
cd ~/grimbots

# Definir senha antes de executar
export PGPASSWORD="123sefudeu"

# Executar
chmod +x diagnostico_meta_purchase.sh
./diagnostico_meta_purchase.sh > diagnostico_output.txt 2>&1

cat diagnostico_output.txt
```

---

## 📋 O QUE O DIAGNÓSTICO VAI MOSTRAR:

1. ✅ Total de payments 'paid' dos últimos 7 dias
2. ✅ Quantos têm `delivery_token`
3. ✅ Quantos têm `meta_purchase_sent = true`
4. ✅ **CRÍTICO:** Quantos têm `delivery_token` mas `meta_purchase_sent = false`
5. ✅ Análise por pool (configuração Meta Pixel)
6. ✅ Payments problemáticos (TOP 20)
7. ✅ Bots sem pool associado
8. ✅ Pools com `meta_events_purchase = false`

---

## 🎯 COM ESSES DADOS VAMOS IDENTIFICAR:

- Se `meta_events_purchase = false` em muitos pools → **essa é a causa raiz!**
- Se muitos bots não têm pool → **purchases não podem ser enviados**
- Padrões nos payments problemáticos → **indica onde está o bug**

---

**Execute o script e me envie o resultado!**

