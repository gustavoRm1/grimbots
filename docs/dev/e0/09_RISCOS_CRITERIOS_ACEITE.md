# Riscos, critérios de aceite, deploy e rollback

## 1. Riscos conhecidos

### 1.1 Riscos do estado atual (já verificados)

| # | Risco | Severidade | Mitigação atual / proposta |
|---|---|---|---|
| R1 | `allowed_actions` não validado no caminho real (mock mascara) | Alta | ADR-003 [PROPOSAL] |
| R2 | `no_reply` mascarado como `continue` (resposta indesejada enviada) | Média | normalização [PROPOSAL]/[JOINT] |
| R3 | `intro_message` enviada com `enabled=false` e em reentradas | Média | correção [PROPOSAL]/[JOINT] |
| R4 | Modo `shadow`/`suggestion` não ramifica execução — motor pode devolver checkout e a Grimbots executa | Média | decisão [JOINT]: enforcement de modo ou documentar como informativo |
| R5 | Sem idempotência de turno (mensagem do Telegram entregue 2× = 2 turnos) | Média | limitação conhecida; request-dedup é evolução futura |
| R6 | `_ai_state_set` no `main` commitado sobrescreve estado inteiro (sem merge) | Média | merge RMW no scaffolding; incluir na fase funcional gated |
| R7 | TTL de 7 dias: conversas mais antigas perdem memória | Baixa | aceito; retenção maior é [JOINT] |

### 1.2 Riscos da evolução proposta

| # | Risco | Severidade | Mitigação |
|---|---|---|---|
| R8 | Payload cresce com memória → estourar 65536 bytes | Média | orçamento de bytes + redução prioritizando recursos (scaffolding §10); limites por campo |
| R9 | Ativação acidental do v1.1/v1.2 (motor ainda não aceita → 422 em todos os turnos) | Alta | dupla flag + rollback por config; rollout por bot piloto; checklist de ativação |
| R10 | Motor devolve `state_update` malicioso/errado alterando estado | Alta | whitelist de chaves + merge RMW + sanitização (T16/T17) |
| R11 | Divergência de contrato entre os dois devs | Alta | Fase E0: contrato aprovado por escrito antes de código (checklist `02_PROPOSTA_V1.2_MOTOR.md` §6) |
| R12 | Regressão em bots já publicados | Média | compatibilidade byte-a-byte + testes T20/T21 + ativação opt-in por bloco |
| R13 | Privacidade: `conversation_summary` pode reter dados sensíveis | Média | sanitização; limites; política de retenção [JOINT] |
| R14 | Clamp de ação esconde desalinhamento recorrente do motor | Baixa | métrica/log `ACTION_CLAMPED` obrigatório na decisão |

## 2. Critérios de aceite (por entregável)

### E0 — Documentação (esta fase)

- [x] Contrato v1.0 documentado com evidências `arquivo:linha`.
- [x] Proposta v1.2 claramente marcada [PROPOSAL]/[JOINT].
- [x] ADRs de memória, versionamento e validação defensiva escritos.
- [x] Matriz de compatibilidade campo a campo.
- [x] Comportamento atual das regras documentado sem alterações.
- [x] Plano de testes com casos de isolamento, ação proibida, saída
      desconectada, IA desativada, reentrada, duplicidade, retomada,
      compatibilidade.
- [x] Riscos e rollback definidos.
- [ ] Aprovação explícita do dono do produto (pendente — é este o gate).

### Fase 1 funcional (segurança) — gate: contrato aprovado

- [ ] Enforcement de `allowed_actions` no caminho real + testes T1-T9 verdes.
- [ ] Correção de `intro_message` (`enabled=false` + unicidade) + T5/T6.
- [ ] Zero regressão: suíte completa verde (incluindo baseline atual).

### Fase 2 funcional (memória) — gate: contrato de memória aprovado + motor pronto

- [ ] Persistência/envio dos campos acordados + `state_update` validado.
- [ ] Testes T10-T19 verdes.
- [ ] Payload dentro do orçamento de bytes em cenários reais.

### Fase 3 funcional (produto/UI) — gate: Fase 2 estável

- [ ] Reorganização do bloco no Flow Builder com compatibilidade (T21).
- [ ] Nenhum campo antigo removido sem migração.

### Aceite final do produto (o briefing exige mais que demo)

- [ ] Agente mantém memória entre mensagens (T13/T14 + piloto manual).
- [ ] Adapta-se a leads distintos (piloto com 2+ personas de teste).
- [ ] Executa o funil até o checkout corretamente (checkout real em staging).
- [ ] Evidência de melhoria de conversão/qualidade (métricas do piloto vs
      baseline), não apenas impressão em demonstração.

## 3. Procedimento de deploy (futuro, resumido)

1. Merge do código funcional gated (flags desligadas) — comportamento idêntico
   ao atual; suíte verde.
2. Deploy de código na VPS (fluxo Git canônico: `git pull` + reload Gunicorn).
3. Validação em staging/bot piloto com flags **desligadas** (v1.0).
4. Ativação progressiva: flag global → bot piloto (`step_config`) →
   observar 24-48h → demais bots.
5. Cada passo reversível por config (desligar flags).

**Ordem obrigatória (não negociável):** motor aceita os campos **antes** de a
Grimbots enviá-los. Ativação invertida causa 422 em massa (R9).

## 4. Rollback

| Nível | Ação | Tempo | Cobre |
|---|---|---|---|
| Primário | desligar flags (global e/ou por bloco) | minutos, sem deploy | qualquer problema de contrato/v1.2 |
| Secundário | reverter merge (git revert) + deploy | ~15 min | bug de código na fase funcional |
| Emergencial | `git checkout <sha anterior>` na VPS + reload | minutos | incidente grave (fluxo canônico de rollback do repo) |

Dados: estado em Redis (TTL 7d) e `ai_generations` não são afetados por
rollback de código; campos novos de memória permanecem inertes até a próxima
ativação.
