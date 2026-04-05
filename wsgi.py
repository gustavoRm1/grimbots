"""
WSGI Entry Point
Para produção com Gunicorn
"""

import eventlet
eventlet.monkey_patch(all=True)
print("✅ [INFRA] Eventlet Monkey Patch aplicado com sucesso no WSGI.")

import os
from app import app as application

if __name__ == "__main__":
    application.run()



