# ADR-003 — Validação defensiva de `action` no caminho real de produção

> **Status:** [PROPOSAL] — NÃO implementado. Requer aprovação conjunta
> (política de enforcement) antes de qualquer código.

## Contexto (fato verificado)

O `allowed_actions` configurado no bloco vai no payload para o motor
(`bot_manager.py:4242`), mas **a resposta do motor não é validada contra ele**
no caminho de produção:

- `MockAIService` faz o clamp: ação fora de `allowed` vira `continue` (ou a
  primeira permitida) — `ai_service.py:562-563`. **Isso mascara o problema em
  testes com mock.**
- `AIResult` só valida contra o **enum global** (7 ações); ação fora do enum
  vira `continue` — `ai_service.py:115-117`.
- `GrimbotsAIService.respond` não aplica `allowed_actions` — o resultado segue
  direto para `_handle_ai_turn`, que executa qualquer ação do enum.

**Risco concreto:** seller restringe o bloco a `["continue","ask_question"]`
(ex.: agente de qualificação sem autorização de vender), mas o motor devolve
`send_checkout` → a Grimbots roteia para o checkout mesmo assim. Violação de
permissão do seller.

## Decisão proposta [JOINT]

Validar `action` da resposta contra `allowed_actions` **no caminho real**, em
duas camadas:

### Camada 1 — normalização (alias)

- Se o contrato v1.2 adotar o alias `no_reply`, normalizar para
  `do_not_respond` (canônico) antes da validação. Enquanto o alias não for
  acordado, NÃO adicionar nomes novos ao enum.

### Camada 2 — enforcement

Após normalização, se `action not in allowed_actions` (e `allowed_actions` foi
enviado, ou seja, não é o default "todas"):

| Política | Comportamento | Efeito |
|---|---|---|
| **A) Clamp para ação segura** (recomendada) | mapear para `continue` se permitida; senão `do_not_respond` (silêncio é sempre seguro); logar `ACTION_CLAMPED` | nunca executa checkout/handoff indevido; conversa segue |
| **B) Fallback total** | tratar como erro do turno: enviar `fallback_message` | mais visível, mas quebra a conversa em um simples desalinhamento |
| **C) Só logar (heurística)** | executar mesmo assim + log `ACTION_NOT_ALLOWED` | **rejeitada**: viola a permissão do seller |

**Recomendação:** Política **A**, com log estruturado em `ai_generations`
(campo `error_code` já existe no modelo de auditoria —
`bot_manager.py:4140-4160`) e métrica para acompanhar a taxa de clamp.

### Exceção `handoff_human`

`handoff_human=true` na resposta (fora do campo `action`) também deve passar
pela checagem: se `handoff_human` não está em `allowed_actions`, não rotear
para HUMANO via motor (a rota de erro do sistema — timeout, risco alto —
continua livre de `allowed_actions`, pois não é decisão do motor).

## Consequências

- **Positivas:** permissão do seller respeitada mesmo com motor desalinhado;
  teste com mock deixa de mascarar (o clamp do mock passa a espelhar o real);
  auditoria visível via `error_code`.
- **Negativas:** se o motor emitir ações fora de `allowed_actions` com
  frequência, a clamp esconde o sintoma — por isso o log/métrica é parte da
  decisão, não opcional.
- **Risco de regressão:** baixo — o comportamento novo só difere do atual
  quando `allowed_actions` é um subconjunto explícito (hoje a maioria dos bots
  usa o default "todas"). Pode ser gated por flag para rollout seguro.

## Alternativas rejeitadas

1. **Validar só no mock** — já faz isso hoje e mascara o gap.
2. **Confiar no motor para nunca exceder** — viola o princípio "a Grimbots
   aplica permissões" (divisão de responsabilidades do briefing).
