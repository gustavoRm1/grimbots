# Guia do Desenvolvedor — Grimbots

> **Leia ANTES de fazer push.** Este guia existe porque erros "pequenos" já custaram dinheiro real.

---

## Por que este guia existe

Em Agosto de 2026, um commit "auditoria production - 11 bugs criticos" mudou o formato de uma chave Redis em `bot_manager.py` mas esqueceu de atualizar `callback_handler.py`. Resultado: **PIX nunca foi gerado** para usuários que aceitavam order bumps. O erro era 3 linhas. O prejuízo foi real.

Este guia documenta as regras que evitam esses erros.

---

## Regra #1: Chaves Redis são CONTRATOS

Quando você define uma chave Redis como `f"orderbump_{bot_id}_{chat_id}"`, isso vira um **contrato** entre TODOS os arquivos que usam essa chave. Se você muda o formato em 1 arquivo, TODOS os outros arquivos que usam essa chave precisam ser atualizados.

### O erro que já cometemos

```python
# bot_manager.py (L4485) — NOVO formato
user_key = f"orderbump_{bot_id}_{chat_id}"  # ✅ CORRETO

# callback_handler.py (L537) — formato ANTIGO  
user_key = f"orderbump_{chat_id_from_callback}"  # ❌ ERRADO
```

Resultado: sessão salva como `gb:ob_session:orderbump_126_8519081036`, mas buscada como `gb:ob_session:orderbump_8519081036`. **PIX nunca gerado.**

### Como evitar

**ANTES** de mudar qualquer chave Redis, rode:

```bash
grep -rn "nome_da_chave" --include="*.py" .
```

Isso mostra **TODOS** os arquivos que usam essa chave. Atualize **TODOS**.

### Exemplos de chaves críticas

| Chave | Arquivos que a usam |
|-------|---------------------|
| `gb:ob_session:orderbump_*` | bot_manager.py, callback_handler.py |
| `gb:pix_cache:*` | bot_manager.py, callback_handler.py |
| `gb:pix_claim:*` | bot_manager.py |
| `gb:*:flow_current_step:*` | bot_manager.py, tasks_async.py, start_command_handler.py |
| `flow_step_timestamp:*` | bot_manager.py, tasks_async.py |

---

## Regra #2: O flow engine é sagrado

O flow engine (`bot_manager.py`) processa **funis de pagamento reais**. Quebrar ele = quebrar pagamento = perder dinheiro.

### O que NUNCA fazer

1. **NUNCA** remova proteções existentes (Lua guards, try/except com log, rate limits)
2. **NUNCA** mude lógica de pagamento sem testar com funil real
3. **NUNCA** faça "refactor grande" de uma vez — faça mudanças pequenas e testáveis
4. **NUNCA** assuma que "só muda uma coisa" — toda mudança tem efeitos colaterais

### Arquivos que você NÃO pode quebrar

| Arquivo | Por que é sagrado |
|---------|-------------------|
| `bot_manager.py` | Engine do fluxo — timer, conditions, race conditions, Redis state |
| `tasks_async.py` | Filas RQ, timer fire, Lua atomic guard |
| `callback_handler.py` | Handlers de pagamento, order bumps, PIX |
| `drawflowAdapter.js` | Conversão Drawflow ⇄ schema grimbots |

### Se você não tem certeza

**NÃO faça a mudança.** Pergunte ao Gustavo primeiro. É melhor atrasar 1 dia do que quebrar pagamento por 1 dia.

---

## Regra #3: Antes de push, pergunte "o que mais isso afeta?"

Toda mudança tem efeitos colaterais. O erro é pensar que sua mudança é isolada.

### O erro que já cometemos

O commit `a4b84db` era "auditoria production - 11 bugs criticos" — **11 mudanças de uma vez**, sem entender o impacto completo. Algumas mudanças quebraram funis existentes.

### Como evitar

**1 mudança por commit.** Se você mudou 3 coisas, faça 3 commits separados.

**ANTES** de commitar:

```bash
# 1. Vê quais arquivos mudou
git diff --stat

# 2. Vê quem mais usa a função que você mudou
grep -rn "nome_da_funcao" --include="*.py" .

# 3. Vê se quebrou imports
python3 -m py_compile arquivo_que_voce_mudou.py
```

---

## Checklist pré-push

Rode **TUDO** antes de fazer push:

