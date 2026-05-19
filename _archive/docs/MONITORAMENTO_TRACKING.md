# 📊 MONITORAMENTO - TRACKING META PIXEL

**Guia prático para monitorar o sistema após deploy**

---

## 🚀 COMANDOS RÁPIDOS (COPIE E COLE)

### 1. Monitorar Logs em Tempo Real (RECOMENDADO)

```bash
# Monitorar tracking completo (client_ip, Parameter Builder, eventos)
tail -f logs/gunicorn.log | grep -E "META TRACKING|META PIXEL|client_ip|Parameter Builder|PageView|Purchase|_fbi"

# Monitorar apenas eventos Meta Pixel (PageView, Purchase)
tail -f logs/gunicorn.log | grep -E "PageView|Purchase|event_id"

# Monitorar client_ip e Parameter Builder
tail -f logs/gunicorn.log | grep -E "client_ip|_fbi|Parameter Builder"

# Monitorar erros
tail -f logs/gunicorn.log | grep -E "ERROR|❌|Exception"
```

---

## 📈 MONITORAMENTO DETALHADO

### 1. Verificar se `client_ip` está sendo capturado

```bash
# Ver últimas 50 linhas com client_ip
tail -n 100 logs/gunicorn.log | grep -E "client_ip|Tracking token atualizado" | tail -20

# Verificar taxa de sucesso (últimas 100 atualizações)
tail -n 500 logs/gunicorn.log | grep "Tracking token atualizado" | tail -100 | grep -o "client_ip=[✅❌]" | sort | uniq -c
```

**Resultado esperado:**
- `client_ip=✅`: Parameter Builder capturou IP
- `client_ip=❌`: Primeira chamada (normal se não houver headers)

---

### 2. Verificar Parameter Builder (`_fbi`)

```bash
# Ver se Parameter Builder está enviando _fbi
tail -f logs/gunicorn.log | grep "_fbi"

# Ver últimas capturas de IP do Parameter Builder
tail -n 200 logs/gunicorn.log | grep "Client IP capturado do Parameter Builder" | tail -10
```

**Resultado esperado:**
```
[META TRACKING] Client IP capturado do Parameter Builder (_fbi): 2804:2d78:4001:5c00:5c06:d5a8:8716:6a17 (IPv6/IPv4)
```

---

### 3. Monitorar Eventos Meta Pixel

```bash
# Monitorar PageView events
tail -f logs/gunicorn.log | grep -E "PageView|pageview_event_id"

# Monitorar Purchase events
tail -f logs/gunicorn.log | grep -E "Purchase|purchase_event_id"

# Ver eventos enviados (últimas 50)
tail -n 500 logs/gunicorn.log | grep -E "PageView enviado|Purchase enviado" | tail -20
```

**Resultado esperado:**
```
[META PIXEL] PageView enviado: event_id=xxx, external_id=xxx, client_ip=xxx
[META PIXEL] Purchase enviado: event_id=xxx, external_id=xxx, client_ip=xxx
```

---

### 4. Verificar Deduplicação (`event_id`)

```bash
# Ver se event_id está sendo usado corretamente
tail -f logs/gunicorn.log | grep -E "event_id|eventID"

# Verificar se pageview_event_id está sendo preservado
tail -n 300 logs/gunicorn.log | grep -E "pageview_event_id|Preservando pageview_event_id" | tail -10
```

**Resultado esperado:**
```
✅ Preservando pageview_event_id do tracking_payload inicial: xxx
✅ Usando pageview_event_id para deduplicação: xxx
```

---

### 5. Monitorar Cookies (`_fbp`, `_fbc`)

```bash
# Verificar cookies capturados
tail -f logs/gunicorn.log | grep -E "_fbp|_fbc|Cookie.*capturado"

# Ver taxa de sucesso dos cookies (últimas 100)
tail -n 500 logs/gunicorn.log | grep "Tracking token atualizado" | tail -100 | grep -oE "fbp=[✅❌]|fbc=[✅❌]" | sort | uniq -c
```

**Resultado esperado:**
```
[META TRACKING] Cookie _fbp capturado do browser: fb.1.xxx...
[META TRACKING] Cookie _fbc capturado do browser: fb.1.xxx...
```

---

### 6. Verificar Erros e Avisos

```bash
# Monitorar erros em tempo real
tail -f logs/gunicorn.log | grep -E "ERROR|❌|Exception|Traceback"

# Ver erros críticos de tracking (últimas 50)
tail -n 1000 logs/gunicorn.log | grep -E "ERROR.*tracking|ERROR.*META|ERROR.*client_ip" | tail -20

# Ver avisos (warnings)
tail -f logs/gunicorn.log | grep -E "WARNING|⚠️"
```

---

### 7. Verificar Redis (Tracking Tokens)

```bash
# Entrar no Redis CLI
redis-cli

# Ver tracking tokens ativos (últimos 10)
KEYS tracking:*

# Ver um tracking token específico (substituir XXX pelo token)
GET tracking:XXX

# Ver tracking por fbclid (substituir YYY pelo fbclid)
GET tracking:fbclid:YYY

# Sair do Redis CLI
exit
```

---

## 📊 MÉTRICAS PARA MONITORAR

### Taxa de Sucesso de `client_ip` (esperado: > 70%)

