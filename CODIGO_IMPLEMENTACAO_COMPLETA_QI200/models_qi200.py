"""
MODIFICAÇÕES NO models.py - ARQUITETO SÊNIOR QI 200

Adicionar os seguintes campos:

1. Payment:
   - webhook_token (VARCHAR(100), UNIQUE, INDEX)
   - gateway_id (INTEGER, FK → gateways.id, INDEX)
   - tracking_token (VARCHAR(100), INDEX)

2. Gateway:
   - webhook_secret (VARCHAR(100), UNIQUE, INDEX)
   - priority (INTEGER, DEFAULT 0)
   - weight (INTEGER, DEFAULT 1)

3. BotUser:
   - tracking_token (VARCHAR(100), UNIQUE, INDEX)
"""

# ============================================================================
# MODIFICAÇÃO 1: Payment Class
# ============================================================================
# Localização: models.py, linha ~820 (após gateway_transaction_hash)

"""
class Payment(db.Model):
    # ... campos existentes ...
    gateway_transaction_hash = db.Column(db.String(100))
    
    # ✅ NOVO - QI 200: Webhook token (único, garantido)
    webhook_token = db.Column(db.String(100), unique=True, nullable=True, index=True)
    
    # ✅ NOVO - QI 200: Gateway FK (integridade referencial)
    gateway_id = db.Column(db.Integer, db.ForeignKey('gateways.id'), nullable=True, index=True)
    gateway = db.relationship('Gateway', backref='payments')
    
    # ✅ NOVO - QI 200: Tracking token (unificado)
    tracking_token = db.Column(db.String(100), nullable=True, index=True)
    
    # ... resto dos campos ...
"""

# ============================================================================
# MODIFICAÇÃO 2: Gateway Class
# ============================================================================
# Localização: models.py, linha ~632 (após split_percentage)

"""
class Gateway(db.Model):
    # ... campos existentes ...
    split_percentage = db.Column(db.Float, default=2.0)
    
    # ✅ NOVO - QI 200: Webhook secret (multi-tenant)
    webhook_secret = db.Column(db.String(100), unique=True, nullable=True, index=True)
    
    # ✅ NOVO - QI 200: Priority e weight (multi-gateway)
    priority = db.Column(db.Integer, default=0)  # 1=preferencial, 0=normal
    weight = db.Column(db.Integer, default=1)  # Para weighted selection
    
    # ... resto dos campos ...
"""

# ============================================================================
# MODIFICAÇÃO 3: BotUser Class
# ============================================================================
# Localização: models.py, linha ~942 (após tracking_session_id)

"""
class BotUser(db.Model):
    # ... campos existentes ...
    tracking_session_id = db.Column(db.String(100), nullable=True)
    click_timestamp = db.Column(db.DateTime, nullable=True)
    
    # ✅ NOVO - QI 200: Tracking token (unificado)
    tracking_token = db.Column(db.String(100), unique=True, nullable=True, index=True)
    
    # ... resto dos campos ...
"""

