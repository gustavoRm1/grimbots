# ============================================================================
# LEGACY BOT CONFIG - EXTRAÇÃO DA LÓGICA DE CONFIGURAÇÃO DE BOTS
# Arquivo: _legacy_exports/legacy_bot_config.py
# Origem: app.py legado
# ============================================================================
# Este arquivo contém a "assinatura" exata da configuração de bots:
# - Rota de renderização da página (/bots/<int:bot_id>/config)
# - API de busca de config (GET /api/bots/<int:bot_id>/config)
# - API de atualização (PUT /api/bots/<int:bot_id>/config)
# - Modelo BotConfig e relacionamento com Bot
# NÃO MODIFICAR - Apenas para referência durante migração
# ============================================================================


# ============================================================================
# ALVO 1: ROTA RENDERIZADORA DA PÁGINA
# Origem: app.py - Linhas 5738-5743
# ============================================================================

# @app.route('/bots/<int:bot_id>/config')
# @login_required
# def bot_config_page(bot_id):
#     """Página de configuração do bot"""
#     bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
#     return render_template('bot_config.html', bot=bot)

"""
ANÁLISE:
- A rota apenas busca o bot e renderiza o template
- NÃO passa config diretamente - o frontend carrega via API AJAX
- O template bot_config.html faz requisição GET /api/bots/<bot_id>/config
- Autenticação: login_required + verificação user_id
"""


# ============================================================================
# ALVO 2: API DE BUSCA DE CONFIGURAÇÃO (GET)
# Origem: app.py - Linhas 5992-6036
# ============================================================================

# @app.route('/api/bots/<int:bot_id>/config', methods=['GET'])
# @login_required
# def get_bot_config(bot_id):
#     """Obtém configuração de um bot"""
#     try:
#         logger.info(f"🔍 Buscando config do bot {bot_id}...")
#         bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
#         logger.info(f"✅ Bot encontrado: {bot.name}")
#         
#         # ✅ LAZY LOADING: Se não tiver config, cria automaticamente
#         if not bot.config:
#             logger.warning(f"⚠️ Bot {bot_id} não tem config, criando nova...")
#             config = BotConfig(bot_id=bot.id)
#             db.session.add(config)
#             db.session.commit()
#             db.session.refresh(config)
#             logger.info(f"✅ Config nova criada para bot {bot_id}")
#         else:
#             logger.info(f"✅ Config existente encontrada (ID: {bot.config.id})")
#         
#         config_dict = bot.config.to_dict()
#         logger.info(f"📦 Config serializado com sucesso")
#         logger.info(f"   - welcome_message: {len(config_dict.get('welcome_message', ''))} chars")
#         logger.info(f"   - main_buttons: {len(config_dict.get('main_buttons', []))} botões")
#         logger.info(f"   - downsells: {len(config_dict.get('downsells', []))} downsells")
#         logger.info(f"   - upsells: {len(config_dict.get('upsells', []))} upsells")
#         
#         # ✅ METADADOS ADICIONAIS: Verificar Meta Pixel do pool
#         from models import PoolBot
#         pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
#         has_meta_pixel = False
#         pool_name = None
#         if pool_bot and pool_bot.pool:
#             pool = pool_bot.pool
#             has_meta_pixel = pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token
#             pool_name = pool.name
#         
#         config_dict['has_meta_pixel'] = has_meta_pixel
#         config_dict['pool_name'] = pool_name
#         
#         logger.info(f"   - Meta Pixel ativo: {'✅ Sim' if has_meta_pixel else '❌ Não'} (Pool: {pool_name or 'N/A'})")
#         
#         return jsonify(config_dict)
#     except Exception as e:
#         logger.error(f"❌ Erro ao buscar config do bot {bot_id}: {e}", exc_info=True)
#         return jsonify({'error': f'Erro ao buscar configuração: {str(e)}'}), 500

"""
ANÁLISE - LAZY LOADING (CRÍTICO):
- Se bot.config não existe (None), o sistema CRIA uma configuração automaticamente
- Isso evita erro 500 quando bot existe mas não tem configuração
- BotConfig(bot_id=bot.id) cria config vazia/padrão
- Após criar, faz commit e refresh para garantir ID

METADADOS ADICIONAIS:
- A API adiciona campos extras ao dict: has_meta_pixel e pool_name
- Isso é usado pelo frontend para mostrar status do pixel
"""


# ============================================================================
# ALVO 3: API DE ATUALIZAÇÃO (PUT)
# Origem: app.py - Linhas 6086-~6400
# ============================================================================

