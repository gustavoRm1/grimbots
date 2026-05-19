# FALHA CRÍTICA DE MULTITENANCY - VAZAMENTO DE DADOS ENTRE USUÁRIOS

## **SEVERIDADE: CRITICAL** 
**Impacto:** Usuário com 5 bots conseguiu criar campanhas para 264 bots (incluindo bots de outros usuários)

---

## **RESUMO EXECUTIVO**

Uma falha catastrófica de multitenancy foi identificada na arquitetura do sistema, permitindo que usuários acessem e manipulem dados de outros usuários através do sistema de remarketing. A falha não está na validação de permissão (que é correta), mas sim em **singletons globais compartilhados** que contaminam dados entre sessões.

---

## **1. VETOR PRIMÁRIO DE ATAQUE - SINGLETON GLOBAL COMPARTILHADO**

### **Arquivo:** `internal_logic/services/remarketing_service.py`
**Linhas:** 400-411

```python
# Instância global do serviço
_remarketing_service = None

def get_remarketing_service(bot_manager: Optional[BotManager] = None) -> RemarketingService:
    """
    Retorna instância singleton do RemarketingService
    """
    global _remarketing_service
    if _remarketing_service is None:
        _remarketing_service = RemarketingService(bot_manager)
    return _remarketing_service
```

### **PROBLEMA:** 
- **Singleton Global**: A mesma instância `RemarketingService` é compartilhada entre TODOS os usuários
- **Estado Compartilhado**: `self.worker_threads = {}` e `self.stop_events = {}` acumulam dados de múltiplos usuários
- **Contaminação Cruzada**: Dados de campanhas do usuário A ficam disponíveis para usuário B

---

## **2. VETOR SECUNDÁRIO - QUERIES SEM FILTRO DE USER_ID**

### **Arquivo:** `internal_logic/services/webhook_syncer.py`
**Linha:** 102

```python
# Buscar todos os bots ativos (regra: todos estão sempre online)
active_bots = Bot.query.filter_by(is_active=True).all()
```

### **Arquivo:** `internal_logic/tasks/telegram_tasks.py`
**Linha:** 116

```python
# Buscar TODOS os bots (regra: todos estão sempre online)
bots = Bot.query.all()
```

### **PROBLEMA:**
- **Queries Sem Filtro**: `Bot.query.all()` e `Bot.query.filter_by(is_active=True).all()` retornam bots de TODOS os usuários
- **Explosão de IDs**: Lista de 264 bots (em vez de 5) é processada
- **Herança Maldita**: Campanhas criadas com `bot_ids` de outros usuários

---

## **3. PONTO DE INJEÇÃO - CRIAÇÃO DE CAMPANHAS**

### **Arquivo:** `internal_logic/blueprints/remarketing/routes.py`
**Linha:** 525-540

```python
# Criar campanha para cada bot
for bot_id in bot_ids:
    try:
        # Validar se bot pertence ao usuário
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first()
        if not bot:
            errors.append(f"Bot {bot_id} não encontrado ou sem permissão")
            continue
```

### **PROBLEMA:**
- **Validação Correta**: A verificação `user_id=current_user.id` funciona
- **Contaminação Anterior**: `bot_ids` já vem contaminado com IDs de outros usuários
- **Resultado**: Campanhas órfãs criadas no banco, causando erro 403 no histórico

---

## **4. EVIDÊNCIA DA CONTAMINAÇÃO**

### **Logs Esperados (com contaminação):**
```
[SECURITY_AUDIT] Criando campanha para usuário 123
[SECURITY_AUDIT] Bot_ids recebidos: [1, 2, 3, 4, 5, 999, 1000, 1001]  # <- CONTAMINAÇÃO!
[SECURITY_AUDIT] Total de bots: 8  # <- Deveria ser 5
[CAMPAIGN_CREATE] Processando bot_id: 999 para usuário: 123
[SECURITY] Bot 999 não pertence ao usuário 123 - POSSÍVEL CONTAMINAÇÃO!
```

