#!/usr/bin/env python
"""
TRACKING ELITE - ANÁLISE DE PERFORMANCE
========================================

Script para medir efetividade do tracking elite:
- % de usuários com IP/UA capturado
- Tempo médio entre click e /start
- Taxa de match Redis ↔ BotUser
- Distribuição de dispositivos/navegadores

Uso:
    python tracking_elite_analytics.py

Autor: QI 500 Elite Team
Data: 2025-10-21
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

def analyze_tracking_elite():
    print("=" * 80)
    print("🎯 TRACKING ELITE - ANÁLISE DE PERFORMANCE")
    print("=" * 80)
    print()
    
    from app import app, db
    from models import BotUser
    from sqlalchemy import func
    
    with app.app_context():
        # Período de análise: últimas 24h
        since = datetime.now() - timedelta(hours=24)
        
        # Total de usuários no período
        total_users = BotUser.query.filter(
            BotUser.first_interaction >= since
        ).count()
        
        if total_users == 0:
            print("⚠️ Nenhum usuário nos últimos 24h")
            return
        
        # Usuários com IP capturado
        users_with_ip = BotUser.query.filter(
            BotUser.first_interaction >= since,
            BotUser.ip_address.isnot(None)
        ).count()
        
        # Usuários com User-Agent capturado
        users_with_ua = BotUser.query.filter(
            BotUser.first_interaction >= since,
            BotUser.user_agent.isnot(None)
        ).count()
        
        # Usuários com tracking completo
        users_with_full_tracking = BotUser.query.filter(
            BotUser.first_interaction >= since,
            BotUser.ip_address.isnot(None),
            BotUser.user_agent.isnot(None),
            BotUser.tracking_session_id.isnot(None)
        ).count()
        
        # Calcular porcentagens
        ip_capture_rate = (users_with_ip / total_users * 100) if total_users > 0 else 0
        ua_capture_rate = (users_with_ua / total_users * 100) if total_users > 0 else 0
        full_tracking_rate = (users_with_full_tracking / total_users * 100) if total_users > 0 else 0
        
        print("📊 TAXA DE CAPTURA (últimas 24h)")
        print("-" * 80)
        print(f"Total de usuários:           {total_users:>6}")
        print(f"Com IP capturado:            {users_with_ip:>6}  ({ip_capture_rate:>5.1f}%)")
        print(f"Com User-Agent capturado:    {users_with_ua:>6}  ({ua_capture_rate:>5.1f}%)")
        print(f"Com tracking completo:       {users_with_full_tracking:>6}  ({full_tracking_rate:>5.1f}%)")
        print()
        
        # Tempo médio entre click e /start
        users_with_timing = BotUser.query.filter(
            BotUser.first_interaction >= since,
            BotUser.click_timestamp.isnot(None)
        ).all()
        
        if users_with_timing:
            time_diffs = []
            for user in users_with_timing:
                if user.click_timestamp and user.first_interaction:
                    diff = (user.first_interaction - user.click_timestamp).total_seconds()
                    if 0 <= diff <= 300:  # Ignorar diferenças negativas ou > 5min (dados inválidos)
                        time_diffs.append(diff)
            
            if time_diffs:
                avg_time = sum(time_diffs) / len(time_diffs)
                min_time = min(time_diffs)
                max_time = max(time_diffs)
                
                print("⏱️ TEMPO CLICK → /START")
                print("-" * 80)
                print(f"Amostras válidas:            {len(time_diffs):>6}")
                print(f"Tempo médio:                 {avg_time:>6.1f}s")
                print(f"Tempo mínimo:                {min_time:>6.1f}s")
                print(f"Tempo máximo:                {max_time:>6.1f}s")
                print()
        
        # Análise de dispositivos (parsing básico do User-Agent)
        users_with_ua_data = BotUser.query.filter(
            BotUser.first_interaction >= since,
            BotUser.user_agent.isnot(None)
        ).all()
        
        if users_with_ua_data:
            platforms = []
            browsers = []
            
            for user in users_with_ua_data:
                ua = user.user_agent.lower()
                
                # Detectar plataforma
                if 'android' in ua:
                    platforms.append('Android')
                elif 'iphone' in ua or 'ipad' in ua:
                    platforms.append('iOS')
                elif 'windows' in ua:
                    platforms.append('Windows')
                elif 'mac' in ua:
                    platforms.append('macOS')
                elif 'linux' in ua:
                    platforms.append('Linux')
                else:
                    platforms.append('Outro')
                
                # Detectar navegador
                if 'chrome' in ua and 'edg' not in ua:
                    browsers.append('Chrome')
                elif 'firefox' in ua:
                    browsers.append('Firefox')
                elif 'safari' in ua and 'chrome' not in ua:
                    browsers.append('Safari')
                elif 'edg' in ua:
                    browsers.append('Edge')
                elif 'instagram' in ua:
                    browsers.append('Instagram')
                elif 'fbav' in ua or 'fban' in ua:
                    browsers.append('Facebook')
                else:
                    browsers.append('Outro')
            
            platform_counts = Counter(platforms)
            browser_counts = Counter(browsers)
            
            print("📱 DISPOSITIVOS E NAVEGADORES")
            print("-" * 80)
            print("Plataformas:")
            for platform, count in platform_counts.most_common():
                percentage = (count / len(platforms) * 100)
                print(f"  {platform:<15} {count:>6}  ({percentage:>5.1f}%)")
            print()
            print("Navegadores:")
            for browser, count in browser_counts.most_common():
                percentage = (count / len(browsers) * 100)
                print(f"  {browser:<15} {count:>6}  ({percentage:>5.1f}%)")
            print()
        
        # Taxa de match Redis (estimativa)
        redis_match_rate = full_tracking_rate  # Se tem tracking completo, houve match
        print("🔗 TAXA DE MATCH REDIS ↔ BOTUSER")
        print("-" * 80)
        print(f"Taxa de sucesso:             {redis_match_rate:>5.1f}%")
        print(f"Falhas estimadas:            {100 - redis_match_rate:>5.1f}%")
        print()
        print("💡 Falhas podem ocorrer por:")
        print("   - TTL expirado (> 3 min entre click e /start)")
        print("   - Redis indisponível")
        print("   - fbclid não presente na URL")
        print("   - Acesso direto ao bot (sem passar pelo /go/)")
        print()
        
        # Top IPs (para detectar bots)
        top_ips = db.session.query(
            BotUser.ip_address,
            func.count(BotUser.id).label('count')
        ).filter(
            BotUser.first_interaction >= since,
            BotUser.ip_address.isnot(None)
        ).group_by(BotUser.ip_address)\
         .order_by(func.count(BotUser.id).desc())\
         .limit(10)\
         .all()
        
        if top_ips:
            print("🌐 TOP 10 IPs (últimas 24h)")
            print("-" * 80)
            for ip, count in top_ips:
                print(f"  {ip:<20} {count:>6} acessos")
            print()
        
        print("=" * 80)
        print("✅ ANÁLISE CONCLUÍDA")
        print("=" * 80)

if __name__ == '__main__':
    analyze_tracking_elite()

