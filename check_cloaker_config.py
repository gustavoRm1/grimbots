"""
Verifica configuração do cloaker do pool ads01
"""

from app import app, db
from models import RedirectPool

with app.app_context():
    pool = RedirectPool.query.filter_by(slug='ads01').first()
    
    if not pool:
        print("❌ Pool não encontrado")
    else:
        print("=" * 80)
        print(f"🔗 Pool: {pool.name}")
        print(f"   Slug: {pool.slug}")
        print("=" * 80)
        print()
        print(f"🛡️ Cloaker Habilitado: {pool.meta_cloaker_enabled}")
        print(f"📝 Parâmetro Esperado: {pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
        print()
        print("=" * 80)
        print("✅ LINK CORRETO PARA USAR:")
        print("=" * 80)
        print()
        print(f"https://seudominio.com/go/{pool.slug}?{pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
        print()
        print("=" * 80)
        print("⚠️ SE O CLIENTE USAR LINK SEM PARÂMETRO:")
        print("=" * 80)
        print()
        print(f"❌ https://seudominio.com/go/{pool.slug}")
        print("   RESULTADO: BLOQUEADO (invalid_grim)")
        print()

