#!/usr/bin/env python3
from __future__ import annotations

import os
from dotenv import load_dotenv
# Carregar variáveis de ambiente com caminho absoluto
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

"""
Rotina automatizada de recuperação do ambiente GRIMBOTS.

Fluxo:
 1. Carrega variáveis de ambiente (.env).
 2. Termina processos existentes (Gunicorn + workers RQ).
 3. Reinicia Gunicorn com EVENTLET_NO_GREENDNS habilitado.
 4. Reinicia workers RQ (gateway, webhook, tasks).
 5. Aguarda estabilização e executa o diagnóstico completo.
 6. Persiste o relatório JSON em logs/diagnostico_YYYYmmdd_HHMMSS.json e exibe resumo.

Uso:
    python scripts/recuperacao_automatica.py [--bots 5]
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv

# ✅ CONEXÃO DIRETA: Importar app já inicializado
from app import app
from internal_logic.core.extensions import db


ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

HEALTH_URL = "http://127.0.0.1:5000/health"


def load_environment() -> None:
    load_dotenv()


def run(cmd: List[str], *, check: bool = True, env: Dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, env=env)


def kill_processes(pattern: str) -> None:
    try:
        run(["pkill", "-f", pattern], check=False)
    except FileNotFoundError:
        print("[⚠️] pkill não disponível no PATH; ignorando")


def start_background(cmd: List[str], log_path: Path, env: Dict[str, str]) -> None:
    log_file = open(log_path, "ab", buffering=0)
    subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid,
        close_fds=True,
    )
    print(f"[🚀] Processo iniciado: {' '.join(cmd)} (log: {log_path})")


def restart_gunicorn(env: Dict[str, str]) -> None:
    print("[🔁] Reiniciando Gunicorn...")
    kill_processes("gunicorn -c gunicorn_config.py")
    kill_processes("gunicorn: worker")

    env = env.copy()
    env.setdefault("EVENTLET_NO_GREENDNS", "yes")

    start_background(
        ["python", "-m", "gunicorn.app.wsgiapp", "-c", "gunicorn_config.py", "wsgi:application"],
        LOG_DIR / "gunicorn.log",
        env,
    )


def restart_rq_workers(env: Dict[str, str]) -> None:
    queues = ["gateway", "webhook", "tasks"]
    for queue in queues:
        print(f"[🔁] Reiniciando worker RQ: {queue}")
        kill_processes(f"start_rq_worker.py {queue}")
        start_background(
            ["python", "start_rq_worker.py", queue],
            LOG_DIR / f"rq-{queue}.log",
            env,
        )


def run_diagnostico(bot_limit: int) -> Dict[str, object]:
    """Diagnóstico pós-restart - script detalhado removido na Order 66"""
    print("[ℹ️] Diagnóstico detalhado ignorado (script removido na Order 66)")
    return {"status": "skipped", "reason": "diagnostico_sistema.py removido na Order 66"}


def summarize(report: Dict[str, object]) -> None:
    print("\n===== RESUMO DO DIAGNÓSTICO =====")
    status = report.get("health_endpoint", {}).get("body", {}).get("status")
    print(f"/health: {status}")

    redis_info = report.get("redis", {})
    workers = redis_info.get("workers", {})
    print(
        "RQ workers:",
        workers.get("total_workers"),
        workers.get("by_queue"),
    )

    telegram = report.get("telegram", {})
    if telegram:
        failures = [d for d in telegram.get("details", []) if not d.get("ok")]
        if failures:
            print("Bots com erro:")
            for entry in failures:
                print(
                    f"  - {entry.get('username')} ({entry.get('status_code')}): {entry.get('error')}"
                )
        else:
            print("Todos os bots testados responderam OK")


def wait_for_health(url: str, timeout: int = 30, interval: int = 2) -> bool:
    print(f"[⏳] Aguardando /health responder 200 (timeout {timeout}s)...")
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                print("[✅] /health respondeu 200")
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    print("[⚠️] /health não respondeu 200 dentro do timeout")
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recuperação automatizada do ambiente GRIMBOTS")
    parser.add_argument("--bots", type=int, default=10, help="Quantidade de bots para testar no diagnóstico final")
    parser.add_argument("--sleep", type=int, default=8, help="Tempo (s) de espera entre restart e diagnóstico")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_environment()

    env = os.environ.copy()

    restart_gunicorn(env)
    restart_rq_workers(env)

    # Conceder tempo para processos inicializarem e conexões se estabilizarem
    print(f"[⏳] Aguardando {args.sleep}s para estabilização inicial...")
    time.sleep(args.sleep)

    wait_for_health(HEALTH_URL)

    try:
        report = run_diagnostico(args.bots)
    except subprocess.CalledProcessError as exc:
        print("[❌] Erro ao executar diagnóstico:", exc.stdout, exc.stderr, sep="\n")
        return 1

    summarize(report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("[⚠️] Execução interrompida pelo usuário")
        sys.exit(130)


