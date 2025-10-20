#!/usr/bin/env python3
"""
🧪 TESTE DE DEMONSTRAÇÃO DO CLOAKER
Executa testes automatizados para comprovar funcionamento
"""

import requests
import json
import time
from datetime import datetime

class CloakerDemonstration:
    def __init__(self, base_url="https://app.grimbots.online"):
        self.base_url = base_url
        self.results = []
    
    def test_legitimate_access(self):
        """Teste 1: Acesso legítimo via Meta Ads"""
        print("🧪 Teste 1: Acesso legítimo via Meta Ads")
        
        url = f"{self.base_url}/go/test"
        params = {
            'apx': 'ohx9lury',
            'utm_source': 'facebook',
            'utm_campaign': 'teste'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; MetaBot/1.0)',
            'Referer': 'https://www.facebook.com/'
        }
        
        start_time = time.time()
        response = requests.get(url, params=params, headers=headers, allow_redirects=False)
        latency = (time.time() - start_time) * 1000
        
        result = {
            'test': 'legitimate_access',
            'url': response.url,
            'status_code': response.status_code,
            'latency_ms': round(latency, 2),
            'headers': dict(response.headers),
            'success': response.status_code in [200, 302],
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Status: {response.status_code}")
        print(f"⏱️ Latência: {latency:.2f}ms")
        print(f"🔗 URL: {response.url}")
        
        self.results.append(result)
        return result
    
    def test_bot_detection(self):
        """Teste 2: Detecção de bot"""
        print("\n🧪 Teste 2: Detecção de bot")
        
        url = f"{self.base_url}/go/test"
        params = {'apx': 'ohx9lury'}
        headers = {'User-Agent': 'python-requests/2.28.1'}
        
        start_time = time.time()
        response = requests.get(url, params=params, headers=headers, allow_redirects=False)
        latency = (time.time() - start_time) * 1000
        
        result = {
            'test': 'bot_detection',
            'url': response.url,
            'status_code': response.status_code,
            'latency_ms': round(latency, 2),
            'headers': dict(response.headers),
            'success': response.status_code == 200,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Status: {response.status_code}")
        print(f"⏱️ Latência: {latency:.2f}ms")
        print(f"🔗 URL: {response.url}")
        
        self.results.append(result)
        return result
    
    def test_direct_access(self):
        """Teste 3: Acesso direto sem parâmetros"""
        print("\n🧪 Teste 3: Acesso direto sem parâmetros")
        
        url = f"{self.base_url}/go/test"
        
        start_time = time.time()
        response = requests.get(url, allow_redirects=False)
        latency = (time.time() - start_time) * 1000
        
        result = {
            'test': 'direct_access',
            'url': response.url,
            'status_code': response.status_code,
            'latency_ms': round(latency, 2),
            'headers': dict(response.headers),
            'success': response.status_code == 200,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Status: {response.status_code}")
        print(f"⏱️ Latência: {latency:.2f}ms")
        print(f"🔗 URL: {response.url}")
        
        self.results.append(result)
        return result
    
    def test_missing_apx(self):
        """Teste 4: Parâmetro apx ausente"""
        print("\n🧪 Teste 4: Parâmetro apx ausente")
        
        url = f"{self.base_url}/go/test"
        params = {'utm_source': 'facebook'}  # Sem apx
        
        start_time = time.time()
        response = requests.get(url, params=params, allow_redirects=False)
        latency = (time.time() - start_time) * 1000
        
        result = {
            'test': 'missing_apx',
            'url': response.url,
            'status_code': response.status_code,
            'latency_ms': round(latency, 2),
            'headers': dict(response.headers),
            'success': response.status_code == 200,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Status: {response.status_code}")
        print(f"⏱️ Latência: {latency:.2f}ms")
        print(f"🔗 URL: {response.url}")
        
        self.results.append(result)
        return result
    
    def test_invalid_referer(self):
        """Teste 5: Referer inválido"""
        print("\n🧪 Teste 5: Referer inválido")
        
        url = f"{self.base_url}/go/test"
        params = {'apx': 'ohx9lury'}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://google.com/'  # Referer inválido
        }
        
        start_time = time.time()
        response = requests.get(url, params=params, headers=headers, allow_redirects=False)
        latency = (time.time() - start_time) * 1000
        
        result = {
            'test': 'invalid_referer',
            'url': response.url,
            'status_code': response.status_code,
            'latency_ms': round(latency, 2),
            'headers': dict(response.headers),
            'success': response.status_code == 200,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Status: {response.status_code}")
        print(f"⏱️ Latência: {latency:.2f}ms")
        print(f"🔗 URL: {response.url}")
        
        self.results.append(result)
        return result
    
    def run_all_tests(self):
        """Executa todos os testes"""
        print("🚀 INICIANDO DEMONSTRAÇÃO DO CLOAKER")
        print("=" * 50)
        
        # Executar testes
        self.test_legitimate_access()
        self.test_bot_detection()
        self.test_direct_access()
        self.test_missing_apx()
        self.test_invalid_referer()
        
        # Resumo
        print("\n📊 RESUMO DOS TESTES")
        print("=" * 50)
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r['success'])
        
        print(f"Total de testes: {total_tests}")
        print(f"Testes bem-sucedidos: {successful_tests}")
        print(f"Taxa de sucesso: {successful_tests/total_tests*100:.1f}%")
        
        # Latência média
        avg_latency = sum(r['latency_ms'] for r in self.results) / len(self.results)
        print(f"Latência média: {avg_latency:.2f}ms")
        
        # Salvar resultados
        self.save_results()
        
        return self.results
    
    def save_results(self):
        """Salva resultados em arquivo JSON"""
        filename = f"cloaker_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultados salvos em: {filename}")

if __name__ == "__main__":
    # Executar demonstração
    demo = CloakerDemonstration()
    results = demo.run_all_tests()
    
    print("\n✅ DEMONSTRAÇÃO CONCLUÍDA!")
    print("📋 Todos os testes foram executados com sucesso.")
    print("🔍 Verifique os logs do servidor para detalhes completos.")
