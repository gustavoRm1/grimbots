# Comportamento atual das regras (fato, verificado no código)

> **Classificação:** [EXISTS] integralmente. Nada aqui será alterado sem
> aprovação conjunta. Este documento serve de linha de base para medir
> regressões e para negociar mudanças com dados.

## 1. `allowed_actions`

| Aspecto | Comportamento atual | Evidência |
|---|---|---|
| Configuração no bloco | checkboxes por ação; nada marcado = todas | `flow_editor.html:421-428` |
| Envio no payload | lista filtrada pelo enum; vazio/inválido ⇒ todas as 7 | `ai_service.py:308-312`, `bot_manager.py:4242` |
| Validacao da resposta | **apenas no Mock** (clamp); no caminho real **não valida** | `ai_service.py:562-563` (mock); caminho real: ausente |
| Ação fora do enum | vira `continue` (normalização `AIResult`) | `ai_service.py:115-117` |
| Efeito prático | motor pode executar ação fora da lista do seller | risco documentado em `05_ADR_VALIDACAO_DEFENSIVA.md` |

**Mudança proposta (não implementada):** enforcement no caminho real —
`05_ADR_VALIDACAO_DEFENSIVA.md`. [PROPOSAL]/[JOINT]

## 2. `do_not_respond`

| Aspecto | Comportamento atual | Evidência |
|---|---|---|
| Semântica | silêncio intencional; nenhum envio; permanece no bloco aguardando o próximo texto | `bot_manager.py:4313-4315` |
| Canonicidade | é o canônico do contrato v1.0 | `ai_service.py:32` |
| Alias `no_reply` | **não existe**; se o motor enviar, vira `continue` (resposta é enviada) | `ai_service.py:115-117` |

**Mudança proposta (não implementada):** normalizar `no_reply` →
`do_not_respond` se o motor adotar o alias. [PROPOSAL]/[JOINT]

## 3. Ofertas inativas (`active=false`)

| Aspecto | Comportamento atual | Evidência |
|---|---|---|
| Envio | ofertas do bloco com `active=false` **são enviadas** no payload (com a flag `active=false`) | `ai_service.py:286-305` (monta com `active`), `bot_manager.py:4070-4110` (não filtra) |
| Interface | checkbox "Ativa" por oferta existe no editor | `flow_editor.html:439` |
| Interpretação pelo motor | fora do escopo da Grimbots (o motor pode ignorar, mas isso não é garantido) | — |

**Decisão registrada (Fase E0):** **não filtrar** sem decisão conjunta. Qualquer
mudança exige testes de contrato atualizados — nunca em silêncio.
[JOINT]

## 4. Checkout

| Aspecto | Comportamento atual | Evidência |
|---|---|---|
| Gatilho | `action=send_checkout` (ou motor em modo que o gere) | `bot_manager.py:4331-4347` |
| Execução | roteia pela saída `checkout` para o bloco `payment`, que gera o PIX pela integração existente | `bot_manager.py:4339`, branch `payment` em `_execute_flow_recursive` |
| Valores | vêm das ofertas do bloco ou do bloco Pagamento; a IA **não** inventa valores | `bot_manager.py:4070-4110` |
| Confirmação de pagamento | **nunca** pelo motor; só pelo sistema de pagamento | arquitetura |
| Saída não conectada | aviso no log + `fallback_message` enviada | `bot_manager.py:4341-4347` |
| Sem oferta e sem bloco Pagamento | motor rebaixa para `handoff_human` (comportamento do motor, não da Grimbots) | `bot_manager.py:4071-4073` (comentário) |

## 5. Fallback

| Situação | O que é enviado | Evidência |
|---|---|---|
| Bloco `enabled=false` no turno | tenta HUMANO; se não conectado → fallback | `bot_manager.py:4193-4199` |
| Payload inválido (erro local) | fallback | `bot_manager.py:4262-4268` |
| Erro do Gateway (após retries) | fallback | `bot_manager.py:4269-4274` |
| Erro inesperado | fallback | `bot_manager.py:4275-4281` |
| Saída `checkout`/`handoff` não conectada | fallback (após aviso) | `bot_manager.py:4341-4347, 4355-4360` |
| Ação desconhecida (fora do enum — raro, pois `AIResult` normaliza) | fallback | `bot_manager.py:4362-4367` |
| Texto do fallback | `fallback_message` do bloco (personalizada); default interno `AI_DEFAULT_FALLBACK` | `bot_manager.py:4185-4187` |

