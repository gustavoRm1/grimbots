import time
import threading
import logging
from app import create_app
from internal_logic.core.extensions import db
from internal_logic.core.models import RemarketingCampaign, Bot
from internal_logic.services.remarketing_service import get_remarketing_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RemarketingDaemon")

def run_daemon():
    app = create_app()
    logger.info("🚀 Motor Enterprise de Remarketing Iniciado...")
    
    with app.app_context():
        while True:
            try:
                # Limpar a sessão para dados sempre frescos
                db.session.remove()
                
                campaigns = RemarketingCampaign.query.filter_by(status='queued').all()
                for campaign in campaigns:
                    logger.info(f"⚡ Nova campanha detectada na fila: ID {campaign.id}")
                    
                    bot = Bot.query.get(campaign.bot_id)
                    if not bot:
                        campaign.status = 'failed'
                        campaign.error_message = 'Bot não encontrado'
                        db.session.commit()
                        continue
                        
                    service = get_remarketing_service(user_id=bot.user_id)
                    stop_event = threading.Event()
                    thread_id = f"daemon_{campaign.id}"
                    
                    # O worker roda sincronamente dentro deste daemon que já é background
                    service._campaign_worker(app, campaign.id, bot.user_id, stop_event, thread_id)
                    
            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")
            
            # Aguarda 5 segundos antes de olhar a fila novamente
            time.sleep(5)

if __name__ == "__main__":
    run_daemon()
