"""
Coleta automática de logs de Purchase para um pagamento específico.

Uso (exemplos):
  python scripts/collect_purchase_logs.py --payment-id 12345
  python scripts/collect_purchase_logs.py --gateway-id 2384889
  python scripts/collect_purchase_logs.py --payment-hash 2384889

O script:
- Localiza o Payment (id/payment_id/gateway_transaction_id/gateway_transaction_hash)
- Imprime dados-chave (event_id, tracking_token, fbclid, is_remarketing)
- Procura nos arquivos de log (logs/*.log) as linhas relevantes:
    * event_source_url recuperado
    * tracking_data vazio / fallback
    * REMARKETING ATTRIBUTED USING STORED CLICK CONTEXT
    * Meta Pixel Purchase - Parâmetros (fbp/fbc/external_id hash)
    * Payload enviado para Meta (antes do POST)
- Limita a quantidade de linhas retornadas por arquivo para evitar explosão de saída.

Requisitos: executar na raiz do projeto, com venv ativado (ou PYTHONPATH configurado).
"""

import argparse
import glob
import os
import sys
from collections import deque
from pathlib import Path

# Garantir que o app seja importável
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from app import app, db
    from models import Payment
except Exception as e:  # pragma: no cover - diagnóstico rápido
    print(f"❌ Erro ao importar app/models: {e}")
    sys.exit(1)


def find_payment(args):
    with app.app_context():
        q = Payment.query
        if args.payment_id:
            q = q.filter(Payment.id == args.payment_id)
        elif args.payment_slug:
            q = q.filter(Payment.payment_id == args.payment_slug)
        elif args.gateway_id:
            q = q.filter(Payment.gateway_transaction_id == args.gateway_id)
        elif args.gateway_hash:
            q = q.filter(Payment.gateway_transaction_hash == args.gateway_hash)
        else:
            return None
        return q.first()


def print_payment_info(p):
    print("✅ Payment encontrado")
    print(f"  id                : {p.id}")
    print(f"  payment_id        : {p.payment_id}")
    print(f"  status            : {p.status}")
    print(f"  is_remarketing    : {p.is_remarketing}")
    print(f"  remarketing_campaign_id: {p.remarketing_campaign_id}")
    print(f"  event_id (expected): purchase_{p.id}")
    print(f"  tracking_token    : {p.tracking_token}")
    print(f"  fbclid            : {p.fbclid}")
    print(f"  fbp               : {p.fbp}")
    print(f"  fbc               : {p.fbc}")
    print(f"  click_context_url : {p.click_context_url}")


def grep_logs(event_id: str, payment_id: str, max_matches: int = 50):
    """Busca linhas relevantes nos logs/*.log com limites de saída."""
    patterns = [
        "META PURCHASE",
        "event_source_url recuperado",
        "tracking_data vazio",
        "REMARKETING ATTRIBUTED USING STORED CLICK CONTEXT",
        "Payload enviado para Meta",
        payment_id,
        event_id,
    ]

    log_files = glob.glob(str(BASE_DIR / "logs" / "*.log"))
    if not log_files:
        print("⚠️ Nenhum arquivo em logs/*.log encontrado")
        return

    for lf in log_files:
        matches = deque(maxlen=max_matches)
        try:
            with open(lf, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    lower = line.lower()
                    for pat in patterns:
                        if pat and pat.lower() in lower:
                            matches.append(line.rstrip())
                            break
        except Exception as e:  # pragma: no cover - leitura defensiva
            print(f"⚠️ Erro lendo {lf}: {e}")
            continue

        if matches:
            print(f"\n----- {lf} (últimos {len(matches)} hits, max {max_matches}) -----")
            for m in matches:
                print(m)


def main():
    parser = argparse.ArgumentParser(description="Coleta de logs de Purchase (remarketing)")
    parser.add_argument("--payment-id", type=int, help="Payment.id numérico")
    parser.add_argument("--payment-slug", help="Payment.payment_id completo")
    parser.add_argument("--gateway-id", help="gateway_transaction_id")
    parser.add_argument("--gateway-hash", help="gateway_transaction_hash")
    parser.add_argument("--max-matches", type=int, default=50, help="Máximo de linhas por arquivo")
    args = parser.parse_args()

    p = find_payment(args)
    if not p:
        print("❌ Payment não encontrado com os filtros fornecidos")
        sys.exit(1)

    print_payment_info(p)
    event_id = f"purchase_{p.id}"
    grep_logs(event_id=event_id, payment_id=str(p.payment_id), max_matches=args.max_matches)


if __name__ == "__main__":
    main()
