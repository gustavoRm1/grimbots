"""E4 offline — assercao executavel (nao substitui o runner; valida invariantes).

Roda a simulacao roteirizada e checa propriedades objetivas. NAO alega conversao.
"""
import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import e4_runner as e4  # noqa: E402


@pytest.fixture(scope="module")
def corpus():
    return json.loads((e4.E4_DIR / "scenarios.json").read_text())


@pytest.fixture(scope="module")
def run(corpus):
    out = {}
    for version in (e4.V10, e4.V11):
        logs, memory = [], []
        for sc in corpus["scenarios"]:
            l, m = e4.simulate(version, sc, corpus)
            logs.extend(l)
            memory.append(m)
        out[version] = {"logs": logs, "memory": memory,
                        "summary": e4.summarize(version, logs, memory)}
    return out


def test_both_versions_run_and_quality(run):
    for version in (e4.V10, e4.V11):
        s = run[version]["summary"]
        assert s["turns"] > 0
        assert s["action_allowed_pct"] == 100.0
        assert s["message_nonempty_pct"] == 100.0
        assert s["question_when_asked_pct"] == 100.0


def test_v11_carries_context_v10_does_not(run):
    assert run[e4.V11]["summary"]["payload_has_context_pct"] == 100.0
    assert run[e4.V10]["summary"]["payload_has_context_pct"] == 0.0


def test_memory_consistent_all_scenarios(run):
    for version in (e4.V10, e4.V11):
        assert run[version]["summary"]["memory_consistent"] is True
        for m in run[version]["memory"]:
            assert m["turn_count"] == m["expected_turns"]
            assert m["questions_deduped"] is True
            assert m["summary_not_injected"] is True


def test_state_update_whitelist_enforced(run):
    v11 = [e for e in run[e4.V11]["logs"] if e.get("state_update_ignored_summary")]
    assert len(run[e4.V11]["logs"]) == len(
        [e for e in run[e4.V11]["logs"]])  # sanity
    # toda turno v1.1 enviou state_update com chave fora da whitelist
    assert all("conversation_summary" not in (m["collected_information"] or {})
               for m in run[e4.V11]["memory"])


def test_objection_handling_scripted_capability(run):
    assert run[e4.V11]["summary"]["objection_handled_pct"] == 100.0
    assert run[e4.V10]["summary"]["objection_handled_pct"] < 100.0


def test_d12_alias_normalization(run):
    for version in (e4.V10, e4.V11):
        aliases = [e for e in run[version]["logs"] if e["intent_kind"] == "alias"]
        assert aliases, "corpus deve exercitar ao menos um alias de intent (D12)"
        for e in aliases:
            assert e["intent"] != e["intent_original"]
            assert e["intent"] in {"interesse", "duvida"}


def test_deterministic(corpus):
    def snapshot():
        snap = {}
        for version in (e4.V10, e4.V11):
            for sc in corpus["scenarios"]:
                logs, _ = e4.simulate(version, sc, corpus)
                snap[(version, sc["id"])] = [(e["action"], e["intent"], e["passed"]) for e in logs]
        return snap
    assert snapshot() == snapshot()


def test_runner_writes_outputs(corpus, tmp_path, monkeypatch):
    monkeypatch.setattr(e4, "OUT_DIR", tmp_path)
    assert e4.main(["--quiet"]) == 0
    for name in ("report.md", "results.json", "failures.md", "run.log"):
        assert (tmp_path / name).exists()
    data = json.loads((tmp_path / "results.json").read_text())
    assert set(data["summary"]) == {e4.V10, e4.V11}
