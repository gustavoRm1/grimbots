"""
WSGI Entry Point
Para produção com Gunicorn
"""

import eventlet
eventlet.monkey_patch(all=True)
print("✅ [INFRA] Eventlet Monkey Patch aplicado com sucesso no WSGI.")

import os
from dotenv import load_dotenv
load_dotenv()  # Carrega o .env antes de qualquer import do Flask

from internal_logic.core.extensions import create_app

# Criar app via factory
application = create_app()

if __name__ == "__main__":
    application.run()



