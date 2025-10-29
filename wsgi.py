"""
WSGI Entry Point
Para produção com Gunicorn
"""

import os
import time
from app import app, socketio, restart_all_active_bots

# ✅ Reiniciar bots que estavam rodando quando servidor iniciar
# Proteção contra execução múltipla em workers do gunicorn (baseado em arquivo)
LOCK_FILE = "/tmp/grimbots_restart_bots.lock" if os.name != 'nt' else "C:/temp/grimbots_restart_bots.lock"

def _ensure_single_execution():
    """Garante que restart_all_active_bots() execute apenas uma vez"""
    try:
        # Criar diretório temporário se não existir
        lock_dir = os.path.dirname(LOCK_FILE)
        if lock_dir and not os.path.exists(lock_dir):
            try:
                os.makedirs(lock_dir, exist_ok=True)
            except:
                pass  # Se falhar, tenta criar arquivo mesmo assim
        
        # Verificar se já foi executado (marcador de tempo)
        done_file = LOCK_FILE + ".done"
        if os.path.exists(done_file):
            # Verificar se foi executado há menos de 30 segundos (evita reiniciar em cada worker)
            try:
                with open(done_file, 'r') as f:
                    last_run = float(f.read().strip())
                if time.time() - last_run < 30:
                    return False  # Já foi executado recentemente
            except:
                pass  # Se erro ao ler, continua e executa
        
        # Tentar criar lock file (exclusivo)
        try:
            # No Windows, usar modo exclusivo
            if os.name == 'nt':
                import msvcrt
                lock_file = open(LOCK_FILE, 'w')
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except IOError:
                    lock_file.close()
                    return False  # Outro processo já tem o lock
            else:
                # Linux/Unix: usar fcntl
                import fcntl
                lock_file = open(LOCK_FILE, 'w')
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    lock_file.close()
                    return False  # Outro processo já tem o lock
            
            # Executar reinicialização
            with app.app_context():
                restart_all_active_bots()
            
            # Marcar como executado
            try:
                with open(done_file, 'w') as f:
                    f.write(str(time.time()))
            except:
                pass
            
            lock_file.close()
            return True
        except Exception as e:
            # Fallback: executar mesmo se lock falhar (melhor reiniciar bots do que não reiniciar)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Erro ao adquirir lock, tentando reiniciar bots mesmo assim: {e}")
            try:
                with app.app_context():
                    restart_all_active_bots()
            except Exception as e2:
                logger.error(f"❌ Erro ao reiniciar bots no startup: {e2}", exc_info=True)
            return False
    except Exception as e:
        # Último fallback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Erro crítico ao reiniciar bots: {e}", exc_info=True)
        return False

# Executar apenas uma vez
try:
    _ensure_single_execution()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"❌ Erro crítico ao reiniciar bots: {e}", exc_info=True)

if __name__ == "__main__":
    socketio.run(app)