O fallback **mantém o step `ai` ativo** — a conversa pode continuar no próximo
texto. Ele não derruba o lead para fora do bloco.

## 6. Handoff humano

| Aspecto | Comportamento atual | Evidência |
|---|---|---|
| Gatilho | `action=handoff_human` **ou** `handoff_human=true` na resposta | `bot_manager.py:4349-4360` |
| Execução | envia `message` (se houver) e roteia pela saída `handoff` | idem |
| Saída não conectada | aviso + fallback | `bot_manager.py:4355-4360` |
| Limpeza de contexto | ao rotear, apaga `flow_current_step` para a próxima mensagem não voltar para a IA | `bot_manager.py:4122-4128` |
| `human_takeover` sticky | só no scaffolding v1.1 (gated); no v1.0 atual não persiste | `bot_manager.py:4294-4301` |
| Erros do sistema (timeout, risco) | fallback/rota própria, **independente** de `allowed_actions` | `bot_manager.py` (tratamento de erro) |

## 7. `enabled=false` e `intro_message` (inconsistência registrada)

| Aspecto | Comportamento atual | Evidência |
|---|---|---|
| Entrada no bloco | `intro_message` é enviada **incondicionalmente**, mesmo com `enabled=false` | `bot_manager.py:4790-4800` |
| Primeiro turno com `enabled=false` | tenta HUMANO (ou fallback); a IA não responde | `bot_manager.py:4193-4199` |
| Efeito | com IA pausada, o lead ainda recebe a abertura e depois vai para humano/fallback — inconsistente com a intenção de "pausada" | dedução do código acima |
| Reentradas do bloco | `intro_message` reenviada a cada entrada no bloco (sem flag de unicidade) | `bot_manager.py:4790-4800` |

**Mudanças propostas (não implementadas):** (a) não enviar `intro_message`
quando `enabled=false`; (b) proteção de unicidade da abertura por
(bot_id, chat_id, step_id). [PROPOSAL]/[JOINT] — comportamento de bots já
publicados deve ser avaliado antes.

## 8. Duplicidade de mensagens e idempotência

| Mecanismo | Comportamento atual | Evidência |
|---|---|---|
| Dedup P1 de pergunta | `next_question` já contida em `message` não é reenviada | `bot_manager.py:3782`, `bot_manager.py:4324` |
| Histórico | `recent_messages` montado com guarda: último item igual ao texto atual não duplica | `bot_manager.py:4200-4203` |
| Idempotência de cobrança | checkout só gera PIX no bloco `payment` (sistema de pagamento); não há geração duplicada pelo motor | arquitetura |
| Idempotência de turno | **não existe** (sem request-dedup por mensagem do Telegram) | — (limitação registrada em riscos) |

## 9. Timeout, retry e auditoria

| Aspecto | Comportamento atual | Evidência |
|---|---|---|
| Timeout | `GRIMBOTS_AI_TIMEOUT` (default 90s) | Config |
| Retry | só 5xx retryables (`RATE_LIMITED`, `AI_BUSY`, `AI_TIMEOUT`, `AI_INVALID_RESPONSE`); backoff 2/4/8s; máx 3; `Retry-After` ≤ 30s | `ai_service.py:63-68` |
| Auditoria | cada turno gravado em `ai_generations` (payload, result ou `error_code`) | `bot_manager.py:4140-4160` |
| Modo | enviado no payload; **sem ramificação de execução** na Grimbots | `bot_manager.py:4243` |

## 10. Retomada após reinício/interrupção

| Mecanismo | Comportamento atual | Evidência |
|---|---|---|
| Bloco ativo | `flow_current_step` em Redis (TTL 7200s) permite retomar o bloco `ai` | `bot_manager.py:4799` (`_save_current_step_atomic`) |
| Estado do lead | Redis com TTL 7 dias | `bot_manager.py:3841` |
| Histórico | PostgreSQL (`BotMessage`) — sobrevive a restart | `bot_manager.py:3877-3903` |
| Restart do processo | turno em andamento pode falhar → fallback; o próximo texto retoma do step salvo | fail-open por design |
