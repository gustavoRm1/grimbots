from typing import Optional

from app import app, db
from models import Payment, BotUser
from sqlalchemy import or_

# Dados alvo
TARGET_REFERENCE = 'BOT132-1769190542-c6f0279f-1769190542652-26026f61'
TARGET_PIXEL_HTML = '1175627784393660'


def find_payment() -> Optional[Payment]:
    with app.app_context():
        payment = (
            Payment.query.filter(
                or_(
                    Payment.payment_id == TARGET_REFERENCE,
                    Payment.gateway_transaction_id == TARGET_REFERENCE,
                    Payment.gateway_transaction_hash == TARGET_REFERENCE,
                )
            ).first()
        )
        return payment


def find_bot_user(bot_id: int, telegram_user_id: str) -> Optional[BotUser]:
    with app.app_context():
        return BotUser.query.filter_by(bot_id=bot_id, telegram_user_id=str(telegram_user_id), archived=False).first()


def main():
    payment = find_payment()

    print("=== AUDITORIA DE DNA (VIA BOTUSER) ===")

    if not payment:
        print("1. Pagamento Encontrado: Não")
        print("2. BotUser Encontrado: Não")
        print("3. DNA do Usuário (DB):\n   - Pixel Salvo (campaign_code): -\n   - FBC Salvo: -")
        print("---------------------------------------")
        print("VEREDITO FINAL:")
        print(f"O Pixel disparado no HTML ({TARGET_PIXEL_HTML}) bate com o salvo no Usuário?")
        print("[ ] SIM - O usuário pertence a este Pixel.")
        print("[X] NÃO - O usuário está marcado com outro Pixel.")
        return

    # Extrair bot_id e telegram_user_id
    bot_id = payment.bot_id
    telegram_user_id = payment.customer_user_id or payment.customer_username or ''

    print("1. Pagamento Encontrado: Sim")

    bot_user = find_bot_user(bot_id, telegram_user_id)
    if bot_user:
        print(f"2. BotUser Encontrado: Sim (ID Telegram: {bot_user.telegram_user_id})")
        pixel_saved = bot_user.campaign_code or '-'
        fbc_saved = bot_user.fbc or '-'
    else:
        print("2. BotUser Encontrado: Não")
        pixel_saved = '-'
        fbc_saved = '-'

    print("3. DNA do Usuário (DB):")
    print(f"   - Pixel Salvo (campaign_code): {pixel_saved}")
    print(f"   - FBC Salvo: {fbc_saved}")
    print("---------------------------------------")
    print("VEREDITO FINAL:")
    print(f"O Pixel disparado no HTML ({TARGET_PIXEL_HTML}) bate com o salvo no Usuário?")

    if bot_user and str(pixel_saved) == str(TARGET_PIXEL_HTML):
        print("[X] SIM - O usuário pertence a este Pixel.")
        print("[ ] NÃO - O usuário está marcado com outro Pixel.")
    else:
        print("[ ] SIM - O usuário pertence a este Pixel.")
        print("[X] NÃO - O usuário está marcado com outro Pixel.")


if __name__ == "__main__":
    main()
