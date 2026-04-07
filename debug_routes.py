#!/usr/bin/env python3
"""
Script para listar todas as rotas registradas no Flask
"""

from internal_logic.core.extensions import create_app

app = create_app()

print("🗺️ MAPA DE ROTAS DO FLASK")
print("=" * 60)

for rule in app.url_map.iter_rules():
    print(f"Endpoint: {rule.endpoint:30} | Métodos: {list(rule.methods):15} | Rota: {rule.rule}")

print("\n" + "=" * 60)

# Buscar especificamente por remarketing e delivery
print("\n🔍 BUSCA ESPECÍFICA:")
print("-" * 40)

remarketing_routes = []
delivery_routes = []
telegram_routes = []

for rule in app.url_map.iter_rules():
    if 'remarketing' in rule.endpoint.lower() or 'remarketing' in rule.rule.lower():
        remarketing_routes.append(rule)
    elif 'delivery' in rule.endpoint.lower() or 'delivery' in rule.rule.lower():
        delivery_routes.append(rule)
    elif 'telegram' in rule.endpoint.lower() or 'telegram' in rule.rule.lower():
        telegram_routes.append(rule)

print("\n📋 ROTAS DE REMARKETING:")
for rule in remarketing_routes:
    print(f"  {rule.endpoint:30} | {rule.rule}")

print("\n📦 ROTAS DE DELIVERY:")
for rule in delivery_routes:
    print(f"  {rule.endpoint:30} | {rule.rule}")

print("\n📞 ROTAS DE TELEGRAM:")
for rule in telegram_routes:
    print(f"  {rule.endpoint:30} | {rule.rule}")

print("\n" + "=" * 60)
