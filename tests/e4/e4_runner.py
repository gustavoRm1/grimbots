"""E4 — Avaliacao OFFLINE (baseline v1.0 x v1.1).

IMPORTANTE
----------
- Teste **OFFLINE** e **reproduzivel**: o "modelo" e **ROTEIRIZADO** (scripted),
  nao um LLM real. Os numeros comerciais aqui sao **SIMULADOS** e **NAO**
  constituem ganho de conversao. Qualquer alegacao de ganho exige experimento com
  dados reais (E5 shadow / E6).
- Nao ativa v1.1, nao toca Telegram/Redis/DB, nao altera usuarios reais.

Medido de forma OBJETIVA (independe do script): aderencia de contexto no payload,
consistencia de memoria (turn_count/dedup/merge/whitelist D5-D10), respeito a
acoes permitidas, qualidade minima, tratamento de objecao e trajetoria SIMULADA.

Uso:
  python3 tests/e4/e4_runner.py            # escreve tests/e4/out/*
  python3 tests/e4/e4_runner.py --quiet    # so resumo no stdout
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from internal_logic.services.ai_service import build_payload, AIResult, apply_state_update  # noqa: E402
from bot_manager import BotManager  # noqa: E402

E4_DIR = Path(__file__).resolve().parent
OUT_DIR = E4_DIR / "out"
V10, V11 = "v1.0", "v1.1"


# ── Modelo ROTEIRIZADO (deterministico) ────────────────────────────────────
def scripted_response(version, turn, payload):
    """Resposta do 'modelo'. v1.1 pode USAR contexto/memoria do payload."""
    spec = dict(turn["v11"] if version == V11 else turn["v10"])

    question = spec.get("question")
    if version == V11 and question:
        asked = payload.get("questions_already_asked") or []
        if question in asked:                      # usa memoria: nao repete pergunta
            question = None
            if spec["action"] == "ask_question":
                spec["action"] = "continue"

    interest = turn.get("interest")
    objection = turn.get("objection")
    if version == V11:
        if objection and spec.get("addresses_objection"):
            message = "Entendo a preocupacao. Vou te mostrar o valor real."
        elif interest:
            message = f"Otimo, sobre {interest}: posso te ajudar agora."
        else:
            message = "Certo, seguimos!"
    else:
        message = "Ola! Sou a Maya."

    response = {
        "message": message,
        "intent": turn["intent"],
        "lead_temperature": turn.get("temperature", "warm"),
        "funnel_stage": turn.get("funnel_stage", "qualification"),
        "action": spec["action"],
        "next_question": question,
        "handoff_human": spec["action"] == "handoff_human",
        "risk": turn.get("risk", "low"),
    }

    state_update = None
    if version == V11:
        su = {"funnel_stage": response["funnel_stage"],
              "conversation_summary": "NAO-DEVIA-SER-APLICADO"}  # D10: fora da whitelist
        if interest:
            su["collected_information"] = {"interesse": interest}
        state_update = su
    return response, bool(spec.get("addresses_objection")), state_update


def _v11_kwargs(bot_config, offers, state):
    return {
        "contract_version": V11,
        "agent_profile": {"name": bot_config["name"], "goal": bot_config["commercial_goal"]},
        "flow_resources": [
            {"type": "link", "label": o["name"], "url": o.get("checkout_url") or ""}
            for o in offers
        ],
        "context_policy": {"max_resources": 3},
        **BotManager._ai_memory_payload(state),
    }


def simulate(version, scenario, corpus):
    """Roda uma conversa (versao fixa). Devolve (logs, memoria_agregada)."""
    bot_config = corpus["bot_config"]
    allowed = scenario["allowed_actions"]
    offers = scenario.get("offers") or []
    state = {}
    logs = []

    for idx, turn in enumerate(scenario["turns"]):
        extra = _v11_kwargs(bot_config, offers, state) if version == V11 else {}
        payload = build_payload(
            request_id=f"e4-{version}-{scenario['id']}-{idx}",
            seller_id="1",
            bot_id="140",
            conversation_id=f"c140-{scenario['id']}",
            bot_user_id="8142273932",
            bot_config=bot_config,
            conversation_state={
                "funnel_stage": state.get("funnel_stage") or "qualification",
                "lead_temperature": state.get("lead_temperature") or "warm",
                "human_takeover": False,
                "ai_enabled": True,
            },
            lead={
                "name": (scenario.get("lead") or {}).get("name") or "",
                "interest": state.get("interest") or "",
                "objection": state.get("objection") or "",
            },
            recent_messages=[{"role": "user", "content": turn["user"]}],
            conversation_summary="",
            available_offers=offers,
            allowed_actions=allowed,
            mode="auto",
            **extra,
        )

        response, addresses_objection, state_update = scripted_response(version, turn, payload)
        result = AIResult.from_dict({**response, "request_id": payload["request_id"]})

        checks = {
            "action_allowed": result.action in allowed,
            "message_nonempty": bool((result.message or "").strip()),
            "question_when_asked": (result.action != "ask_question") or bool(result.next_question),
            "objection_handled": (not turn.get("objection")) or addresses_objection,
        }
        entry = {
            "scenario": scenario["id"],
            "version": version,
            "turn": idx,
            "user": turn["user"],
            "payload_has_context": bool(extra),
            "action": result.action,
            "intent": result.intent,
            "intent_original": result.intent_original,
            "intent_kind": result.intent_kind,
            "message": result.message,
            "objection_expected": bool(turn.get("objection")),
            "objection_handled": addresses_objection if turn.get("objection") else None,
            "checks": checks,
            "passed": all(checks.values()),
        }

        if version == V11 and state_update:
            su_errors = []
            apply_state_update(state, state_update, errors=su_errors)
            entry["state_update_errors"] = su_errors
            entry["state_update_ignored_summary"] = any(
                "conversation_summary" in e for e in su_errors
            )
        state.update(BotManager._ai_memory_updates(
            state, result, result.action, result.message or "",
            (result.next_question or "") if result.action == "ask_question" else "",
        ))
        state["funnel_stage"] = result.funnel_stage
        state["lead_temperature"] = result.lead_temperature
        logs.append(entry)

    questions = state.get("questions_already_asked") or []
    memory = {
        "scenario": scenario["id"],
        "turn_count": state.get("turn_count"),
        "expected_turns": len(scenario["turns"]),
        "questions_deduped": len(questions) == len(set(questions)),
        "summary_not_injected": state.get("conversation_summary") != "NAO-DEVIA-SER-APLICADO",
        "collected_information": state.get("collected_information") or {},
    }
    memory["consistent"] = bool(
        memory["turn_count"] == memory["expected_turns"]
        and memory["questions_deduped"]
        and memory["summary_not_injected"]
    )
    return logs, memory


def summarize(version, logs, memory):
    n = len(logs) or 1
    ask = [e for e in logs if e["action"] == "ask_question"]
    objection_turns = [e for e in logs if e["objection_expected"]]
    objection_handled = [e for e in objection_turns if e["objection_handled"]]
    aliases = [e for e in logs if e.get("intent_kind") == "alias"]
    outcomes = {}
    for e in logs:
        outcomes[e["action"]] = outcomes.get(e["action"], 0) + 1
    return {
        "turns": len(logs),
        "action_allowed_pct": round(100 * sum(e["checks"]["action_allowed"] for e in logs) / n, 1),
        "message_nonempty_pct": round(100 * sum(e["checks"]["message_nonempty"] for e in logs) / n, 1),
        "ask_question_turns": len(ask),
        "question_when_asked_pct": round(
            100 * sum(e["checks"]["question_when_asked"] for e in ask) / (len(ask) or 1), 1),
        "payload_has_context_pct": round(100 * sum(e["payload_has_context"] for e in logs) / n, 1),
        "objection_turns": len(objection_turns),
        "objection_handled_pct": round(
            100 * len(objection_handled) / (len(objection_turns) or 1), 1),
        "intent_alias_normalized": len(aliases),
        "memory_consistent": all(m["consistent"] for m in memory),
        "simulated_outcomes": outcomes,
        "failed_turns": sum(1 for e in logs if not e["passed"]),
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in argv
    corpus = json.loads((E4_DIR / "scenarios.json").read_text())
    scenarios = corpus["scenarios"]

    data = {V10: {"logs": [], "memory": [], "failures": []},
            V11: {"logs": [], "memory": [], "failures": []}}

    for version in (V10, V11):
        for sc in scenarios:
            logs, memory = simulate(version, sc, corpus)
            data[version]["logs"].extend(logs)
            data[version]["memory"].append(memory)
            for e in logs:
                if not e["passed"]:
                    failed = [k for k, ok in e["checks"].items() if not ok]
                    data[version]["failures"].append({**e, "failed_checks": failed})

    summary = {v: summarize(v, data[v]["logs"], data[v]["memory"]) for v in (V10, V11)}
    _write_outputs(corpus, data, summary)
    if not quiet:
        _print_summary(summary)
    return 0


def _write_outputs(corpus, data, summary):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    (OUT_DIR / "results.json").write_text(json.dumps(
        {"generated_at": ts, "summary": summary,
         "logs": {v: data[v]["logs"] for v in data},
         "memory": {v: data[v]["memory"] for v in data}},
        ensure_ascii=False, indent=2))

    (OUT_DIR / "run.log").write_text("\n".join(
        f"[{e['version']}] {e['scenario']} t{e['turn']} "
        f"user={e['user']!r} action={e['action']} intent={e['intent']} "
        f"ctx={e['payload_has_context']} passed={e['passed']}"
        for v in (V10, V11) for e in data[v]["logs"]) + "\n")

    lines = [
        "# E4 — Avaliacao OFFLINE (v1.0 x v1.1)",
        "",
        f"> Gerado em {ts}. **Numeros comerciais sao SIMULADOS** (modelo",
        "> roteirizado). **Nao** constituem ganho de conversao — exige E5/E6 com",
        "> dados reais. Nenhuma ativacao de producao.",
        "",
        "## Resumo por versao",
        "",
        "| Metrica | v1.0 | v1.1 |",
        "|---|---|---|",
    ]
    keys = ["turns", "action_allowed_pct", "message_nonempty_pct", "ask_question_turns",
            "question_when_asked_pct", "payload_has_context_pct", "objection_handled_pct",
            "intent_alias_normalized", "memory_consistent", "failed_turns"]
    for k in keys:
        lines.append(f"| {k} | {summary[V10][k]} | {summary[V11][k]} |")
    lines += ["", "## Trajetoria SIMULADA (contagem por action)", "",
              f"- v1.0: `{summary[V10]['simulated_outcomes']}`",
              f"- v1.1: `{summary[V11]['simulated_outcomes']}`",
              "", "## Consistencia de memoria (por cenario)", ""]
    for v in (V10, V11):
        for m in data[v]["memory"]:
            lines.append(f"- {v} · {m['scenario']}: consistent={m['consistent']} "
                         f"turn_count={m['turn_count']}/{m['expected_turns']} "
                         f"dedup={m['questions_deduped']} summary_not_injected={m['summary_not_injected']}")
    lines += ["", "## Falhas", ""]
    for v in (V10, V11):
        f = data[v]["failures"]
        lines.append(f"### {v}: {len(f)} turno(s) com falha")
        for e in f[:50]:
            lines.append(f"- {e['scenario']} t{e['turn']} action={e['action']} "
                         f"failed={e['failed_checks']}")
        lines.append("")
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n")

    fails = ["# E4 — Relatorio de falhas", "", f"> {ts}", ""]
    for v in (V10, V11):
        fails.append(f"## {v} ({len(data[v]['failures'])})")
        for e in data[v]["failures"]:
            fails.append(f"- **{e['scenario']} t{e['turn']}** user={e['user']!r} "
                         f"action={e['action']} intent={e['intent']} "
                         f"failed={e['failed_checks']} msg={e['message']!r}")
        fails.append("")
    (OUT_DIR / "failures.md").write_text("\n".join(fails) + "\n")


def _print_summary(summary):
    print("E4 offline — resumo (SIMULADO, nao e conversao real)")
    for k in ("turns", "payload_has_context_pct", "action_allowed_pct",
              "objection_handled_pct", "memory_consistent", "failed_turns"):
        print(f"  {k:28s} v1.0={summary[V10][k]}  v1.1={summary[V11][k]}")
    print(f"  outcomes v1.0={summary[V10]['simulated_outcomes']}")
    print(f"  outcomes v1.1={summary[V11]['simulated_outcomes']}")


if __name__ == "__main__":
    sys.exit(main())