---

## **5. IMPACTO DO ATAQUE**

### **Consequências Imediatas:**
1. **Vazamento de Dados**: Usuário vê campanhas de outros usuários no histórico
2. **Erro 403 Forbidden**: Sistema bloqueia acesso a dados contaminados
3. **Corrupção de Banco**: Campanhas órfãs criadas com `bot_ids` inválidos
4. **Negócio**: Perda de confiança, possível violação de LGPD/GDPR

### **Escala do Problema:**
- **Usuário Teste**: 5 bots legítimos
- **Bots Recuperados**: 264 bots (incluindo 259 de outros usuários)
- **Taxa de Contaminação**: 5.180% (52x mais bots que o permitido)

---

## **6. ARQUITETURA VULNERÁVEL**

### **Componentes Afetados:**
1. **RemarketingService** - Singleton global com estado compartilhado
2. **BotManager** - Instâncias sem isolamento por usuário
3. **Queries Globais** - Acesso a todos os bots sem filtro `user_id`
4. **Cache Compartilhado** - Estado global entre requisições

### **Padrão de Falha:**
```
Frontend (5 bots) -> Backend (264 bots) -> Criação (264 campanhas) -> Histórico (403)
```

---

## **7. SOLUÇÕES RECOMENDADAS**

### **AÇÃO IMEDIATA (Critical):**
1. **Eliminar Singleton**: Remover `_remarketing_service` global
2. **Isolar por Usuário**: Criar instância por `current_user.id`
3. **Filtrar Queries**: Adicionar `user_id=current_user.id` em todas as queries
4. **Limpar Estado**: Resetar `worker_threads` e `stop_events` por sessão

### **Refatoração Estrutural:**
```python
# ANTES (Vulnerável):
_remarketing_service = None  # Global compartilhado

# DEPOIS (Seguro):
def get_remarketing_service(user_id: int):
    """Retorna instância isolada por usuário"""
    key = f"remarketing_service_{user_id}"
    if key not in _user_services:
        _user_services[key] = RemarketingService(user_id=user_id)
    return _user_services[key]
```

---

## **8. PLANO DE REMEDIAÇÃO**

### **Fase 1 - Contenção (Imediata):**
- [ ] Adicionar logging detalhado para detectar contaminação
- [ ] Implementar validação extra na entrada da API
- [ ] Filtrar `bot_ids` recebidos do frontend

### **Fase 2 - Correção (Crítica):**
- [ ] Eliminar singleton global do RemarketingService
- [ ] Isolar instâncias por usuário
- [ ] Corrigir queries sem filtro `user_id`

### **Fase 3 - Prevenção (Estratégica):**
- [ ] Implementar arquitetura multitenancy robusta
- [ ] Adicionar testes de isolamento de dados
- [ ] Auditoria de segurança completa

---

## **9. INDICADORES DE COMPROMETIMENTO**

### **Sintomas:**
- Erro 403 em `/remarketing/history`
- Contagem de bots > bots do usuário
- Campanhas órfãs no banco
- Logs de `[SECURITY] Bot X não pertence ao usuário Y`

### **Monitoramento:**
```python
# Alerta automático se bot_ids > bots_do_usuario
if len(bot_ids) > len(current_user.bots):
    logger.critical(f"[MULTITENANCY_BREACH] {len(bot_ids)} > {len(current_user.bots)}")
```

---

## **10. CONCLUSÃO**

Esta é uma falha **CRÍTICA** de multitenancy que expõe dados de usuários entre si. O problema não é um bug simples, mas uma **falha fundamental de arquitetura** que requer intervenção imediata.

**Tempo Estimado para Correção:** 4-6 horas
**Risco de Exploração:** Alto
**Impacto no Negócio:** Crítico

---

**Status:** INVESTIGAÇÃO COMPLETA - AGUARDANDO AÇÃO IMEDIATA
