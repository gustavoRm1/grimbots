"""
GRIM-RECONCILER V2 — Reconciliação em tempo real para Átomo Pay.

Características:
- Executa em lotes pequenos (<=30) para evitar sobrecarga.
- Usa lock distribuído em Redis para garantir idempotência por pagamento.
- Consulta a API oficial da Átomo Pay (GET /transactions/{id}) para obter o status real.
- Quando a transação está "paid", reenvia o payload para a fila webhook (process_webhook_async),
  preservando todo o fluxo existente: estatísticas, entregável, Meta Pixel etc.
- Não duplica entregáveis nem eventos, porque reutiliza o processamento oficial do webhook.
"""

import os
from datetime import datetime

import requests

# Garantir que o diretório raiz do projeto esteja no sys.path
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from models import Payment, Gateway
from gateway_factory import GatewayFactory
from redis_manager import get_redis_connection
from tasks_async import webhook_queue, process_webhook_async


BATCH_LIMIT = int(os.environ.get("ATOMOPAY_RECON_BATCH", 30))
LOCK_TTL = int(os.environ.get("ATOMOPAY_RECON_LOCK_TTL", 45))
API_TIMEOUT = float(os.environ.get("ATOMOPAY_RECON_TIMEOUT", 6.0))
API_PATH_TEMPLATE = os.environ.get(
    "ATOMOPAY_RECON_ENDPOINT", "/transactions/{transaction_id}"
)

redis_conn = get_redis_connection()


def _acquire_lock(payment_id: int) -> bool:
    """Tenta adquirir um lock no Redis para o pagamento informado."""
    lock_key = f"grim:reconciler:payment:{payment_id}"
    acquired = redis_conn.set(lock_key, "1", nx=True, ex=LOCK_TTL)
    return bool(acquired)


def _release_lock(payment_id: int) -> None:
    """Libera o lock do pagamento no Redis."""
    redis_conn.delete(f"grim:reconciler:payment:{payment_id}")


def _build_gateway(payment: Payment):
    """
    Retorna instância do gateway Átomo Pay (sem adapter) com credenciais reais
    do dono do bot responsável pelo pagamento.
    """
    if not payment.bot:
        return None

    gateway = Gateway.query.filter_by(
        user_id=payment.bot.user_id,
        gateway_type="atomopay",
        is_active=True,
        is_verified=True,
    ).first()

    if not gateway:
        return None

    creds = {
        "api_token": gateway.api_key,
        "product_hash": gateway.product_hash,
        "offer_hash": gateway.offer_hash,
    }

    # use_adapter=False → instância direta de AtomPayGateway (permite usar _make_request)
    return GatewayFactory.create_gateway("atomopay", creds, use_adapter=False)


def _fetch_atomopay_status(gateway_instance, payment: Payment):
    """
    Consulta a API da Átomo Pay para obter o status atualizado de uma transação.

    Tenta com os identificadores conhecidos (hash primeiro, depois id numérico).
    Retorna o payload bruto (dict) em caso de sucesso; caso contrário, None.
    """
    candidates = [
        str(payment.gateway_transaction_hash or "").strip(),
        str(payment.gateway_transaction_id or "").strip(),
        str(payment.payment_id or "").strip(),
    ]
    candidates = [c for c in candidates if c]

    for candidate in candidates:
        try:
            endpoint = API_PATH_TEMPLATE.format(transaction_id=candidate)
            response = gateway_instance._make_request("GET", endpoint, params=None)  # type: ignore[attr-defined]
        except Exception:
            continue

        if not response or response.status_code != 200:
            continue

        try:
            payload = response.json()
        except ValueError:
            continue

        if isinstance(payload, dict):
            if payload.get("success") and isinstance(payload.get("data"), dict):
                return payload["data"]
            return payload

    return None


def _queue_webhook(payload: dict) -> None:
    """
    Processa o payload usando a mesma função oficial dos webhooks.
    Por padrão, executa inline (síncrono) para garantir reconciliação imediata.
    Se quiser usar a fila, defina ATOMOPAY_RECON_USE_QUEUE=1.
    """
    payload = dict(payload)
    payload.setdefault("event", "transaction")
    payload["_reconciled_by"] = "grim_reconciler_v2"
    payload["_reconciled_at"] = datetime.utcnow().isoformat()

    use_queue = os.environ.get("ATOMOPAY_RECON_USE_QUEUE", "0") in {"1", "true", "yes"}

    if use_queue:
        if not webhook_queue:
            print("⚠️ webhook_queue indisponível – verifique os workers RQ.")
            return
        webhook_queue.enqueue(
            process_webhook_async,
            "atomopay",
            payload,
        )
    else:
        process_webhook_async("atomopay", payload)


def main():
    with app.app_context():
        pendentes = (
            Payment.query.filter_by(gateway_type="atomopay", status="pending")
            .order_by(Payment.id.desc())
            .limit(BATCH_LIMIT)
            .all()
        )

        if not pendentes:
            print("Nenhum payment pending encontrado.")
            return

        print(f"🔍 Processando {len(pendentes)} payment(s) pending (Átomo Pay).")

        for payment in pendentes:
            if not _acquire_lock(payment.id):
                continue  # outro processo já está tratando

            try:
                transaction_id = (
                    payment.gateway_transaction_id
                    or payment.gateway_transaction_hash
                    or payment.payment_id
                )

                gateway_instance = _build_gateway(payment)
                if not gateway_instance or not transaction_id:
                    continue

                api_payload = _fetch_atomopay_status(gateway_instance, payment)
                if not api_payload:
                    continue

                status = (
                    api_payload.get("payment_status")
                    or api_payload.get("status")
                    or ""
                ).lower()

                if status != "paid":
                    continue  # ainda aguardando pagamento

                _queue_webhook(api_payload)
                print(
                    f"✅ Payment {payment.payment_id} ({payment.id}) reconciliação enfileirada."
                )
            finally:
                _release_lock(payment.id)


if __name__ == "__main__":
    main()