```bash
# 1. Syntax check (todos os arquivos que você mexeu)
python3 -m py_compile bot_manager.py
python3 -m py_compile tasks_async.py
python3 -m py_compile internal_logic/services/callback_handler.py

# 2. Encoding check
python3 -c "
for f in ['bot_manager.py', 'tasks_async.py']:
    data = open(f, 'rb').read()
    text = data.decode('utf-8', errors='replace')
    bad = any(c in text for c in '├│║')
    print(f'{f}: {\"MOJIBAKE\" if bad else \"OK\"}')
"

# 3. Redis key consistency (substitua pela chave que você mexeu)
grep -rn "sua_chave_redis" --include="*.py" .

# 4. Import check
python3 -c "from bot_manager import BotManager; print('import OK')"
```

**Se QUALQUER item falhar, NÃO faça push.** Corrija primeiro.

---

## Incidentes reais (para não repetir)

### Bug #1: PIX não gera (Agosto 2026)

**O que aconteceu**: Usuário clica "SIM" no order bump, vê "Bônus adicionado!", mas PIX nunca aparece.

**Causa**: Chave Redis `orderbump_{bot_id}_{chat_id}` em `bot_manager.py` vs `orderbump_{chat_id}` em `callback_handler.py`.

**Prevenção**: `grep -rn "orderbump_" --include="*.py" .` antes de mudar chave.

### Bug #2: Timer nunca dispara (Agosto 2026)

**O que aconteceu**: Funil fica preso no step de condition, fluxo para completamente.

**Causa**: `from internal_logic.core.extensions import get_redis_connection` — função não existe em `extensions.py`, existe em `redis_manager.py`.

**Prevenção**: Testar imports em environment isolado. `python3 -c "from modulo import funcao"` antes de commitar.

### Bug #3: Encoding quebrado (Agosto 2026)

**O que aconteceu**: 443 linhas com mojibake (caracteres quebrados como `├║`, `ÔÜá`), commits anteriores ficaram ilegíveis.

**Causa**: Editor Windows salvou como Latin-1/CP1252.

**Prevenção**: Salvar como UTF-8 SEMPRE. Verificar com script antes de commitar.

### Bug #4: Conditions travam funil (Julho 2026)

**O que aconteceu**: Usuário fica preso no step 1, nunca chega ao step 3.

**Causa**: `conditions[]` em steps que não são type `condition` causava pause indevida.

**Prevenção**: `INPUT_WAITING_TYPES` no backend + cleanup no adapter frontend.

### Bug #5: Health worker derruba bots online em massa (Set/2026)

**O que aconteceu**: 33 bots avulsos (não-pool) ficaram `offline` no dashboard em um único ciclo, mesmo estando 100% funcionais (ex: bot 48 ACESSO RESTRITO).

**Causa**: O Fix D adicionou verificação de bots avulsos no `async_health_worker.py`, mas marcava `offline` com **uma única falha** do `getMe`. Quando o worker disparava ~70 bots × 2 chamadas HTTP em paralelo, a API do Telegram rate-limitava (502/429), derrubando todos de uma vez. Pior: a query filtrava `is_running=True`, então os derrubados ficavam **invisíveis** e nunca eram re-marcados online.

**Correção (Fix E + G + query ampliada)**:
1. **Fix G**: `asyncio.Semaphore(15)` limita chamadas HTTP concorrentes à API (não satura mais).
2. **Fix E**: só marca `offline` após `LOOSE_OFFLINE_THRESHOLD=3` falhas consecutivas de `getMe`; reseta `consecutive_failures` quando responde; recupera `is_running=True` automaticamente ao ver `getMe ok`.
3. **Query ampliada**: varre TODOS os bots não-`manually_disabled` e sem pool (independente de `is_running`), pois é o health worker quem recalcula a saúde.

**Prevenção / regras do health worker**:
- **Nunca derrubar bot com UMA falha** — sempre exigir consistência (threshold de falhas consecutivas / circuit breaker), igual ao código de pools já fazia.
- **Não filter por `is_running` na entrada** de um verificador de saúde — isso impede a auto-recuperação.
- **Não disparar dezenas de chamadas HTTP simultâneas** à API do Telegram (usa semáforo).
- `manually_disabled=True` é o ÚNICO sinal de que o usuário desligou de propósito — o health worker nunca deve mexer nesses.

---

## Regra de ouro

**Se você mudou 1 linha, pergunte: "quem mais usa essa linha?"**

Se não souber a resposta, **não faça push**. Pergunte ao Gustavo.

---

*Última atualização: 24/Agosto/2026*
*Autor: Senior dev (quem já limpou a bagunça)*
