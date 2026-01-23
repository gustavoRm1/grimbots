import os
from typing import Optional

from app import app, db
from models import Payment, RedirectPool
from utils.tracking_service import TrackingServiceV4
from sqlalchemy import or_

# Dados alvo
TARGET_GATEWAY_ID = '4016781'
TARGET_REFERENCE = 'BOT132-1769190542-c6f0279f-1769190542652-26026f61'
TARGET_PIXEL_HTML = '1175627784393660'


def find_payment() -> Optional[Payment]:
    with app.app_context():
        payment = (
            Payment.query.filter(
                or_(
                    Payment.payment_id == TARGET_GATEWAY_ID,
                    Payment.gateway_transaction_id == TARGET_GATEWAY_ID,
                    Payment.gateway_transaction_hash == TARGET_GATEWAY_ID,
                    Payment.payment_id == TARGET_REFERENCE,
                    Payment.gateway_transaction_id == TARGET_REFERENCE,
                    Payment.gateway_transaction_hash == TARGET_REFERENCE,
                )
            ).first()
        )
        return payment


def recover_tracking(token: Optional[str]):
    if not token:
        return {}
    svc = TrackingServiceV4()
    return svc.recover_tracking_data(token) or {}


def load_redirect_pool(redirect_id: Optional[str]):
    if not redirect_id:
        return None
    try:
        return db.session.get(RedirectPool, int(redirect_id))
    except Exception:
        return None


def main():
    payment = find_payment()

    print("=== RELATÓRIO DE DNA ===")
    if not payment:
        print("1. Venda Encontrada: Não")
        print("2. Token de Rastreamento: -")
        print("3. Dados no Redis:\n   - Redirect ID de Origem: -\n   - Pixel ID na Sessão: -")
        print("4. Dados do Redirecionador Pai (Tabela SQL):\n   - Nome/Slug: -\n   - Pixel Configurado no Banco: -")
        print("---------------------------------------------")
        print("VEREDITO: O Pixel do HTML ({}) pertence ao Redirect Pai?".format(TARGET_PIXEL_HTML))
        print("[ ] SIM, ISOLAMENTO CONFIRMADO.")
        print("[ ] NÃO, VAZAMENTO DETECTADO (O pai usa pixel X, mas disparou Y).")
        return

    tracking_token = payment.tracking_token
    tracking_data = recover_tracking(tracking_token)
    redirect_id = tracking_data.get('redirect_id') or tracking_data.get('pool_id')
    pixel_in_session = tracking_data.get('pixel_id') or tracking_data.get('meta_pixel_id')
    redirect_pool = load_redirect_pool(redirect_id)

    print(f"1. Venda Encontrada: Sim (ID DB: {payment.id}, payment_id: {payment.payment_id}, gateway_tx_id: {payment.gateway_transaction_id})")
    print(f"2. Token de Rastreamento: {tracking_token or '-'}")
    print("3. Dados no Redis:")
    print(f"   - Redirect ID de Origem: {redirect_id or '-'}")
    print(f"   - Pixel ID na Sessão: {pixel_in_session or '-'}")

    redirect_name = '-'
    redirect_pixel_db = '-'
    if redirect_pool:
        redirect_name = f"{redirect_pool.name} (slug: {redirect_pool.slug}, id: {redirect_pool.id})"
        redirect_pixel_db = redirect_pool.meta_pixel_id or '-'

    print("4. Dados do Redirecionador Pai (Tabela SQL):")
    print(f"   - Nome/Slug: {redirect_name}")
    print(f"   - Pixel Configurado no Banco: {redirect_pixel_db}")
    print("---------------------------------------------")
    print(f"VEREDITO: O Pixel do HTML ({TARGET_PIXEL_HTML}) pertence ao Redirect Pai?")

    if redirect_pixel_db and str(redirect_pixel_db) == str(TARGET_PIXEL_HTML):
        print("[X] SIM, ISOLAMENTO CONFIRMADO.")
        print("[ ] NÃO, VAZAMENTO DETECTADO (O pai usa pixel X, mas disparou Y).")
    else:
        print("[ ] SIM, ISOLAMENTO CONFIRMADO.")
        print("[X] NÃO, VAZAMENTO DETECTADO (O pai usa pixel X, mas disparou Y).")


if __name__ == "__main__":
    main()
