#!/usr/bin/env python3
"""
Diagnóstico completo do ambiente GRIMBOTS.

Executa verificações em PostgreSQL, Redis/RQ, bots do Telegram,
endpoint /health e logs principais, produzindo um relatório JSON
para orientar correções.

Uso:
    python scripts/diagnostico_sistema.py [--bots 5] [--health-url URL]
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from requests.exceptions import RequestException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Inicializar Flask e extensões do projeto
from app import app, db  # noqa: E402  (importar após carregar dotenv)
from models import Bot  # noqa: E402
from redis_manager import get_redis_connection  # noqa: E402

try:
    from rq import Worker
except ImportError:  # pragma: no cover - RQ deve estar instalado
    Worker = None  # type: ignore


DEFAULT_HEALTH_URL = "http://127.0.0.1:5000/health"
DEFAULT_LOG_PATH = Path("logs/gunicorn.log")


def load_environment() -> None:
    """Carrega variáveis de ambiente (.env) caso ainda não estejam presentes."""

    if os.environ.get("GRIMBOTS_ENV_LOADED"):
        return

    load_dotenv()
    os.environ["GRIMBOTS_ENV_LOADED"] = "1"


def check_dns(host: str = "api.telegram.org") -> Dict[str, object]:
    result: Dict[str, object] = {"host": host}
    start = time.monotonic()
    try:
        ip = socket.gethostbyname(host)
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        result.update({"status": "ok", "ip": ip, "latency_ms": elapsed_ms})
    except socket.gaierror as exc:  # DNS failure
        result.update({"status": "error", "error": str(exc)})
    return result


def check_postgresql(url: Optional[str]) -> Dict[str, object]:
    result: Dict[str, object] = {"status": "skipped"}
    if not url:
        result["error"] = "DATABASE_URL não configurada"
        return result

    result["url"] = url
    try:
        engine = create_engine(url, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            start = time.monotonic()
            conn.execute(text("SELECT 1"))
            conn.commit()
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        result.update({"status": "ok", "latency_ms": elapsed_ms})
    except SQLAlchemyError as exc:
        result.update({"status": "error", "error": str(exc.__cause__ or exc)})
    return result


def check_redis_and_rq() -> Dict[str, object]:
    result: Dict[str, object] = {}
    try:
        redis_conn = get_redis_connection(decode_responses=False)
        start = time.monotonic()
        pong = redis_conn.ping()
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        result["ping"] = {"status": "ok" if pong else "error", "latency_ms": elapsed_ms}

        info = redis_conn.info(section="server")
        result["info"] = {
            "redis_version": info.get("redis_version"),
            "connected_clients": info.get("connected_clients"),
            "uptime_in_seconds": info.get("uptime_in_seconds"),
        }

        if Worker is None:
            result["workers"] = {
                "status": "skipped",
                "error": "rq não instalado"
            }
            return result

        workers = Worker.all(connection=redis_conn)
        queues_map: Dict[str, int] = {}

        for worker in workers:
            try:
                queue_names = worker.queue_names()
            except AttributeError:
                queue_names = [queue.name for queue in getattr(worker, "queues", [])]

            for queue_name in queue_names:
                queues_map[queue_name] = queues_map.get(queue_name, 0) + 1

        result["workers"] = {
            "status": "ok",
            "total_workers": len(workers),
            "by_queue": queues_map
        }
    except Exception as exc:  # pragma: no cover - captura geral de diagnóstico
        result["error"] = str(exc)
        result["status"] = "error"

    return result


def get_bot_tokens(limit: int) -> List[Dict[str, object]]:
    bots_info: List[Dict[str, object]] = []
    with app.app_context():
        query = (
            Bot.query.filter(Bot.token.isnot(None))
            .filter(Bot.token != "")
            .order_by(Bot.id.asc())
            .limit(limit)
        )

        for bot in query:
            token = bot.token.strip()
            if not token:
                continue
            masked = f"{token[:7]}...{token[-4:]}"
            bots_info.append({
                "id": bot.id,
                "username": bot.username,
                "token": token,
                "masked_token": masked
            })

    return bots_info


def check_telegram(tokens: List[Dict[str, object]], timeout: int = 10) -> Dict[str, object]:
    result: Dict[str, object] = {"total_tested": len(tokens), "details": []}
    session = requests.Session()

    for bot in tokens:
        token = bot["token"]
        url = f"https://api.telegram.org/bot{token}/getMe"
        entry: Dict[str, object] = {
            "id": bot["id"],
            "username": bot.get("username"),
            "token": bot["masked_token"],
        }
        try:
            start = time.monotonic()
            resp = session.get(url, timeout=timeout)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            entry["latency_ms"] = elapsed_ms

            if resp.status_code == 200:
                payload = resp.json()
                entry["status_code"] = 200
                entry["ok"] = payload.get("ok")
            else:
                entry.update({
                    "status_code": resp.status_code,
                    "error": resp.text[:200]
                })
        except RequestException as exc:
            entry["error"] = str(exc)
        result["details"].append(entry)

    return result


def check_health_endpoint(url: str) -> Dict[str, object]:
    result: Dict[str, object] = {"url": url}
    try:
        resp = requests.get(url, timeout=5)
        result["status_code"] = resp.status_code
        try:
            result["body"] = resp.json()
        except ValueError:
            result["body"] = resp.text[:200]
    except RequestException as exc:
        result["error"] = str(exc)
    return result


def tail_logs(path: Path, lines: int = 200) -> Dict[str, object]:
    result: Dict[str, object] = {"path": str(path)}
    if not path.exists():
        result["status"] = "missing"
        return result

    try:
        output = subprocess.check_output(["tail", "-n", str(lines), str(path)], text=True)
        result["status"] = "ok"
        result["lines"] = output.splitlines()
    except subprocess.CalledProcessError as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result


def build_report(bot_limit: int, health_url: str) -> Dict[str, object]:
    load_environment()
    database_url = os.environ.get("DATABASE_URL")

    report: Dict[str, object] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "eventlet_no_greendns": os.environ.get("EVENTLET_NO_GREENDNS"),
        "dns": check_dns(),
        "postgres": check_postgresql(database_url),
        "redis": check_redis_and_rq(),
        "health_endpoint": check_health_endpoint(health_url),
        "logs": tail_logs(DEFAULT_LOG_PATH),
    }

    try:
        bots = get_bot_tokens(bot_limit)
        report["telegram"] = check_telegram(bots)
    except Exception as exc:  # pragma: no cover - diagnóstico completo
        report["telegram"] = {"status": "error", "error": str(exc)}

    return report


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnóstico completo do sistema GRIMBOTS")
    parser.add_argument("--bots", type=int, default=5, help="Quantidade de bots para testar (default: 5)")
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL, help="URL do endpoint /health")
    parser.add_argument("--json", action="store_true", help="Imprimir relatório como JSON compacto")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    report = build_report(args.bots, args.health_url)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())


