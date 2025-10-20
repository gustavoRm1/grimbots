#!/usr/bin/env python3
"""
🔥 LOCUST LOAD TEST - CLOAKER PERFORMANCE
Testa capacidade do sistema sob carga

Rodar:
  locust -f locustfile.py --host=https://app.grimbots.online

Configurações sugeridas:
  - Users: 1000
  - Spawn rate: 100/s
  - Duration: 5m

Métricas esperadas:
  - P95 < 100ms (tráfego normal)
  - P95 < 500ms (spike de 1000 req/s)
  - Taxa de erro < 1%
"""

from locust import HttpUser, task, between, events
import time
import json
from datetime import datetime

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================
PARAM_NAME = "grim"
CORRECT_VALUE = "escalafull"  # Valor real do cloaker
WRONG_VALUE = "wrongvalue"
TEST_SLUG = "red1"  # Pool real com cloaker ativo

# ============================================================================
# USER CLASSES
# ============================================================================

class LegitUser(HttpUser):
    """
    Usuário legítimo vindo do Meta Ads
    80% do tráfego
    """
    weight = 80
    wait_time = between(0.1, 0.5)
    
    @task(10)
    def access_with_correct_param(self):
        """Acesso com parâmetro correto"""
        with self.client.get(
            f"/go/{TEST_SLUG}",
            params={PARAM_NAME: CORRECT_VALUE},
            catch_response=True,
            name="/go/[slug]?param=correct"
        ) as response:
            if response.status_code in [200, 302]:
                response.success()
            else:
                response.failure(f"Expected 200/302, got {response.status_code}")


class BlockedUser(HttpUser):
    """
    Usuário sem parâmetro (deve ser bloqueado)
    15% do tráfego
    """
    weight = 15
    wait_time = between(0.5, 2.0)
    
    @task
    def access_without_param(self):
        """Acesso sem parâmetro"""
        with self.client.get(
            f"/go/{TEST_SLUG}",
            catch_response=True,
            name="/go/[slug] (no param)"
        ) as response:
            if response.status_code == 403:
                response.success()
            else:
                response.failure(f"Expected 403, got {response.status_code}")


class MaliciousUser(HttpUser):
    """
    Usuário com parâmetro incorreto
    5% do tráfego
    """
    weight = 5
    wait_time = between(1.0, 3.0)
    
    @task
    def access_with_wrong_param(self):
        """Acesso com parâmetro incorreto"""
        with self.client.get(
            f"/go/{TEST_SLUG}",
            params={PARAM_NAME: WRONG_VALUE},
            catch_response=True,
            name="/go/[slug]?param=wrong"
        ) as response:
            if response.status_code == 403:
                response.success()
            else:
                response.failure(f"Expected 403, got {response.status_code}")


# ============================================================================
# EVENTOS E MÉTRICAS
# ============================================================================

# Armazenar métricas customizadas
custom_metrics = {
    'start_time': None,
    'total_requests': 0,
    'blocked_requests': 0,
    'allowed_requests': 0,
    'latencies': []
}

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Executado ao iniciar o teste"""
    custom_metrics['start_time'] = time.time()
    print("\n" + "=" * 60)
    print("🔥 CLOAKER LOAD TEST - STARTED")
    print("=" * 60)
    print(f"Target: {environment.host}")
    print(f"Start Time: {datetime.now().isoformat()}")
    print("=" * 60 + "\n")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, 
               response, context, exception, **kwargs):
    """Executado após cada request"""
    custom_metrics['total_requests'] += 1
    custom_metrics['latencies'].append(response_time)
    
    if response and response.status_code == 403:
        custom_metrics['blocked_requests'] += 1
    elif response and response.status_code in [200, 302]:
        custom_metrics['allowed_requests'] += 1

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Executado ao finalizar o teste"""
    duration = time.time() - custom_metrics['start_time']
    
    print("\n" + "=" * 60)
    print("📊 CLOAKER LOAD TEST - FINAL REPORT")
    print("=" * 60)
    print(f"Duration: {duration:.2f}s")
    print(f"Total Requests: {custom_metrics['total_requests']}")
    print(f"Allowed: {custom_metrics['allowed_requests']} ({custom_metrics['allowed_requests']/custom_metrics['total_requests']*100:.1f}%)")
    print(f"Blocked: {custom_metrics['blocked_requests']} ({custom_metrics['blocked_requests']/custom_metrics['total_requests']*100:.1f}%)")
    print(f"RPS: {custom_metrics['total_requests']/duration:.2f}")
    
    # Calcular percentis de latência
    if custom_metrics['latencies']:
        latencies = sorted(custom_metrics['latencies'])
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        
        print("\n" + "-" * 60)
        print("⏱️  LATENCY METRICS")
        print("-" * 60)
        print(f"P50: {p50:.0f}ms")
        print(f"P95: {p95:.0f}ms")
        print(f"P99: {p99:.0f}ms")
        print(f"Min: {min(latencies):.0f}ms")
        print(f"Max: {max(latencies):.0f}ms")
        print(f"Avg: {sum(latencies)/len(latencies):.0f}ms")
        
        # Validar SLA
        print("\n" + "-" * 60)
        print("✅ SLA VALIDATION")
        print("-" * 60)
        
        if p95 < 100:
            print(f"✅ PASS: P95 latency {p95:.0f}ms < 100ms (normal traffic)")
        else:
            print(f"⚠️  WARNING: P95 latency {p95:.0f}ms >= 100ms")
        
        if p95 < 500:
            print(f"✅ PASS: P95 latency {p95:.0f}ms < 500ms (spike traffic)")
        else:
            print(f"❌ FAIL: P95 latency {p95:.0f}ms >= 500ms")
    
    # Salvar relatório em JSON
    report = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': duration,
        'total_requests': custom_metrics['total_requests'],
        'allowed_requests': custom_metrics['allowed_requests'],
        'blocked_requests': custom_metrics['blocked_requests'],
        'rps': custom_metrics['total_requests']/duration,
        'latency': {
            'p50': p50 if custom_metrics['latencies'] else 0,
            'p95': p95 if custom_metrics['latencies'] else 0,
            'p99': p99 if custom_metrics['latencies'] else 0,
            'min': min(latencies) if custom_metrics['latencies'] else 0,
            'max': max(latencies) if custom_metrics['latencies'] else 0,
            'avg': sum(latencies)/len(latencies) if custom_metrics['latencies'] else 0
        }
    }
    
    report_file = f"load_test_report_{int(time.time())}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Report saved to: {report_file}")
    print("=" * 60 + "\n")

# ============================================================================
# EXECUÇÃO DIRETA
# ============================================================================

if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py --host=https://app.grimbots.online")

