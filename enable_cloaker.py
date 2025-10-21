"""
RE-HABILITA CLOAKER
===================
Depois que o cliente corrigir o link

EXECUTAR:
---------
python enable_cloaker.py
"""

from app import app, db
from models import RedirectPool

with app.app_context():
    pool = RedirectPool.query.filter_by(slug='ads01').first()
    
    if not pool:
        print("❌ Pool não encontrado")
    else:
        print("=" * 80)
        print("🛡️ RE-HABILITANDO CLOAKER")
        print("=" * 80)
        print()
        print(f"Pool: {pool.name}")
        print(f"Cloaker ANTES: {pool.meta_cloaker_enabled}")
        
        pool.meta_cloaker_enabled = True
        db.session.commit()
        
        print(f"Cloaker DEPOIS: {pool.meta_cloaker_enabled}")
        print()
        print(f"Parâmetro: {pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
        print()
        print("=" * 80)
        print("✅ CLOAKER RE-HABILITADO!")
        print("=" * 80)
        print()
        print("Link correto:")
        print(f"https://seudominio.com/go/{pool.slug}?{pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
        print()
        print("⚠️ IMPORTANTE: Restart o servidor")
        print("pkill -9 gunicorn && nohup gunicorn -c gunicorn_config.py wsgi:app > /var/log/gunicorn.log 2>&1 &")
        print()

