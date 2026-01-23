import json
import argparse
from datetime import datetime

from app import app, db  # type: ignore
from models import Payment  # type: ignore
from utils.tracking_service import TrackingServiceV4  # type: ignore


def fmt_dt(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def find_payment(id_value: int | None, payment_id_value: str | None, gateway_id_value: str | None):
    """Find payment by priority: id -> payment_id -> gateway_transaction_id."""
    if id_value is not None:
        payment = Payment.query.filter_by(id=id_value).first()
        if payment:
            return payment
    if payment_id_value:
        payment = Payment.query.filter_by(payment_id=payment_id_value).first()
        if payment:
            return payment
    if gateway_id_value:
        payment = Payment.query.filter_by(gateway_transaction_id=gateway_id_value).first()
        if payment:
            return payment
    return None


def audit_payment(id_value: int | None, payment_id_value: str | None, gateway_id_value: str | None):
    with app.app_context():
        payment = find_payment(id_value, payment_id_value, gateway_id_value)
        if not payment:
            # Fallback: listar candidatos por prefix/substring para ajudar a achar
            candidates = []
            if payment_id_value:
                candidates = [p.payment_id for p in Payment.query.filter(Payment.payment_id.ilike(f"%{payment_id_value}%")).limit(5).all()]
            print(json.dumps({
                "error": "payment not found",
                "searched": {
                    "id": id_value,
                    "payment_id": payment_id_value,
                    "gateway_transaction_id": gateway_id_value,
                },
                "candidates_payment_id_contains": candidates
            }, ensure_ascii=False, indent=2))
            return

        tracking_token = getattr(payment, "tracking_token", None)
        info = {
            "payment": {
                "id": payment.id,
                "payment_id": payment.payment_id,
                "bot_id": payment.bot_id,
                "amount": payment.amount,
                "status": payment.status,
                "created_at": fmt_dt(payment.created_at),
                "paid_at": fmt_dt(payment.paid_at),
                "tracking_token": tracking_token,
            }
        }

        ts = TrackingServiceV4()
        redis_payload = None
        if tracking_token:
            try:
                redis_payload = ts.recover_tracking_data(tracking_token)
            except Exception as e:
                redis_payload = {"error": str(e)}

        info["redis_payload"] = {
            "pixel_id": redis_payload.get("pixel_id") if redis_payload else None,
            "meta_pixel_id": redis_payload.get("meta_pixel_id") if redis_payload else None,
            "redirect_id": redis_payload.get("redirect_id") if redis_payload else None,
            "fbp": redis_payload.get("fbp") if redis_payload else None,
            "fbc": redis_payload.get("fbc") if redis_payload else None,
            "utm_source": redis_payload.get("utm_source") if redis_payload else None,
            "utm_campaign": redis_payload.get("utm_campaign") if redis_payload else None,
            "event_source_url": redis_payload.get("event_source_url") if redis_payload else None,
            "raw": redis_payload,
        } if redis_payload is not None else None

        print(json.dumps(info, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Audit sale tracking in DB + Redis")
    parser.add_argument("id", nargs="?", type=int, default=None, help="Payment primary key id (int).")
    parser.add_argument("--payment-id", dest="payment_id_value", help="Payment.payment_id (string gateway reference)")
    parser.add_argument("--gateway-id", dest="gateway_id_value", help="gateway_transaction_id (string)")
    parser.add_argument("--default", action="store_true", help="Use defaults: id=4015990 if nothing passed")
    args = parser.parse_args()
    id_value = args.id
    payment_id_value = args.payment_id_value
    gateway_id_value = args.gateway_id_value

    if args.default and not any([id_value, payment_id_value, gateway_id_value]):
        id_value = 4015990

    audit_payment(id_value, payment_id_value, gateway_id_value)


if __name__ == "__main__":
    main()
