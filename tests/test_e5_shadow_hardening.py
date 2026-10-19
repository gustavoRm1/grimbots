"""
E5 — hardening (Fase 2): retenção, limites operacionais, relatório e versão.

Offline, sem rede/DB/Redis. Cobre:
  2A retenção/expurgo (política, injeção, fail-open, preserva recentes)
  2B limites (in-flight, taxa/min, teto/dia, ignorar sem bloquear)
  2C relatório (puro, determinístico, sem PII, neutro, comparáveis)
  2D versão do motor (/health verificável, fallback explícito, cache)

  python tests/test_e5_shadow_hardening.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from internal_logic.services import ai_shadow as shadow  # noqa: E402
from internal_logic.services import ai_shadow_report as report  # noqa: E402

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


# ── 2A — Retenção ────────────────────────────────────────────────────────────
def test_retention_cutoff_policy():
    assert shadow.retention_cutoff(0, NOW) is None
    assert shadow.retention_cutoff(-5, NOW) is None
    assert shadow.retention_cutoff(90, NOW) == NOW - timedelta(days=90)


def test_filter_expired_picks_only_old_rows():
    cutoff = NOW - timedelta(days=90)
    rows = [
        (1, NOW - timedelta(days=100)),   # expira
        (2, NOW - timedelta(days=10)),    # mantém
        (3, NOW - timedelta(days=91)),    # expira
        (4, None),                        # ignora
    ]
    assert shadow.filter_expired(rows, cutoff) == [1, 3]
    assert shadow.filter_expired(rows, None) == []


def test_filter_expired_handles_naive_datetimes():
    cutoff = NOW - timedelta(days=90)
    naive = (NOW - timedelta(days=100)).replace(tzinfo=None)
    assert shadow.filter_expired([(9, naive)], cutoff) == [9]


def test_purge_disabled_returns_noop():
    res = shadow.purge_expired(retention_days=0, now=NOW,
                               fetch=lambda c, lim: (_ for _ in ()).throw(AssertionError("não deve buscar")))
    assert res == {"enabled": False, "deleted": 0, "cutoff": None}


def test_purge_batches_and_counts():
    store = [(i, NOW - timedelta(days=200)) for i in range(1, 6)]
    deleted = []

    def fetch(cutoff, limit):
        rows = [r for r in store if r[0] not in deleted]
        return rows[:limit] if limit else rows

    def delete(ids):
        deleted.extend(ids)

    res = shadow.purge_expired(retention_days=90, now=NOW, batch_size=2,
                               fetch=fetch, delete=delete)
    assert res["enabled"] is True
    assert res["deleted"] == 5
    assert sorted(deleted) == [1, 2, 3, 4, 5]


def test_purge_is_fail_open():
    def boom(cutoff, limit):
        raise RuntimeError("db fora")

    res = shadow.purge_expired(retention_days=90, now=NOW, fetch=boom, delete=lambda ids: None)
    assert res["enabled"] is True and res["deleted"] == 0


# ── 2B — Limites operacionais ────────────────────────────────────────────────
def test_limiter_inflight_cap_and_release():
    lim = shadow.ShadowLimiter(max_inflight=2, max_per_minute=0, max_per_day=0)
    assert lim.admit() is True
    assert lim.admit() is True
    assert lim.admit() is False       # estourou in-flight
    lim.release()
    assert lim.admit() is True


def test_limiter_per_minute_window():
    clock = {"t": 0.0}
    lim = shadow.ShadowLimiter(max_inflight=100, max_per_minute=2, max_per_day=0,
                               now_fn=lambda: clock["t"])
    assert lim.admit() and lim.admit()
    assert lim.admit() is False       # 3ª no mesmo minuto
    clock["t"] = 61.0                 # janela desliza
    assert lim.admit() is True


def test_limiter_daily_budget():
    lim = shadow.ShadowLimiter(max_inflight=100, max_per_minute=0, max_per_day=2)
    assert lim.admit() and lim.admit()
    assert lim.admit() is False
    snap = lim.snapshot()
    assert snap["day_count"] == 2 and snap["max_per_day"] == 2


def test_dispatch_ignored_when_limiter_full():
    from flask import Flask
    from bot_manager import BotManager

    app = Flask(__name__)
    app.config.update(SECRET_KEY="k" * 32, GRIMBOTS_AI_SHADOW_SECRET="hmac",
                      GRIMBOTS_AI_SHADOW_SAMPLE=1.0, GRIMBOTS_AI_SHADOW_INCLUDE_TEXT=False,
                      GRIMBOTS_AI_SHADOW_MAX_TEXT_CHARS=0)
    full = shadow.ShadowLimiter(max_inflight=1, max_per_minute=0, max_per_day=0)
    assert full.admit() is True  # ocupa o único slot (não libera)

    collected = []
    orig_get = shadow.get_limiter
    orig_rec = shadow.record_shadow_decision
    shadow.get_limiter = lambda: full
    shadow.record_shadow_decision = lambda r: collected.append(r)

    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7
    try:
        with app.app_context():
            mgr._ai_dispatch_shadow(
                bot_id=1, telegram_user_id="8", config={}, step={"id": "s"},
                step_config={"shadow": True}, history=[], state={}, request_id="x",
                observed={"action": "continue"},
                build_payload_fn=lambda extra: {"request_id": "x", "mode": "shadow"},
                secret="hmac", sample_rate=1.0, include_text=False, max_text_chars=0,
                motor_version="1.6.0", motor_commit="c",
            )
    finally:
        shadow.get_limiter = orig_get
        shadow.record_shadow_decision = orig_rec
    assert collected == []  # limite atingido => shadow ignorado, sem registro


def test_configure_and_get_limiter():
    lim = shadow.configure_limiter(max_inflight=3, max_per_minute=0, max_per_day=0)
    assert shadow.get_limiter() is lim
    assert lim.max_inflight == 3
    # restaura default para não vazar entre testes
    shadow.configure_limiter(max_inflight=shadow.DEFAULT_MAX_INFLIGHT,
                             max_per_minute=shadow.DEFAULT_MAX_PER_MINUTE,
                             max_per_day=shadow.DEFAULT_MAX_PER_DAY)


# ── 2C — Relatório ───────────────────────────────────────────────────────────
def _row(**kw):
    base = {
        "bot_id": 1, "lead_ref": "hmac", "request_id": "r", "error_code": None,
        "proposed_action": "ask_question", "observed_action": "ask_question",
        "proposed_valid": True, "action_match": True, "funnel_delta": 0,
        "motor_version": "1.6.0", "motor_version_source": "health",
    }
    base.update(kw)
    return base


def test_report_no_pii_keys():
    rep = report.build_report([_row(), _row()])
    blob = repr(rep)
    for forbidden in ("lead_ref", "request_id", "context_json", "hmac"):
        assert forbidden not in blob


def test_report_comparable_and_match_rate():
    rows = [
        _row(action_match=True),
        _row(action_match=False, proposed_action="present_offer", observed_action="continue",
             funnel_delta=1),
        _row(error_code="AI_BACKEND_UNAVAILABLE", proposed_action=None, observed_action="pause"),
        _row(proposed_valid=False, proposed_action=None, observed_action="continue", action_match=None),
    ]
    rep = report.build_report(rows)
    assert rep["sample"]["total"] == 4
    assert rep["sample"]["comparable"] == 2
    assert rep["sample"]["non_comparable"] == 2
    assert rep["match"]["matches"] == 1
    assert rep["match"]["mismatches"] == 1
    assert rep["match"]["match_rate"] == 0.5
    assert rep["divergences_by_action"] == {"present_offer->continue": 1}
    assert rep["stage_differences"] == {"0": 1, "1": 1}
    assert rep["failures"]["total"] == 1
    assert rep["failures"]["timeouts"] == 1
    assert rep["failures"]["by_code"] == {"AI_BACKEND_UNAVAILABLE": 1}


def test_report_is_neutral_and_deterministic():
    rows = [_row(action_match=False, proposed_action="present_offer", observed_action="continue")]
    a = report.build_report(rows)
    b = report.build_report(rows)
    a.pop("generated_at")
    b.pop("generated_at")
    assert a == b
    assert "NEUTRA" in a["disclaimer"] or "NEUTR" in a["disclaimer"]


def test_report_empty_dataset():
    rep = report.build_report([])
    assert rep["sample"]["total"] == 0
    assert rep["match"]["match_rate"] is None
    assert rep["failures"]["total"] == 0


def test_report_markdown_renders():
    md = report.render_markdown(report.build_report([_row()]))
    assert "# E5 Shadow" in md and "correspondência de ação" in md


# ── 2D — Versão do motor ─────────────────────────────────────────────────────
def test_resolve_version_from_health():
    shadow.reset_version_cache()
    v, src = shadow.resolve_motor_version(health_fetcher=lambda: {"version": "1.6.0"})
    assert v == "1.6.0" and src == "health"
    shadow.reset_version_cache()


def test_resolve_version_falls_back_to_env():
    shadow.reset_version_cache()
    def boom():
        raise RuntimeError("offline")
    v, src = shadow.resolve_motor_version(health_fetcher=boom, fallback="1.5.0-env")
    assert v == "1.5.0-env" and src == "env"
    shadow.reset_version_cache()


def test_resolve_version_unknown_when_nothing_known():
    shadow.reset_version_cache()
    v, src = shadow.resolve_motor_version(health_fetcher=None, fallback="")
    assert v == "" and src == "unknown"
    shadow.reset_version_cache()


def test_resolve_version_caches_within_ttl():
    shadow.reset_version_cache()
    calls = {"n": 0}
    def first():
        calls["n"] += 1
        return {"version": "1.6.0"}
    shadow.resolve_motor_version(health_fetcher=first)
    v, src = shadow.resolve_motor_version(health_fetcher=lambda: {"version": "9.9.9"})
    assert v == "1.6.0" and src == "health"   # cacheado, não refez
    assert calls["n"] == 1
    shadow.reset_version_cache()


def test_build_record_includes_version_source():
    row = shadow.build_record(
        bot_id=1, lead_ref="r", request_id="x",
        observed={"action": "continue"},
        meta={"motor_version": "1.6.0", "motor_version_source": "health"},
    )
    assert row["motor_version"] == "1.6.0"
    assert row["motor_version_source"] == "health"


def test_build_record_version_source_defaults_unknown():
    row = shadow.build_record(bot_id=1, lead_ref="r", request_id="y",
                              observed={"action": "continue"})
    assert row["motor_version_source"] == "unknown"


# ── Runner ──────────────────────────────────────────────────────────────────
def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in tests:
        try:
            fn()
            print(f"✅ {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"💥 {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} offline OK")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
