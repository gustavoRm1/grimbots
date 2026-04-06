"""
WSGI Entry Point
Para produção com Gunicorn
"""

import eventlet
eventlet.monkey_patch(all=True)
print("✅ [INFRA] Eventlet Monkey Patch aplicado com sucesso no WSGI.")

import os
from dotenv import load_dotenv
# Caminho absoluto para garantir o carregamento correto em qualquer contexto
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

from internal_logic.core.extensions import create_app

# Criar app via factory
application = create_app()

if __name__ == "__main__":
    application.run()



