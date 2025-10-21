"""
DESABILITA CLOAKER TEMPORARIAMENTE
===================================
Use apenas se o cliente NÃO conseguir atualizar o link agora

EXECUTAR:
---------
python disable_cloaker_emergency.py
"""

from app import app, db
from models import RedirectPool

with app.app_context():
    pool = RedirectPool.query.filter_by(slug='ads01').first()
    
    if not pool:
        print("❌ Pool não encontrado")
    else:
        print("=" * 80)
        print("⚠️ DESABILITANDO CLOAKER TEMPORARIAMENTE")
        print("=" * 80)
        print()
        print(f"Pool: {pool.name}")
        print(f"Cloaker ANTES: {pool.meta_cloaker_enabled}")
        
        pool.meta_cloaker_enabled = False
        db.session.commit()
        
        print(f"Cloaker DEPOIS: {pool.meta_cloaker_enabled}")
        print()
        print("=" * 80)
        print("✅ CLOAKER DESABILITADO!")
        print("=" * 80)
        print()
        print("⚠️ IMPORTANTE:")
        print("   1. Restart o servidor: pkill -9 gunicorn && nohup gunicorn -c gunicorn_config.py wsgi:app > /var/log/gunicorn.log 2>&1 &")
        print("   2. Todos os links vão funcionar agora (sem validação)")
        print("   3. Re-habilite depois quando cliente corrigir o link")
        print()

