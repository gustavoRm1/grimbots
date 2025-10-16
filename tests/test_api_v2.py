"""
Teste de API - Gamificação V2.0
Valida todos os endpoints REST
"""

from app import app
from models import User
import json

def test_all_endpoints():
    """Testa todos os endpoints da API de gamificação"""
    
    with app.test_client() as client:
        
        # Login
        login_response = client.post('/api/login', json={
            'email': 'admin@botmanager.com',
            'password': 'admin123'
        })
        
        print("=" * 80)
        print("TESTANDO API ENDPOINTS - GAMIFICACAO V2.0")
        print("=" * 80)
        
        # Teste 1: GET /api/v2/gamification/profile
        print("\nTESTE 1: GET /api/v2/gamification/profile")
        response = client.get('/api/v2/gamification/profile')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Pontos: {data['profile']['ranking']['points']}")
            print(f"  ✅ Liga: {data['profile']['ranking']['league']['name'] if data['profile']['ranking']['league'] else 'Nenhuma'}")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        # Teste 2: GET /api/v2/gamification/achievements
        print("\nTESTE 2: GET /api/v2/gamification/achievements")
        response = client.get('/api/v2/gamification/achievements')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Total de conquistas: {data['total']}")
            print(f"  ✅ Primeira conquista: {data['achievements'][0]['name'] if data['achievements'] else 'Nenhuma'}")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        # Teste 3: GET /api/v2/gamification/leaderboard
        print("\nTESTE 3: GET /api/v2/gamification/leaderboard")
        response = client.get('/api/v2/gamification/leaderboard?limit=10')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Usuários no leaderboard: {data['total']}")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        # Teste 4: GET /api/v2/gamification/leagues
        print("\nTESTE 4: GET /api/v2/gamification/leagues")
        response = client.get('/api/v2/gamification/leagues')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Total de ligas: {len(data['leagues'])}")
            for league in data['leagues'][:3]:
                print(f"    - {league['name']}: {league['user_count']} usuários")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        # Teste 5: GET /api/v2/gamification/seasons
        print("\nTESTE 5: GET /api/v2/gamification/seasons")
        response = client.get('/api/v2/gamification/seasons')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Total de seasons: {len(data['seasons'])}")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        # Teste 6: GET /api/v2/gamification/seasons/current
        print("\nTESTE 6: GET /api/v2/gamification/seasons/current")
        response = client.get('/api/v2/gamification/seasons/current')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            if data['season']:
                print(f"  ✅ Season ativa: {data['season']['name']}")
                print(f"  ✅ Dias restantes: {data['season']['days_left']}")
            else:
                print(f"  ℹ️ Nenhuma season ativa")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        # Teste 7: GET /api/v2/gamification/stats
        print("\nTESTE 7: GET /api/v2/gamification/stats")
        response = client.get('/api/v2/gamification/stats')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Vendas: {data['stats']['sales']['total']}")
            print(f"  ✅ Receita: R$ {data['stats']['sales']['revenue']:.2f}")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        # Teste 8: GET /api/v2/gamification/categories
        print("\nTESTE 8: GET /api/v2/gamification/categories")
        response = client.get('/api/v2/gamification/categories')
        data = json.loads(response.data)
        
        if response.status_code == 200 and data.get('success'):
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Categorias: {[c['name'] for c in data['categories']]}")
        else:
            print(f"  ❌ FALHOU: {response.status_code}")
        
        print("\n" + "=" * 80)
        print("TODOS OS TESTES DE API CONCLUIDOS")
        print("=" * 80)


if __name__ == '__main__':
    test_all_endpoints()

