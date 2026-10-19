# ADR-001 — Memória persistente por lead é responsabilidade da Grimbots

> **Status:** Aceito pelo dono do produto (Out/2026), pendente de detalhamento
> conjunto com o dev do `grimbots-ai` para formatos e limites.
> **Classificação:** decisão de arquitetura [EXISTS como princípio]; campos
> específicos permanecem [PROPOSAL]/[JOINT] em `02_PROPOSTA_V1.2_MOTOR.md`.

## Contexto

O motor `grimbots-ai` é **stateless**: cada chamada recebe o contexto completo
e devolve uma sugestão. A conversa precisa de memória entre mensagens (senão o
agente repete perguntas, "esquece" objeções e perde coerência). Duas perguntas
de propriedade precisam ser respondidas antes de implementar:

1. Quem persiste o estado por conversa?
2. Qual sistema é a fonte de verdade de cada campo?

## Decisão

**A Grimbots é dona da memória persistente por lead/conversa.** O motor
continua stateless. A Grimbots:

1. **Persiste** o estado por conversa em Redis (já existe:
   `gb:{user_id}:flow_ai_state:{bot_id}:{telegram_user_id}`, TTL 7 dias —
   `bot_manager.py:3839-3841`).
2. **Envia** o contexto necessário por chamada (payload v1.0 + campos de
   memória quando o contrato v1.2 for aprovado).
3. **Aplica** o `state_update` devolvido pelo motor com validação estrita e
   merge read-modify-write, descartando chaves não permitidas.

### Fonte da verdade campo a campo (proposta [JOINT])

| Campo | Fonte da verdade | Persistência |
|---|---|---|
| `turn_count`, `last_action`, `last_assistant_message` | **Grimbots** (calcula) | Redis |
| `questions_already_asked`, `offers_already_presented` | **Grimbots** (append + dedup) | Redis |
| `collected_information` | motor **sugere**, Grimbots **persiste** | Redis (merge por chave) |
| `conversation_summary` | motor **gera**, Grimbots **persiste e reenvia** | Redis |
| `lead_temperature`, `funnel_stage`, `objection`, `interest` | motor **sugere**, Grimbots **persiste** | Redis (já existe hoje para 3 deles) |
| `human_takeover` | **somente Grimbots** (sticky; motor não seta) | Redis |
| Histórico curto (`recent_messages`) | **Grimbots** (tabela `BotMessage`) | PostgreSQL |
| Persona/configuração do agente | **Seller** (via Flow Builder) | PostgreSQL (`step_config`) |
| Estratégia de conversa, raciocínio comercial | **Motor** (não persistimos) | — |

## Isolamento (invariantes)

1. Chave de estado inclui `user_id` (vendedor/tenant), `bot_id` e
   `telegram_user_id` — nunca há mistura entre leads, bots ou vendedores.
2. Histórico lido com filtro `(bot_id, telegram_user_id)`
   (`bot_manager.py:3877-3885`).
3. `conversation_id` enviado ao motor deriva de `(bot_id, telegram_user_id)`.
4. Nenhum campo de um lead é legível por outro (não há API de leitura cruzada).

## Consequências

- **Positivas:** memória confiável, retomada após reinício/restart (Redis
  persiste; `flow_current_step` já permite retomar o bloco ativo), isolamento
  garantido pela chave, degradação segura (fail-open: sem Redis, turno segue
  com estado vazio).
- **Negativas:** payload cresce com os campos de memória (mitigado por
  limites + orçamento de bytes já existente no scaffolding §10); TTL de 7 dias
  define a janela de memória (conversas mais antigas perdem estado —
  avaliação de retenção é [JOINT]).
- **Riscos:** dependência de os três elos funcionarem (persistir → enviar →
  consumir), detalhado em `00_E0_SUMMARY.md`.

## Não decidido aqui (vai para negociação)

- Formato exato do objeto de memória no payload.
- Limites numéricos finais.
- Janela de retenção (TTL) e política de privacidade do `conversation_summary`.
- Quem dispara a geração de resumo (motor a cada N turnos vs. evento de
  estouro de histórico).

## Alternativas consideradas

1. **Motor stateful (memória no `grimbots-ai`)** — rejeitada: viola o
   statelessness acordado, cria duas fontes de verdade e complexidade de
   sincronização.
2. **Só `recent_messages` (sem memória de longo prazo)** — rejeitada: conversas
   longas perdem coerência (o briefing exige memória entre mensagens).
3. **Memória em PostgreSQL (tabela própria)** — adiável: Redis já atende a
   janela de 7 dias com menor custo; se a retenção crescer, migrar para PG é
   uma evolução futura, não bloqueia o contrato.
