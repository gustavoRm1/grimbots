# E0.1 — Proposta de ratificação conjunta (PENDENTE)

> **Status:** **proposta** — as decisões abaixo estão alinhadas entre os dois lados
> mas **NÃO são definitivas** até confirmação formal dos dois desenvolvedores.
> **Nada foi mesclado, implantado ou ativado em produção.**
>
> **Regra de trabalho:** cada desenvolvedor atua **exclusivamente no seu repositório**
> (Grimbots ≠ motor `grimbots-ai`). O motor já aceita memória e contexto, então
> **E-P1b não exige mudança no motor** — exige apenas o acordo de rótulo/limites.

---

## 1. Posições para ratificação

| # | Tema | Posição proposta | Status |
|---|---|---|---|
| **D1** | Rótulo de contrato | `1.0` = base; `1.1` = memória + contexto; `1.2` = resposta aditiva. `contract_version` = **rastreabilidade**, não gatilho de ativação (a presença dos campos é o gatilho) | proposto |
| **D4** | `Offer.id` | manter **≤ 64** (schema do motor), salvo decisão conjunta posterior | proposto |
| **D5** | `state_update` (whitelist) | retirar `last_action` (interno da plataforma); aceitar `objection`/`interest` **≤ 120**; `conversation_summary` **fica fora** da whitelist; sugestões passam por validação e **decisão final da plataforma**; chaves desconhecidas são **ignoradas e registradas** em `validation.errors` | proposto |
| **D6** | Limites de memória | adotar os limites do **schema do motor** como **máximos autoritativos** e aplicar **clamps** na Grimbots | proposto |
| **D10** | Resumo persistido | a **plataforma** é responsável pelo resumo; o motor **não** o substitui; permanece `""` até haver implementação e medição | proposto |
| **D12** | Mapa de `intent` | mapa explícito `oferta → interesse` e `informacao → duvida`, registrando **valor original, valor normalizado, erro de validação e métrica**; demais valores inválidos seguem **erro fatal** | proposto |

> Limites autoritativos referenciados (schema do motor): `lead.name ≤ 60`,
> `lead.interest/objection ≤ 120`, `Offer.id ≤ 64`, `checkout_url ≤ 400`;
> `last_assistant_message ≤ 2000`, `collected_information` (≤30 chaves / key ≤60 /
> value ≤300), `questions_already_asked` (≤20 / item ≤300),
> `offers_already_presented` (≤20 / item ≤120), `turn_count 0..100`,
> `last_action ∈ Action`.

---

## 2. Já preparado neste repositório (inerte)

### E-P0 — Clamps defensivos (sem flag)
- `ai_service.py`: `lead.name` 80→**60**, `lead.interest` 200→**120**,
  `lead.objection` 200→**120**, `Offer.id` 80→**64**, `Offer.checkout_url` 500→**400**
  (constantes nomeadas `MAX_LEAD_*`/`MAX_OFFER_*`).
- Só **aperta** limites; para entradas válidas o payload v1.0 **não muda**
  (golden `tests/payloads/agent_respond_request.json` intacto).

### E-P1a — Memória persistida (merge RMW, **não envia**)
- `_ai_state_set` faz **read-modify-write** (nunca apaga chaves existentes).
- Estado passa a persistir: `collected_information`, `questions_already_asked`,
  `offers_already_presented`, `turn_count`, `last_action`,
  `last_assistant_message`, `conversation_summary` (limites do motor, D6).
- **Nada disso entra no payload**: o envio é E-P1b (flag off) e o comportamento
  v1.0 permanece byte-a-byte.

### Testes
- `tests/test_phase6a_contract_v11.py`: fronteiras E-P0 (`60/61`, `120/121`,
  `64/65`, `400/401`), limites de memória, merge RMW preservando chaves, e prova
  de que a memória **nunca** entra no payload.
- `tests/test_agent_respond_contract.py`: golden v1.0 byte-a-byte (verde).

---

## 3. Bloqueado (não liberado)

| Item | Depende de | Situação |
|---|---|---|
| **E-P1b** (enviar memória/contexto) | ratificação formal de **D1 + D6** | **não** liberado |
| **E-P2** (ler `state_update`) | **D5 + D10** + motor E2 | **não** |
| **D12** (implementar o mapa) | confirmação do mapa | **não** |

O caminho de envio v1.1 já existe no código, porém **protegido por flag e
desligado por padrão** (`GRIMBOTS_AI_CONTRACT=v1.0` + `step_config.contract_v11`).
**Não ativar** antes da confirmação formal.

---

## 3.1 Pendências de runtime (não são fato até reprodução)

- **D9** — `HUMAN_TAKEOVER_ACTIVE` (HTTP 409) está **sem guard**; validar em runtime.
- **D11** — risco de **efeito duplicado em retries** (o motor **não deduplica**
  `request_id`); validar em runtime.

---

## 4. Critérios de aceite para liberar E-P1b

1. Golden do cliente v1.0 **byte-a-byte** com flags off.
2. Golden do motor (`tests/golden/prompts/*`) intacto.
3. Suíte unit do motor **100% verde** (sem regressão).
4. Nenhum **422** por clamp/limite (testes de fronteira).
5. Merge RMW não perde estado; isolamento por lead preservado.
6. Ratificação formal de **D1** e **D6** pelos dois lados.

Só então: medição offline (E4) → shadow (E5) → rollout (E6), com aprovação
explícita a cada passo.

---

## 5. Próximos passos

1. Confirmar formalmente as posições da §1 (ambos os desenvolvedores).
2. Validar em runtime D9 (409) e D11 (duplicidade em retry).
3. Com D1+D6 ratificados: liberar **E-P1b** (envio atrás de flag) e medir offline.
4. Sem merge, deploy ou ativação em produção até conclusão dos critérios da §4.

---

### Referências internas
- `13_RESPOSTA_DECISOES_PENDENTES.md` — respostas às decisões.
- `14_PREPARACAO_EP0_EP1.md` — plano de E-P0/E-P1 e dependências.
- `12_ANEXO_MOTOR_DIVERGENCIAS.md` — divergências D1–D14 e T15.
- `11_REVISAO_CONJUNTA_MOTOR_GRIMBOTS.md` — matriz conjunta.