```bash
# Contar sucessos vs falhas (últimas 100 atualizações)
tail -n 500 logs/gunicorn.log | grep "Tracking token atualizado" | tail -100 | \
  awk '{if ($0 ~ /client_ip=✅/) success++; else if ($0 ~ /client_ip=❌/) fail++} END {print "✅ Sucesso: " success "\n❌ Falha: " fail "\nTaxa: " (success/(success+fail)*100) "%"}'
```

### Taxa de Cookies (`_fbp`, `_fbc`) (esperado: > 80%)

```bash
# Contar fbp e fbc
tail -n 500 logs/gunicorn.log | grep "Tracking token atualizado" | tail -100 | \
  awk '{if ($0 ~ /fbp=✅/) fbp_success++; if ($0 ~ /fbc=✅/) fbc_success++; total++} END {print "fbp: " (fbp_success/total*100) "%\nfbc: " (fbc_success/total*100) "%"}'
```

---

## 🔍 TROUBLESHOOTING

### Se `client_ip=❌` em TODAS as requisições:

```bash
# Verificar se Parameter Builder está sendo chamado
tail -n 500 logs/gunicorn.log | grep "Client IP capturado do Parameter Builder" | wc -l

# Se retornar 0, verificar se script do Parameter Builder está carregando
# Verificar template telegram_redirect.html
grep -n "clientParamBuilder" templates/telegram_redirect.html
```

### Se eventos não estão sendo enviados:

```bash
# Verificar se eventos estão sendo enfileirados
tail -n 500 logs/gunicorn.log | grep -E "enfileirando|enqueued|PageView|Purchase" | tail -20

# Verificar workers RQ (se usando Celery/RQ)
ps aux | grep -E "rq|celery"

# Ver logs dos workers
tail -f logs/rq-tasks.log | grep -E "META|PageView|Purchase"
```

### Se `pageview_event_id` não está sendo preservado:

```bash
# Verificar se pageview_event_id está sendo salvo
tail -n 300 logs/gunicorn.log | grep -E "pageview_event_id|Preservando" | tail -10

# Verificar merge logic
tail -n 500 logs/gunicorn.log | grep -E "Merge realizado|Usando.*client_ip" | tail -10
```

---

## 📈 MONITORAMENTO CONTÍNUO (Script)

Criar script `monitorar_tracking.sh`:

```bash
#!/bin/bash
# Script de monitoramento contínuo do tracking

echo "📊 MONITORAMENTO TRACKING META PIXEL"
echo "======================================"
echo ""

# 1. Últimas atualizações de tracking
echo "🔍 Últimas 10 atualizações de tracking:"
tail -n 500 logs/gunicorn.log | grep "Tracking token atualizado" | tail -10
echo ""

# 2. Taxa de sucesso client_ip
echo "📈 Taxa de sucesso client_ip (últimas 50):"
tail -n 500 logs/gunicorn.log | grep "Tracking token atualizado" | tail -50 | \
  awk '{if ($0 ~ /client_ip=✅/) success++; else if ($0 ~ /client_ip=❌/) fail++} END {print "✅: " success " | ❌: " fail " | Taxa: " (success/(success+fail)*100) "%"}'
echo ""

# 3. Últimos eventos PageView
echo "📄 Últimos 5 eventos PageView:"
tail -n 500 logs/gunicorn.log | grep -E "PageView enviado|pageview_event_id" | tail -5
echo ""

# 4. Últimos eventos Purchase
echo "💰 Últimos 5 eventos Purchase:"
tail -n 500 logs/gunicorn.log | grep -E "Purchase enviado|purchase_event_id" | tail -5
echo ""

# 5. Últimos erros (se houver)
echo "⚠️ Últimos 5 erros (se houver):"
tail -n 500 logs/gunicorn.log | grep -E "ERROR|❌" | tail -5
echo ""
```

**Uso:**
```bash
chmod +x monitorar_tracking.sh
./monitorar_tracking.sh
```

---

## ✅ CHECKLIST PÓS-DEPLOY

Após 1 hora de operação, verificar:

- [ ] `client_ip=✅` em > 70% das atualizações (Parameter Builder funcionando)
- [ ] `_fbp` e `_fbc` sendo capturados em > 80% das requisições
- [ ] `pageview_event_id` sendo preservado entre PageView e Purchase
- [ ] Eventos PageView sendo enviados corretamente
- [ ] Eventos Purchase sendo enviados corretamente (após pagamento confirmado)
- [ ] Nenhum erro crítico nos logs
- [ ] Match Quality melhorando no Meta Events Manager

---

## 🎯 META EVENTS MANAGER

Após 24-48 horas, verificar no Meta Events Manager:

1. **FBC Coverage**: Deve estar > 60% (era 0% antes)
2. **Match Quality**: 
   - PageView: > 7.0/10 (era 6.1/10)
   - ViewContent: > 6.0/10 (era 4.4/10)
   - Purchase: > 8.0/10
3. **Purchase via CAPI**: Deve aparecer eventos via "Server" (não só "Browser")
4. **Deduplicação**: Não deve haver eventos duplicados

---

## 📞 PRÓXIMOS PASSOS

1. **Monitorar por 24-48 horas** usando os comandos acima
2. **Verificar Meta Events Manager** para confirmar melhorias
3. **Ajustar se necessário** baseado nos logs
4. **Documentar problemas** encontrados (se houver)

---

**✅ Sistema está funcionando corretamente se:**
- `client_ip=✅` aparece na maioria das atualizações
- Parameter Builder (`_fbi`) está capturando IPs
- Eventos estão sendo enviados sem erros
- `pageview_event_id` está sendo preservado

