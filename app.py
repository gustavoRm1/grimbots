"""
SaaS Bot Manager - Aplicação Principal (Factory Pattern)
✅ LAZARUS RECOVERY: Monólito refatorado para Factory em 2026-04-06
"""

import logging
from internal_logic.core.extensions import create_app

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# ✅ FACTORY PATTERN: Criar app via factory
app = create_app()

# ✅ EXPORTS PARA WSGI/CRON
application = app

if __name__ == '__main__':
    app.run(debug=True)