# @app.route('/api/bots/<int:bot_id>/config', methods=['PUT'])
# @login_required
# @csrf.exempt
# def update_bot_config(bot_id):
#     """Atualiza configuração de um bot"""
#     logger.info(f"🔄 Iniciando atualização de config para bot {bot_id}")
#     
#     bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
#     raw_data = request.get_json() or {}
#     
#     # ✅ CORREÇÃO CRÍTICA: NÃO sanitizar welcome_message - preservar emojis
#     data = raw_data.copy() if isinstance(raw_data, dict) else {}
#     
#     # Sanitizar apenas outros campos (não welcome_message)
#     if 'welcome_message' in raw_data:
#         data['welcome_message'] = raw_data['welcome_message']  # Preserva emojis!
#     
#     logger.info(f"📊 Dados recebidos: {list(data.keys())}")
#     
#     # ✅ LAZY LOADING: Cria config se não existir
#     if not bot.config:
#         logger.info(f"📝 Criando nova configuração para bot {bot_id}")
#         config = BotConfig(bot_id=bot.id)
#         db.session.add(config)
#     else:
#         logger.info(f"📝 Atualizando configuração existente para bot {bot_id}")
#         config = bot.config
#     
#     try:
#         # === CAMPOS ATUALIZÁVEIS ===
#         
#         # 1. Mensagem de boas-vindas
#         if 'welcome_message' in data:
#             config.welcome_message = data['welcome_message']
#             config.welcome_media_url = data.get('welcome_media_url') or config.welcome_media_url
#         
#         # 2. Botões principais (array JSON)
#         if 'main_buttons' in data:
#             config.set_main_buttons(data['main_buttons'])
#         
#         # 3. Botões de redirecionamento
#         if 'redirect_buttons' in data:
#             config.set_redirect_buttons(data['redirect_buttons'])
#         
#         # 4. Order Bump
#         if 'order_bump_enabled' in data:
#             config.order_bump_enabled = data['order_bump_enabled']
#         if 'order_bump_message' in data:
#             config.order_bump_message = data['order_bump_message']
#         if 'order_bump_media_url' in data:
#             config.order_bump_media_url = data['order_bump_media_url']
#         if 'order_bump_price' in data:
#             config.order_bump_price = float(data['order_bump_price'])
#         
#         # 5. Downsells (array JSON com validação)
#         if 'downsells_enabled' in data:
#             config.downsells_enabled = data['downsells_enabled']
#         if 'downsells' in data:
#             downsells = data['downsells']
#             # Validação Poka-Yoke
#             for i, downsell in enumerate(downsells):
#                 message = downsell.get('message', '')
#                 if message and not str(message).strip():
#                     return jsonify({'error': f'A mensagem do Downsell #{i+1} não pode estar vazia.'}), 400
#                 # ... mais validações
#             config.set_downsells(downsells)
#         
#         # 6. Upsells
#         if 'upsells_enabled' in data:
#             config.upsells_enabled = data['upsells_enabled']
#         if 'upsells' in data:
#             config.set_upsells(data['upsells'])
#         
#         # 7. Link de acesso (para delivery)
#         if 'access_link' in data:
#             config.access_link = data['access_link']
#         
#         # 8. Mensagens personalizadas
#         if 'success_message' in data:
#             config.success_message = data['success_message']
#         if 'pending_message' in data:
#             config.pending_message = data['pending_message']
#         
#         # 9. Fluxo Visual (Flow Builder)
#         if 'flow_enabled' in data:
#             config.flow_enabled = bool(data['flow_enabled'])
#         if 'flow_steps' in data:
#             config.set_flow_steps(data['flow_steps'])  # Validação de steps
#         if 'flow_start_step_id' in data:
#             config.flow_start_step_id = data['flow_start_step_id']
#         
#         # === COMMIT E RESPOSTA ===
#         db.session.commit()
#         logger.info(f"✅ Configuração do bot {bot_id} salva com sucesso")
#         
#         return jsonify({
#             'success': True,
#             'message': 'Configuração salva com sucesso',
#             'config': config.to_dict()
#         })
#         
#     except Exception as e:
#         db.session.rollback()
#         logger.error(f"❌ Erro ao salvar config: {e}", exc_info=True)
#         return jsonify({'error': str(e)}), 500


# ============================================================================
# ALVO 4: ESTRUTURA DO MODELO BotConfig
# Origem: app.py - Definição da classe (extrair de múltiplas partes)
# ============================================================================

"""
RELACIONAMENTO:
- Bot (1) ---- (1) BotConfig (relacionamento one-to-one via bot.config)
- Bot.config é uma property que retorna o BotConfig associado
- BotConfig.bot_id é FK para bots.id

LAZY LOADING / CRIAÇÃO AUTOMÁTICA:
- Quando bot.config é acessado e retorna None, o código cria automaticamente
- Isso evita AttributeError em bot.config.welcome_message quando não existe config
"""

