# 🚀 **MVP META PIXEL ASYNC - ROADMAP 7 DIAS**

## ✅ **STATUS GERAL**

**Objetivo:** Sistema assíncrono para 50K eventos/dia com latência < 100ms
**Prazo:** 7 dias corridos
**Início:** Agora
**Entrega:** Dia 7

---

## 📋 **PROGRESSO**

### **✅ DIA 1: INFRAESTRUTURA (CONCLUÍDO)**

- [x] `docker-compose.mvp.yml` - Redis + Postgres + Celery
- [x] `Dockerfile.worker` - Container para workers
- [x] `init_db_mvp.sql` - Schema do banco
- [x] `celery_app.py` - Configuração Celery

**Resultado:** Infraestrutura pronta para rodar

---

### **🔄 DIA 2: CORE DO SISTEMA (EM ANDAMENTO)**

#### **Arquivos a criar:**

1. **`tasks/meta_sender.py`** - Tasks de envio
   - [x] Estrutura base
   - [ ] `send_meta_event()` - Envia evento individual
   - [ ] `send_meta_batch()` - Envia batch
   - [ ] `process_dlq()` - Processa Dead Letter Queue
   - [ ] Rate limiting integrado
   - [ ] Retry com backoff exponencial

2. **`tasks/metrics.py`** - Tasks de métricas
   - [ ] `aggregate_metrics()` - Agrega métricas por hora
   - [ ] `cleanup_old_logs()` - Limpa logs antigos

3. **`tasks/health.py`** - Health checks
   - [ ] `check_system_health()` - Verifica saúde do sistema
   - [ ] Alertas básicos

4. **`models_mvp.py`** - Models SQLAlchemy
   - [ ] `EventQueue` - Fila de eventos
   - [ ] `EventLog` - Log de eventos
   - [ ] `EventMetrics` - Métricas agregadas

5. **`rate_limiter.py`** - Rate limiting
   - [ ] Token bucket em Redis
   - [ ] Limite configurável
   - [ ] Priorização de eventos

6. **`meta_api.py`** - Cliente Meta API
   - [ ] `send_event()` - Envia evento
   - [ ] `send_batch()` - Envia batch
   - [ ] Tratamento de erros
   - [ ] Logging detalhado

---

### **⏳ DIA 3: INTEGRAÇÃO**

- [ ] Integrar com `app.py` (Flask)
- [ ] Rota `/go/<slug>` enfileira eventos
- [ ] Bot manager enfileira ViewContent
- [ ] Webhook enfileira Purchase
- [ ] Testes unitários básicos

---

### **⏳ DIA 4: TESTES E2E**

- [ ] Script `tests/e2e_meta_capi.py`
- [ ] Teste PageView → ViewContent → Purchase
- [ ] Forçar falhas e validar retry
- [ ] Capturar evidências Meta Events Manager
- [ ] Documentar resultados

---

### **⏳ DIA 5: TESTES DE CARGA**

- [ ] Script `tests/load_test.py`
- [ ] Simular 100 req/s por 5 minutos
- [ ] Medir latência (p50, p95, p99)
- [ ] Verificar taxa de sucesso
- [ ] Gerar relatório

---

### **⏳ DIA 6: DOCUMENTAÇÃO**

- [ ] `docs/INSTALL.md` - Como instalar
- [ ] `docs/DEPLOY.md` - Como fazer deploy
- [ ] `docs/ARCHITECTURE.md` - Arquitetura
- [ ] `docs/TROUBLESHOOTING.md` - Resolução de problemas
- [ ] `docs/API.md` - API reference

---

### **⏳ DIA 7: ENTREGA FINAL**

- [ ] Video demo do sistema
- [ ] Checklist final validado
- [ ] Tag `v1.0-mvp` no git
- [ ] Apresentação para stakeholder

---

## 🎯 **MÉTRICAS DE SUCESSO**

### **Obrigatórias:**
- ✅ Sistema suporta 50K eventos/dia
- ✅ Latência < 100ms no caminho crítico
- ✅ Zero perda de eventos (retry até sucesso)
- ✅ Rate limiting funcionando
- ✅ Deduplicação via event_id
- ✅ Testes E2E com evidências
- ✅ Documentação completa

### **Desejáveis:**
- ⭐ Teste de carga 100 req/s
- ⭐ Dashboard básico de métricas
- ⭐ Alertas via console

---

## 📂 **ESTRUTURA DE ARQUIVOS**

```
grpay/
├── celery_app.py                 ✅ Criado
├── docker-compose.mvp.yml        ✅ Criado
├── Dockerfile.worker             ✅ Criado
├── init_db_mvp.sql               ✅ Criado
├── requirements.txt              🔄 Atualizar
├── tasks/
│   ├── __init__.py               ⏳ Criar
│   ├── meta_sender.py            ⏳ Criar
│   ├── metrics.py                ⏳ Criar
│   └── health.py                 ⏳ Criar
├── models_mvp.py                 ⏳ Criar
├── rate_limiter.py               ⏳ Criar
├── meta_api.py                   ⏳ Criar
├── tests/
│   ├── e2e_meta_capi.py          ⏳ Criar
│   ├── load_test.py              ⏳ Criar
│   └── evidencias/               ⏳ Criar
└── docs/
    ├── INSTALL.md                ⏳ Criar
    ├── DEPLOY.md                 ⏳ Criar
    ├── ARCHITECTURE.md           ⏳ Criar
    ├── TROUBLESHOOTING.md        ⏳ Criar
    └── API.md                    ⏳ Criar
```

---

## 🔧 **COMANDOS ÚTEIS**

### **Iniciar sistema:**
```bash
docker-compose -f docker-compose.mvp.yml up -d
```

### **Ver logs:**
```bash
docker-compose -f docker-compose.mvp.yml logs -f celery_worker
```

### **Parar sistema:**
```bash
docker-compose -f docker-compose.mvp.yml down
```

### **Executar testes:**
```bash
python tests/e2e_meta_capi.py
python tests/load_test.py
```

---

## 💪 **PRÓXIMOS PASSOS**

**Agora (Dia 2):**
1. Criar `tasks/meta_sender.py`
2. Criar `models_mvp.py`
3. Criar `rate_limiter.py`
4. Criar `meta_api.py`

**Amanhã (Dia 3):**
1. Integrar com Flask app
2. Testes básicos

**Depois:**
- Continuar roadmap sequencialmente

---

*MVP em execução - QI 540* 🚀
*Status: DIA 1 CONCLUÍDO ✅*
*Próximo: DIA 2 - Core do Sistema*

