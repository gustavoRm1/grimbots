"""
WSGI Entry Point
Para produção com Gunicorn
"""

from app import app, socketio

if __name__ == "__main__":
    socketio.run(app)



