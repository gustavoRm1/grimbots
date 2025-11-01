#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Executa reconciliador Paradise manualmente
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, reconcile_paradise_payments

with app.app_context():
    print("=" * 80)
    print("🔍 EXECUTANDO RECONCILIADOR PARADISE")
    print("=" * 80)
    reconcile_paradise_payments()
    print("=" * 80)
    print("✅ Reconciliador concluído")
    print("=" * 80)

