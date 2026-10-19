#!/usr/bin/env python3
"""
E5 — Relatório reproduzível do shadow (Fase 2C).

Puro e determinístico a partir das linhas (`AIShadowDecision.to_dict()`), para
que o mesmo dataset produza sempre o mesmo relatório. Não inclui PII: agrega
apenas contagens; `lead_ref`/`request_id`/`context_json` nunca entram na saída.
Não trata a ação real como verdade — divergências são reportadas de forma
NEUTRA (o shadow pode estar certo ou errado; o relatório não decide isso).

Uso:
    python -m internal_logic.services.ai_shadow_report --days 30
    python -m internal_logic.services.ai_shadow_report --bot-id 12 --json
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

# Códigos que classificamos como "indisponibilidade/timeout" (não erro de conteúdo).
_TIMEOUT_HINTS = ("TIME", "UNAVAILABLE", "CONNECT", "READ")


def _is_timeout(code):
    c = (code or "").upper()
    return any(h in c for h in _TIMEOUT_HINTS)


def _is_failure(row):
    return bool(row.get("error_code"))


def _is_comparable(row):
    """Comparável = turno com decisão real observada e shadow válido, sem erro."""
    if _is_failure(row):
        return False
    return bool(row.get("proposed_action")) and bool(row.get("observed_action")) \
        and row.get("proposed_valid") is not False


def build_report(rows):
    """Constrói o relatório a partir de linhas já materializadas. Puro."""
    rows = list(rows or [])
    total = len(rows)
    failures = [r for r in rows if _is_failure(r)]
    comparable = [r for r in rows if _is_comparable(r)]
    non_comparable = total - len(comparable)

    matches = [r for r in comparable if r.get("action_match") is True]
    mismatches = [r for r in comparable if r.get("action_match") is False]

    by_action = {}
    for r in mismatches:
        key = f"{r.get('proposed_action') or '?'}->{r.get('observed_action') or '?'}"
        by_action[key] = by_action.get(key, 0) + 1

    stage_diff = {}
    for r in comparable:
        d = r.get("funnel_delta")
        if d is None:
            continue
        stage_diff[str(d)] = stage_diff.get(str(d), 0) + 1

    fail_codes = {}
    for r in failures:
        code = r.get("error_code") or "UNKNOWN"
        fail_codes[code] = fail_codes.get(code, 0) + 1

    versions = {}
    for r in rows:
        v = r.get("motor_version") or "(desconhecida)"
        src = r.get("motor_version_source") or "unknown"
        key = f"{v} [{src}]"
        versions[key] = versions.get(key, 0) + 1

    bots = sorted({r.get("bot_id") for r in rows if r.get("bot_id") is not None})
    leads = {r.get("lead_ref") for r in rows if r.get("lead_ref")}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample": {
            "total": total,
            "comparable": len(comparable),
            "non_comparable": non_comparable,
            "distinct_bots": len(bots),
            "distinct_leads": len(leads),
            "coverage_note": (
                "cobertura relativa não calculável: denominador populacional "
                "(leads elegíveis) não é registrado pelo shadow"
            ),
        },
        "match": {
            "matches": len(matches),
            "mismatches": len(mismatches),
            "match_rate": (len(matches) / len(comparable)) if comparable else None,
        },
        "divergences_by_action": dict(sorted(by_action.items(), key=lambda kv: (-kv[1], kv[0]))),
        "stage_differences": dict(sorted(stage_diff.items(), key=lambda kv: (-kv[1], kv[0]))),
        "failures": {
            "total": len(failures),
            "by_code": dict(sorted(fail_codes.items(), key=lambda kv: (-kv[1], kv[0]))),
            "timeouts": sum(1 for r in failures if _is_timeout(r.get("error_code"))),
        },
        "motor_versions": dict(sorted(versions.items(), key=lambda kv: (-kv[1], kv[0]))),
        "disclaimer": (
            "Divergências são NEUTRAS: o shadow não é tratado como correto "
            "nem como incorreto. Sem PII: apenas contagens agregadas."
        ),
    }


def render_markdown(report):
    s, m = report["sample"], report["match"]
    lines = [
        "# E5 Shadow — Relatório",
        "",
        f"- gerado: {report['generated_at']}",
        f"- total: {s['total']} (comparáveis {s['comparable']}, não comparáveis {s['non_comparable']})",
        f"- bots: {s['distinct_bots']} · leads distintos: {s['distinct_leads']}",
        "- correspondência de ação: "
        + (f"{m['match_rate']:.1%}" if m["match_rate"] is not None else "n/d")
        + f" ({m['matches']}/{s['comparable']})",
        "",
        "## Divergências por ação (proposta→observada)",
    ]
    lines += [f"- {k}: {v}" for k, v in report["divergences_by_action"].items()] or ["- (nenhuma)"]
    lines += ["", "## Diferenças de estágio (delta)"]
    lines += [f"- {k}: {v}" for k, v in report["stage_differences"].items()] or ["- (nenhuma)"]
    f = report["failures"]
    lines += ["", f"## Falhas: {f['total']} (timeouts {f['timeouts']})"]
    lines += [f"- {k}: {v}" for k, v in f["by_code"].items()] or ["- (nenhuma)"]
    lines += ["", "## Versões do motor"]
    lines += [f"- {k}: {v}" for k, v in report["motor_versions"].items()] or ["- (nenhuma)"]
    lines += ["", f"> {report['disclaimer']}"]
    return "\n".join(lines) + "\n"


def collect_rows(bot_id=None, days=None, until=None, limit=None):
    """Materializa linhas do banco (única parte dependente de DB)."""
    from internal_logic.core.models import AIShadowDecision
    q = AIShadowDecision.query
    if bot_id is not None:
        q = q.filter(AIShadowDecision.bot_id == int(bot_id))
    if days:
        cutoff = (until or datetime.now(timezone.utc)) - timedelta(days=int(days))
        q = q.filter(AIShadowDecision.created_at >= cutoff)
    q = q.order_by(AIShadowDecision.created_at.desc())
    if limit:
        q = q.limit(int(limit))
    return [r.to_dict() for r in q.all()]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Relatório E5 shadow (somente leitura).")
    ap.add_argument("--bot-id", type=int, default=None)
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--json", action="store_true", help="saída JSON em vez de Markdown")
    args = ap.parse_args(argv)

    from app import app  # noqa: E402
    with app.app_context():
        rows = collect_rows(bot_id=args.bot_id, days=args.days, limit=args.limit)
    report = build_report(rows)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
