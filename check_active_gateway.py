#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica qual gateway está ativo e verificado
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Gateway, Bot

with app.app_context():
    print("=" * 80)
    print("📊 GATEWAYS NO SISTEMA:")
    print("=" * 80)
    
    # Buscar todos os gateways
    gateways = Gateway.query.all()
    
    for gw in gateways:
        print(f"\nGateway ID: {gw.id} ({gw.gateway_type})")
        print(f"  User ID: {gw.user_id}")
        print(f"  Ativo: {gw.is_active}")
        print(f"  Verificado: {gw.is_verified}")
        print(f"  Product Hash: {gw.product_hash or 'N/A'}")
        print(f"  Store ID: {gw.store_id or 'N/A'}")
    
    # Buscar bots recentes
    print("\n" + "=" * 80)
    print("📊 BOTS E SEUS GATEWAYS:")
    print("=" * 80)
    
    bots = Bot.query.order_by(Bot.id.desc()).limit(10).all()
    
    for bot in bots:
        print(f"\nBot ID: {bot.id} - {bot.name} (User: {bot.user_id})")
        # Buscar gateway deste bot
        bot_gateway = Gateway.query.filter_by(user_id=bot.user_id).order_by(
            Gateway.is_active.desc(), Gateway.is_verified.desc()
        ).first()
        
        if bot_gateway:
            print(f"  Gateway: {bot_gateway.gateway_type}")
            print(f"  Ativo: {bot_gateway.is_active}")
            print(f"  Verificado: {bot_gateway.is_verified}")
        else:
            print(f"  ❌ Nenhum gateway configurado para este bot")
    
    print("\n" + "=" * 80)

