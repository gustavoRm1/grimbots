import os
import sys
from app import app
from internal_logic.core.models import RedirectPool, db

with app.app_context():
    try:
        pools = RedirectPool.query.all()
        print(f"TOTAL_POOLS:{len(pools)}")
        for p in pools:
            print(f"POOL_ID:{p.id}|NAME:{p.name}|USER_ID:{p.user_id}")
    except Exception as e:
        print(f"ERROR:{str(e)}")
