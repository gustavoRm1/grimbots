# Protocolo de Comunicação — Desenvolvimento Grimbots

Este documento define as regras de trabalho entre desenvolvedores para evitar erros de encoding, race conditions e quebras em produção.

---

## 1. Encoding — REGRAS OBRIGATÓRIAS

**TODOS os arquivos Python, HTML, JS e CSS devem ser salvos como UTF-8 sem BOM.**

### Como evitar mojibake (caracteres quebrados como `├║`, `ÔÜá`, etc.)

- **NUNCA** use editores Windows (Notepad, Sublime Text padrão) que salvam como ANSI/CP1252
- **SEMPRE** configure o editor para UTF-8:
  - **VS Code**: barra inferior → clique no encoding → "Save with Encoding" → "UTF-8"
  - **Vim**: `:set encoding=utf-8 fileencoding=utf-8`
  - **Sublime**: Preferences → Settings → `"default_encoding": "UTF-8"`
- **NUNCA** faça copy/paste de arquivos entreeditores diferentes — sempre use `git` para mover código

### Como verificar se um arquivo está limpo

```bash
# Verificar se tem mojibake
python3 -c "
data = open('arquivo.py', 'rb').read()
text = data.decode('utf-8', errors='replace')
if any(c in text for c in '├│║ìÃ§'):
    print('MOJIBAKE DETECTADO — recarregar do git')
else:
    print('OK')
"
```

### Se encontrar mojibake

**NÃO tente "consertar" editando caractere por caractere.** Em vez disso:

```bash
git checkout HEAD~1 -- arquivo.py  # restaura versão anterior limpa
# OU
git show a4b84db:bot_manager.py > bot_manager.py  # restaura commit específico
```

---

## 2. Git Flow

### Fluxo de trabalho

```
1. Criar branch:  git checkout -b fix/nome-da-feature
2. Editar código
3. Commit:        git commit -m "fix(flow): descrição clara"
4. Push:          git push origin fix/nome-da-feature
5. Aguardar review do Gustavo
6. Merge no main (após aprovação)
7. Deploy na VPS (faz o Gustavo)
```

### Regras de commit

- **Mensagem descritiva** no formato: `tipo(escopo): descrição`
  - Tipos: `feat`, `fix`, `refactor`, `docs`, `test`
  - Escopos: `flow`, `editor`, `timer`, `payment`, `admin`, `api`
  - Exemplos:
    - `feat(flow): adiciona timer time_elapsed com minutos e segundos`
    - `fix(editor): corrige save infinito quando API retorna erro`
    - `refactor(bot_manager): extrai lógica de condition para função separada`

- **1 feature por commit** — não misturar correção de bug com feature nova

- **NUNCA commitar**:
  - Arquivos `.env` ou com senhas
  - Arquivos com encoding quebrado (verificar antes de commitar!)
  - `node_modules/`, `__pycache__/`, `*.pyc`

---

## 3. Arquivos Críticos — NÃO MEXER SEM REVIEW

Estes arquivos contêm lógica sensível onde um erro pode derrubar bots inteiros ou causar race conditions. **Sempre pedir review antes de modificar:**

| Arquivo | Por que é crítico |
|---|---|
| `bot_manager.py` | Engine do fluxo. Timer, conditions, race conditions, Redis state |
| `tasks_async.py` | Filas RQ, timer fire, Lua atomic guard |
| `flow_editor.html` | Editor visual — Drawflow canvas + modais + save |
| `drawflowAdapter.js` | Conversão Drawflow ⇄ schema grimbots |
| `grim_flow_bridge.js` | Bridge inline no bot_config |
| `routes.py` | Rotas Flask — anti-cache headers, make_response |

### Antes de modificar qualquer arquivo crítico

1. **Leia o contexto**: `docs/dev/FLOW_CONTEXT.md` explica a arquitetura
2. **Entenda o fluxo**: como dados fluem do editor → Redis → bot_manager → Telegram
3. **Faça UMA mudança por vez** e teste antes de fazer a próxima
4. **NUNCA remova** proteções existentes (Lua guards, try/except com log, rate limits)

### Arquivos livres (pode editar com mais liberdade)