# Colunas da tabela BotConfig (extrapolado do uso em to_dict e rotas):
BOTCONFIG_SCHEMA = {
    # Identificação
    'id': 'Integer PK',
    'bot_id': 'Integer FK -> bots.id',
    
    # Mensagem de boas-vindas
    'welcome_message': 'Text (mensagem inicial do bot)',
    'welcome_media_url': 'String (URL de imagem/video opcional)',
    
    # Botões (armazenados como JSON)
    'main_buttons': 'JSON (array de botões principais)',
    'redirect_buttons': 'JSON (array de botões de redirecionamento)',
    
    # Order Bump (venda adicional)
    'order_bump_enabled': 'Boolean',
    'order_bump_message': 'Text',
    'order_bump_media_url': 'String',
    'order_bump_price': 'Float',
    
    # Downsells (ofertas de recuperação)
    'downsells_enabled': 'Boolean',
    'downsells': 'JSON (array de downsells)',
    # Cada downsell: {id, message, description, price, gateway_type, ...}
    
    # Upsells (ofertas adicionais pós-compra)
    'upsells_enabled': 'Boolean',
    'upsells': 'JSON (array de upsells)',
    
    # Link de acesso (para página de delivery)
    'access_link': 'String (URL do produto/conteúdo)',
    
    # Mensagens de status
    'success_message': 'Text (mensagem após pagamento confirmado)',
    'pending_message': 'Text (mensagem enquanto aguarda pagamento)',
    
    # Fluxo Visual (Flow Builder)
    'flow_enabled': 'Boolean (se usa flow builder ou estrutura linear)',
    'flow_steps': 'JSON (array de steps do fluxo)',
    # Cada step: {id, type, message, media_url, connections: {next, pending, retry}}
    'flow_start_step_id': 'String (ID do step inicial)',
    
    # Timestamps
    'created_at': 'DateTime',
    'updated_at': 'DateTime',
}


# ============================================================================
# ALVO 5: MÉTODO to_dict() DO BotConfig
# ============================================================================

# def to_dict(self):
#     """Serializa configuração para JSON"""
#     return {
#         'id': self.id,
#         'bot_id': self.bot_id,
#         
#         # Mensagem de boas-vindas
#         'welcome_message': self.welcome_message or '',
#         'welcome_media_url': self.welcome_media_url or '',
#         
#         # Botões
#         'main_buttons': self.get_main_buttons() or [],
#         'redirect_buttons': self.get_redirect_buttons() or [],
#         
#         # Order Bump
#         'order_bump_enabled': self.order_bump_enabled or False,
#         'order_bump_message': self.order_bump_message or '',
#         'order_bump_media_url': self.order_bump_media_url or '',
#         'order_bump_price': float(self.order_bump_price) if self.order_bump_price else 0.0,
#         
#         # Downsells
#         'downsells_enabled': self.downsells_enabled or False,
#         'downsells': self.get_downsells() or [],
#         
#         # Upsells
#         'upsells_enabled': self.upsells_enabled or False,
#         'upsells': self.get_upsells() or [],
#         
#         # Link de acesso
#         'access_link': self.access_link or '',
#         
#         # Mensagens
#         'success_message': self.success_message or '',
#         'pending_message': self.pending_message or '',
#         
#         # Fluxo
#         'flow_enabled': self.flow_enabled or False,
#         'flow_steps': self.get_flow_steps() or [],
#         'flow_start_step_id': self.flow_start_step_id or '',
#         
#         # Timestamps
#         'created_at': self.created_at.isoformat() if self.created_at else None,
#         'updated_at': self.updated_at.isoformat() if self.updated_at else None,
#     }


# ============================================================================
# RESUMO DO CONTRATO FRONTEND-BACKEND
# ============================================================================

