"""
Locust Load Testing - GRIMBOTS QI 500
Testa capacidade do sistema sob alta carga
"""

from locust import HttpUser, task, between, events
import json
import random
import time

class GrimbotsUser(HttpUser):
    """Usuário simulado do sistema GRIMBOTS"""
    
    wait_time = between(1, 3)  # Aguarda 1-3 segundos entre requisições
    
    def on_start(self):
        """Executado quando usuário inicia"""
        self.bot_id = random.randint(1, 30)  # Simula 30 bots diferentes
        self.chat_id = random.randint(100000, 999999)  # Chat ID aleatório
    
    @task(10)
    def health_check(self):
        """Health check (peso 10 - menos frequente)"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Health check failed: {response.status_code}")
            else:
                # Validar estrutura da resposta
                try:
                    data = response.json()
                    if data.get('status') not in ['healthy', 'degraded']:
                        response.failure(f"Invalid status: {data.get('status')}")
                except:
                    response.failure("Invalid JSON response")
    
    @task(50)
    def telegram_webhook_start(self):
        """Webhook Telegram /start (peso 50 - mais frequente)"""
        payload = {
            "update_id": int(time.time() * 1000) + random.randint(1, 9999),
            "message": {
                "message_id": random.randint(1000, 9999),
                "from": {
                    "id": self.chat_id,
                    "first_name": f"User{self.chat_id}",
                    "username": f"user{self.chat_id}",
                    "language_code": "pt-BR"
                },
                "chat": {
                    "id": self.chat_id,
                    "first_name": f"User{self.chat_id}",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "/start"
            }
        }
        
        with self.client.post(
            f"/webhook/telegram/{self.bot_id}",
            json=payload,
            catch_response=True,
            name="/webhook/telegram/[bot_id] /start"
        ) as response:
            if response.status_code not in [200, 201]:
                response.failure(f"Webhook /start failed: {response.status_code}")
    
    @task(30)
    def telegram_webhook_text(self):
        """Webhook Telegram texto normal (peso 30)"""
        messages = [
            "Oi",
            "Olá",
            "Quanto custa?",
            "Quero comprar",
            "Tenho interesse",
            "Como funciona?",
            "Mais informações",
            "Precisa de ajuda"
        ]
        
        payload = {
            "update_id": int(time.time() * 1000) + random.randint(1, 9999),
            "message": {
                "message_id": random.randint(1000, 9999),
                "from": {
                    "id": self.chat_id,
                    "first_name": f"User{self.chat_id}",
                    "language_code": "pt-BR"
                },
                "chat": {
                    "id": self.chat_id,
                    "type": "private"
                },
                "date": int(time.time()),
                "text": random.choice(messages)
            }
        }
        
        with self.client.post(
            f"/webhook/telegram/{self.bot_id}",
            json=payload,
            catch_response=True,
            name="/webhook/telegram/[bot_id] text"
        ) as response:
            if response.status_code not in [200, 201]:
                response.failure(f"Webhook text failed: {response.status_code}")
    
    @task(20)
    def telegram_webhook_callback(self):
        """Webhook Telegram callback (botões) (peso 20)"""
        payload = {
            "update_id": int(time.time() * 1000) + random.randint(1, 9999),
            "callback_query": {
                "id": str(random.randint(100000, 999999)),
                "from": {
                    "id": self.chat_id,
                    "first_name": f"User{self.chat_id}"
                },
                "message": {
                    "message_id": random.randint(1000, 9999),
                    "chat": {"id": self.chat_id}
                },
                "chat_instance": str(random.randint(1000000, 9999999)),
                "data": f"buy_{random.randint(0, 2)}"
            }
        }
        
        with self.client.post(
            f"/webhook/telegram/{self.bot_id}",
            json=payload,
            catch_response=True,
            name="/webhook/telegram/[bot_id] callback"
        ) as response:
            if response.status_code not in [200, 201]:
                response.failure(f"Webhook callback failed: {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Executado ao iniciar o teste"""
    print("="*70)
    print("  TESTE DE CARGA - GRIMBOTS QI 500")
    print("="*70)
    print(f"  Target: {environment.host}")
    print(f"  Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("="*70)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Executado ao finalizar o teste"""
    print("\n" + "="*70)
    print("  RESULTADOS DO TESTE")
    print("="*70)
    
    stats = environment.stats
    
    print(f"\n📊 Estatísticas Gerais:")
    print(f"  Total de requisições: {stats.total.num_requests}")
    print(f"  Total de falhas: {stats.total.num_failures}")
    print(f"  Taxa de falhas: {stats.total.fail_ratio:.2%}")
    print(f"  Requisições/seg: {stats.total.current_rps:.2f}")
    
    print(f"\n⏱️  Latência:")
    print(f"  Média: {stats.total.avg_response_time:.0f}ms")
    print(f"  Mediana (P50): {stats.total.median_response_time:.0f}ms")
    print(f"  P95: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"  P99: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"  Max: {stats.total.max_response_time:.0f}ms")
    print(f"  Min: {stats.total.min_response_time:.0f}ms")
    
    print(f"\n📈 Performance:")
    if stats.total.fail_ratio < 0.01:  # <1% falhas
        print(f"  ✅ PASSOU - Taxa de falhas aceitável: {stats.total.fail_ratio:.2%}")
    elif stats.total.fail_ratio < 0.05:  # <5% falhas
        print(f"  ⚠️  ATENÇÃO - Taxa de falhas elevada: {stats.total.fail_ratio:.2%}")
    else:
        print(f"  ❌ FALHOU - Taxa de falhas crítica: {stats.total.fail_ratio:.2%}")
    
    if stats.total.avg_response_time < 500:
        print(f"  ✅ PASSOU - Latência média aceitável: {stats.total.avg_response_time:.0f}ms")
    else:
        print(f"  ⚠️  ATENÇÃO - Latência média elevada: {stats.total.avg_response_time:.0f}ms")
    
    p95 = stats.total.get_response_time_percentile(0.95)
    if p95 < 1000:
        print(f"  ✅ PASSOU - P95 aceitável: {p95:.0f}ms")
    else:
        print(f"  ⚠️  ATENÇÃO - P95 elevado: {p95:.0f}ms")
    
    print("\n" + "="*70)
    
    # Definir exit code baseado nos resultados
    if stats.total.fail_ratio > 0.05:  # >5% falhas
        print("❌ TESTE FALHOU: Taxa de falhas muito alta")
        environment.process_exit_code = 1
    elif stats.total.avg_response_time > 1000:  # >1s média
        print("⚠️  TESTE COM PROBLEMAS: Latência muito alta")
        environment.process_exit_code = 1
    else:
        print("✅ TESTE PASSOU COM SUCESSO")
        environment.process_exit_code = 0


@events.quitting.add_listener
def _(environment, **kw):
    """Executado ao sair do teste"""
    if environment.stats.total.fail_ratio > 0.01:
        print(f"\n⚠️  Taxa de falhas: {environment.stats.total.fail_ratio:.2%}")


# Modo standalone (executar sem CLI)
if __name__ == "__main__":
    import os
    from locust import run_single_user
    
    # Configurar host
    os.environ['LOCUST_HOST'] = 'http://localhost:5000'
    
    # Executar 1 usuário para teste rápido
    print("Modo de teste rápido - 1 usuário")
    run_single_user(GrimbotsUser)