- `templates/bot_config.html` (exceto seções do flow editor)
- `templates/*.html` (outros templates)
- `static/js/*` (exceto `drawflowAdapter.js` e `grim_flow_bridge.js`)
- `internal_logic/services/*` (com cuidado)
- `docs/*`

---

## 4. Deploy — Quem faz

**Deploy na VPS é feito SOMENTE pelo Gustavo.** O outro desenvolvedor faz commit + push, e o Gustavo faz review + deploy.

### Por que?

- Deploy envolve: `git pull` no servidor → atualizar build marker → `pkill -f gunicorn` → verificar workers
- Se o build marker não for atualizado, o browser pode servir cache antigo
- Se o encoding estiver quebrado, o Python pode falhar silenciosamente
- Se houver race condition no timer, mensagens duplicadas são enviadas ao usuário

### Fluxo de deploy

```
1. Desenvolvedor: git push origin main (após review)
2. Gustavo: git stash && git pull origin main (na VPS)
3. Gustavo: atualiza build marker em flow_editor.html
4. Gustavo: pkill -f gunicorn (supervisor reinicia)
5. Gustavo: curl -s http://127.0.0.1:5000/ (verifica HTTP 200)
6. Gustavo: confirma build marker no browser
```

---

## 5. Timer e Race Conditions — Por que é sensível

### O problema

O timer do flow usa `threading.Timer` ou RQ `enqueue_in()` para disparar ações após N segundos. Enquanto o timer dorme, o usuário pode enviar uma mensagem que muda o estado do fluxo. Se o timer não verificar se o estado ainda é válido, **duas ações executam em paralelo** para o mesmo usuário → mensagens duplicadas, estado corrompido.

### Como funciona a proteção

1. **Redis key `flow_current_step`** — indica em qual step o usuário está
2. **Lua atomic guard** — compara e deleta em uma operação atômica no Redis
3. **`flow_time_elapsed_fire()`** em `tasks_async.py` — tem o Lua guard
4. **`marathon_queue.enqueue_in()`** — timer persistido no Redis, sobrevive restart

### O que NÃO fazer

- **NUNCA** chamar `_execute_flow_recursive()` diretamente de um timer sem o Lua guard
- **NUNCA** remover o `flow_current_step` sem compensação (outro handler pode ler)
- **NUNCA** usar `threading.Timer` sem proteção de race condition
- **NUNCA** assumption que "o timer vai sempre executar" — workers morrem, deploys reiniciam

---

## 6. Testes Antes de Push

Antes de fazer push, verificar:

```bash
# 1. Syntax check
python3 -m py_compile bot_manager.py
python3 -m py_compile tasks_async.py

# 2. Encoding check
python3 -c "
for f in ['bot_manager.py', 'tasks_async.py']:
    data = open(f, 'rb').read()
    text = data.decode('utf-8', errors='replace')
    bad = any(c in text for c in '├│║')
    print(f'{f}: {\"MOJIBAKE\" if bad else \"OK\"}')
"

# 3. Não queimar imports
python3 -c "from bot_manager import BotManager; print('import OK')"
```

---

## 7. Contato

- **Gustavo**: faz review e deploy
- **Outro dev**: faz feature branches e push
- **Comunicação**: via commit messages descritivos + este documento

---

## 8. Incidentes Passados (para não repetir)

### Encoding corrompido (Ago 2026)
- Arquivo `bot_manager.py` salvo como Latin-1/CP1252 por um editor Windows
- 443 linhas com mojibake, commits anteriores ficaram ilegíveis
- **Prevenção**: sempre salvar como UTF-8, verificar antes de commitar

### threading.Timer sem Lua guard (Ago 2026)
- Timer substituiu RQ `enqueue_in()` por `threading.Timer` direto
- Lua guard foi bypassado — race condition entre timer e handler de mensagem
- Timer era daemon thread — morria no restart do Gunicorn
- **Prevenção**: nunca chamar `_execute_flow_recursive` direto de timer, sempre usar `flow_time_elapsed_fire` com Lua guard

### Conditions travando funil (Jul 2026)
- `conditions[]` em steps que não são type `condition` causava pause indevida
- Usuário ficava preso no step 1, never reaching step 3
- **Prevenção**: `INPUT_WAITING_TYPES` no backend + cleanup no adapter frontend