"""
CONTRATO DA API GET /api/bots/<bot_id>/config:

Request:
  - Headers: Cookie de autenticação (session)
  - URL: /api/bots/<int:bot_id>/config

Response (200 OK):
  {
    "id": 123,
    "bot_id": 456,
    "welcome_message": "Olá! Bem-vindo...",
    "welcome_media_url": "https://...",
    "main_buttons": [{"text": "Comprar", "action": "payment"}],
    "redirect_buttons": [],
    "order_bump_enabled": false,
    "order_bump_message": "",
    "order_bump_media_url": "",
    "order_bump_price": 0.0,
    "downsells_enabled": false,
    "downsells": [],
    "upsells_enabled": false,
    "upsells": [],
    "access_link": "https://t.me/...",
    "success_message": "Pagamento confirmado!",
    "pending_message": "Aguardando pagamento...",
    "flow_enabled": false,
    "flow_steps": [],
    "flow_start_step_id": "",
    "created_at": "2024-01-15T10:00:00",
    "updated_at": "2024-01-15T10:00:00",
    "has_meta_pixel": true,        // METADADO ADICIONAL
    "pool_name": "Meu Pool"        // METADADO ADICIONAL
  }

CONTRATO DA API PUT /api/bots/<bot_id>/config:

Request:
  - Headers: Cookie + Content-Type: application/json
  - Body: Objeto JSON com campos a atualizar (todos opcionais)
  - Exemplo: {"welcome_message": "Novo texto", "access_link": "https://..."}

Response (200 OK):
  {
    "success": true,
    "message": "Configuração salva com sucesso",
    "config": { ... objeto completo atualizado ... }
  }

Response (400 Bad Request):
  {
    "error": "Mensagem de erro específica (ex: 'A mensagem do Downsell #1 não pode estar vazia')"
  }

CONTRATO DA ROTA DE PÁGINA /bots/<bot_id>/config:

Response (200 OK):
  - HTML renderizado de bot_config.html
  - Variável disponível no template: {{ bot }} (objeto Bot)
  - Frontend carrega config via AJAX para /api/bots/<bot_id>/config


LAZY LOADING - COMPORTAMENTO CRÍTICO:
=====================================

1. Quando bot é criado sem config:
   - Bot.config retorna None
   - GET /api/bots/<id>/config detecta isso e CRIA BotConfig automaticamente
   - Usuário nunca vê erro - config aparece "vazia" mas funcional

2. Quando PUT é chamado sem config existente:
   - Mesmo comportamento: cria config antes de atualizar
   - Evita erro 500 tentando atualizar objeto inexistente

3. Campos JSON (main_buttons, downsells, upsells, flow_steps):
   - São armazenados como JSON string no banco
   - Métodos set_* serializam antes de salvar
   - Métodos get_* deserializam ao ler (retornam arrays/dicts Python)
   - to_dict() já retorna estruturas deserializadas para o frontend
"""


# ============================================================================
# MÉTODOS AUXILIARES DO BotConfig (JSON Serialization)
# ============================================================================

"""
Padrão comum para campos JSON no BotConfig:

class BotConfig(db.Model):
    ...
    
    # Coluna no banco (string JSON)
    _main_buttons = db.Column('main_buttons', db.Text)
    
    # Getter deserializado
    def get_main_buttons(self):
        if not self._main_buttons:
            return []
        try:
            import json
            return json.loads(self._main_buttons)
        except:
            return []
    
    # Setter serializado
    def set_main_buttons(self, buttons):
        import json
        if buttons is None:
            self._main_buttons = None
        else:
            self._main_buttons = json.dumps(buttons)
        
    # Property para conveniência
    @property
    def main_buttons(self):
        return self.get_main_buttons()
    
    @main_buttons.setter
    def main_buttons(self, value):
        self.set_main_buttons(value)

# to_dict() usa o getter:
# 'main_buttons': self.get_main_buttons() or []
"""


# ============================================================================
# CHECKLIST PARA REIMPLEMENTAÇÃO
# ============================================================================

"""
✅ CRÍTICO - LAZY LOADING:
   [ ] Se bot.config é None, criar BotConfig automaticamente
   [ ] Sempre fazer db.session.commit() após criar
   [ ] Sempre fazer db.session.refresh(config) para obter ID

✅ CRÍTICO - PRESERVAÇÃO DE EMOJIS:
   [ ] NÃO sanitizar welcome_message (preserva emojis Unicode)
   [ ] Sanitizar apenas campos que não precisam de emojis

✅ CRÍTICO - JSON SERIALIZATION:
   [ ] Usar métodos set_* para salvar arrays/objects
   [ ] Usar métodos get_* para ler (nunca acessar _coluna diretamente)
   [ ] to_dict() deve retornar estruturas deserializadas

✅ CRÍTICO - VALIDAÇÃO POAK-YOKE:
   [ ] Validar downsells antes de salvar (mensagem não vazia, preço válido)
   [ ] Validar upsells
   [ ] Retornar erro 400 com mensagem específica

✅ METADADOS ADICIONAIS:
   [ ] Adicionar has_meta_pixel ao response
   [ ] Adicionar pool_name ao response
   [ ] Verificar PoolBot associado

✅ ROTAS NECESSÁRIAS:
   [ ] GET /bots/<bot_id>/config (render_template)
   [ ] GET /api/bots/<bot_id>/config (JSON)
   [ ] PUT /api/bots/<bot_id>/config (JSON + CSRF exempt)
"""
