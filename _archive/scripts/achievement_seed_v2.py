"""
Seed de Conquistas V2 - 35 conquistas iniciais
Baseado em GAMIFICATION_V2_ACHIEVEMENTS_SEED.md
"""


def get_all_achievements():
    """Retorna lista de todas as conquistas para seed"""
    
    achievements = []
    
    # ============================================================================
    # CATEGORIA: VENDAS (SALES)
    # ============================================================================
    
    # Tier 1: Bronze
    achievements.extend([
        {
            'slug': 'first_sale_bronze',
            'name': 'Primeira Venda',
            'description': 'Realize sua primeira venda na plataforma',
            'icon': 'fa-handshake',
            'category': 'sales',
            'tier': 1,
            'rarity': 'common',
            'estimated_completion_rate': 0.85,
            'is_secret': False,
            'is_seasonal': False,
            'requirements': {'AND': [{'type': 'sales', 'operator': '>=', 'value': 1}]},
            'points': 100,
            'reward_type': 'xp',
            'reward_value': {'xp': 100}
        },
        {
            'slug': 'sales_10_bronze',
            'name': 'Vendedor Iniciante',
            'description': 'Realize 10 vendas',
            'icon': 'fa-chart-line',
            'category': 'sales',
            'tier': 1,
            'rarity': 'common',
            'estimated_completion_rate': 0.60,
            'requirements': {'AND': [{'type': 'sales', 'operator': '>=', 'value': 10}]},
            'points': 500,
            'reward_type': 'xp',
            'reward_value': {'xp': 500}
        },
        {
            'slug': 'revenue_1k_bronze',
            'name': 'Primeiro Milhar',
            'description': 'Alcance R$ 1.000 em receita total',
            'icon': 'fa-dollar-sign',
            'category': 'sales',
            'tier': 1,
            'rarity': 'common',
            'estimated_completion_rate': 0.50,
            'requirements': {'AND': [{'type': 'revenue', 'operator': '>=', 'value': 1000}]},
            'points': 1000,
            'reward_type': 'currency',
            'reward_value': {'currency': 'gems', 'amount': 10}
        }
    ])
    
    # Tier 2: Prata
    achievements.extend([
        {
            'slug': 'sales_50_silver',
            'name': 'Vendedor Experiente',
            'description': 'Realize 50 vendas',
            'icon': 'fa-medal',
            'category': 'sales',
            'tier': 2,
            'rarity': 'uncommon',
            'parent_id': None,  # Will be set after seed
            'estimated_completion_rate': 0.30,
            'requirements': {'AND': [{'type': 'sales', 'operator': '>=', 'value': 50}]},
            'points': 2500,
            'reward_type': 'commission_discount',
            'reward_value': {'discount': 0.25, 'duration_days': 7}
        },
        {
            'slug': 'revenue_10k_silver',
            'name': 'Cinco Zeros',
            'description': 'Alcance R$ 10.000 em receita total',
            'icon': 'fa-coins',
            'category': 'sales',
            'tier': 2,
            'rarity': 'uncommon',
            'estimated_completion_rate': 0.20,
            'requirements': {'AND': [{'type': 'revenue', 'operator': '>=', 'value': 10000}]},
            'points': 5000,
            'reward_type': 'title',
            'reward_value': {'title': 'Empreendedor'}
        },
        {
            'slug': 'avg_ticket_50_silver',
            'name': 'Vendedor Premium',
            'description': 'Mantenha ticket médio acima de R$ 50',
            'icon': 'fa-gem',
            'category': 'sales',
            'tier': 2,
            'rarity': 'rare',
            'estimated_completion_rate': 0.25,
            'requirements': {
                'AND': [
                    {'type': 'avg_ticket', 'operator': '>=', 'value': 50},
                    {'type': 'sales', 'operator': '>=', 'value': 20}
                ]
            },
            'points': 3000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 6}
        }
    ])
    
    # Tier 3: Ouro
    achievements.extend([
        {
            'slug': 'sales_100_gold',
            'name': 'Centurião',
            'description': 'Realize 100 vendas',
            'icon': 'fa-trophy',
            'category': 'sales',
            'tier': 3,
            'rarity': 'rare',
            'estimated_completion_rate': 0.15,
            'requirements': {'AND': [{'type': 'sales', 'operator': '>=', 'value': 100}]},
            'points': 10000,
            'reward_type': 'commission_discount',
            'reward_value': {'discount': 0.50, 'duration_days': 30}
        },
        {
            'slug': 'revenue_50k_gold',
            'name': 'Magnata Digital',
            'description': 'Alcance R$ 50.000 em receita total',
            'icon': 'fa-crown',
            'category': 'sales',
            'tier': 3,
            'rarity': 'epic',
            'estimated_completion_rate': 0.08,
            'requirements': {'AND': [{'type': 'revenue', 'operator': '>=', 'value': 50000}]},
            'points': 25000,
            'reward_type': 'title',
            'reward_value': {'title': 'Magnata'}
        },
        {
            'slug': 'conversion_10_gold',
            'name': 'Mestre da Conversão',
            'description': 'Alcance 10% de taxa de conversão com no mínimo 100 leads',
            'icon': 'fa-bullseye',
            'category': 'sales',
            'tier': 3,
            'rarity': 'epic',
            'estimated_completion_rate': 0.12,
            'requirements': {
                'AND': [
                    {'type': 'conversion_rate', 'operator': '>=', 'value': 10},
                    {'type': 'bot_users', 'operator': '>=', 'value': 100}
                ]
            },
            'points': 15000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 9}
        }
    ])
    
    # Tier 4: Platina
    achievements.extend([
        {
            'slug': 'sales_250_gold',
            'name': 'Vendedor Veterano',
            'description': 'Realize 250 vendas',
            'icon': 'fa-user-tie',
            'category': 'sales',
            'tier': 3,
            'rarity': 'epic',
            'estimated_completion_rate': 0.10,
            'requirements': {'AND': [{'type': 'sales', 'operator': '>=', 'value': 250}]},
            'points': 20000,
            'reward_type': 'commission_discount',
            'reward_value': {'discount': 0.75, 'duration_days': 60}
        },
        {
            'slug': 'sales_500_platinum',
            'name': 'Vendedor de Elite',
            'description': 'Realize 500 vendas',
            'icon': 'fa-star',
            'category': 'sales',
            'tier': 4,
            'rarity': 'legendary',
            'estimated_completion_rate': 0.05,
            'requirements': {'AND': [{'type': 'sales', 'operator': '>=', 'value': 500}]},
            'points': 50000,
            'reward_type': 'commission_discount',
            'reward_value': {'discount': 1.0, 'duration_days': 90}
        },
        {
            'slug': 'revenue_100k_platinum',
            'name': 'Seis Dígitos',
            'description': 'Alcance R$ 100.000 em receita total',
            'icon': 'fa-rocket',
            'category': 'sales',
            'tier': 4,
            'rarity': 'legendary',
            'estimated_completion_rate': 0.03,
            'requirements': {'AND': [{'type': 'revenue', 'operator': '>=', 'value': 100000}]},
            'points': 100000,
            'reward_type': 'title',
            'reward_value': {'title': 'Lenda das Vendas'}
        },
        {
            'slug': 'revenue_500k_platinum',
            'name': 'Meio Milhão',
            'description': 'Alcance R$ 500.000 em receita total',
            'icon': 'fa-gem',
            'category': 'sales',
            'tier': 5,
            'rarity': 'mythic',
            'estimated_completion_rate': 0.01,
            'requirements': {'AND': [{'type': 'revenue', 'operator': '>=', 'value': 500000}]},
            'points': 250000,
            'reward_type': 'title',
            'reward_value': {'title': 'Imperador', 'permanent': True}
        }
    ])
    
    # ============================================================================
    # CATEGORIA: STREAK
    # ============================================================================
    
    achievements.extend([
        {
            'slug': 'streak_3_bronze',
            'name': 'Aquecendo',
            'description': 'Venda por 3 dias consecutivos',
            'icon': 'fa-fire',
            'category': 'streak',
            'tier': 1,
            'rarity': 'common',
            'estimated_completion_rate': 0.45,
            'requirements': {'AND': [{'type': 'streak', 'operator': '>=', 'value': 3}]},
            'points': 300,
            'reward_type': 'xp',
            'reward_value': {'xp': 300}
        },
        {
            'slug': 'streak_7_silver',
            'name': 'Semana Perfeita',
            'description': 'Venda por 7 dias consecutivos',
            'icon': 'fa-fire-alt',
            'category': 'streak',
            'tier': 2,
            'rarity': 'uncommon',
            'estimated_completion_rate': 0.25,
            'requirements': {'AND': [{'type': 'streak', 'operator': '>=', 'value': 7}]},
            'points': 2000,
            'reward_type': 'multiplier',
            'reward_value': {'multiplier': 1.1, 'duration_days': 7}
        },
        {
            'slug': 'streak_30_gold',
            'name': 'Incansável',
            'description': 'Venda por 30 dias consecutivos',
            'icon': 'fa-infinity',
            'category': 'streak',
            'tier': 3,
            'rarity': 'epic',
            'estimated_completion_rate': 0.08,
            'requirements': {'AND': [{'type': 'streak', 'operator': '>=', 'value': 30}]},
            'points': 15000,
            'reward_type': 'commission_discount',
            'reward_value': {'discount': 0.75, 'duration_days': 30}
        },
        {
            'slug': 'streak_90_platinum',
            'name': 'Máquina de Vendas',
            'description': 'Venda por 90 dias consecutivos',
            'icon': 'fa-bolt',
            'category': 'streak',
            'tier': 4,
            'rarity': 'legendary',
            'estimated_completion_rate': 0.02,
            'requirements': {'AND': [{'type': 'streak', 'operator': '>=', 'value': 90}]},
            'points': 50000,
            'reward_type': 'title',
            'reward_value': {'title': 'Imortal'}
        }
    ])
    
    # ============================================================================
    # CATEGORIA: VELOCIDADE (SPEED)
    # ============================================================================
    
    achievements.extend([
        {
            'slug': 'first_sale_24h_bronze',
            'name': 'Início Rápido',
            'description': 'Realize sua primeira venda em menos de 24h após cadastro',
            'icon': 'fa-running',
            'category': 'speed',
            'tier': 1,
            'rarity': 'uncommon',
            'estimated_completion_rate': 0.30,
            'requirements': {'AND': [{'type': 'first_sale_hours', 'operator': '<=', 'value': 24}]},
            'points': 1500,
            'reward_type': 'currency',
            'reward_value': {'currency': 'gems', 'amount': 25}
        },
        {
            'slug': 'sales_10_day_silver',
            'name': 'Dia Produtivo',
            'description': 'Realize 10 vendas em um único dia',
            'icon': 'fa-calendar-day',
            'category': 'speed',
            'tier': 2,
            'rarity': 'rare',
            'estimated_completion_rate': 0.15,
            'requirements': {'AND': [{'type': 'daily_sales', 'operator': '>=', 'value': 10}]},
            'points': 5000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 18}
        },
        {
            'slug': 'revenue_1k_day_gold',
            'name': 'Dia de Ouro',
            'description': 'Fature R$ 1.000 em um único dia',
            'icon': 'fa-sun',
            'category': 'speed',
            'tier': 3,
            'rarity': 'epic',
            'estimated_completion_rate': 0.10,
            'requirements': {'AND': [{'type': 'daily_revenue', 'operator': '>=', 'value': 1000}]},
            'points': 10000,
            'reward_type': 'title',
            'reward_value': {'title': 'Relâmpago'}
        }
    ])
    
    # ============================================================================
    # CATEGORIA: TÉCNICA (TECHNICAL)
    # ============================================================================
    
    achievements.extend([
        {
            'slug': 'config_complete_bronze',
            'name': 'Configurado',
            'description': 'Configure completamente seu bot (mensagem, mídia, botões, access link)',
            'icon': 'fa-cog',
            'category': 'technical',
            'tier': 1,
            'rarity': 'common',
            'estimated_completion_rate': 0.70,
            'requirements': {'AND': [{'type': 'bot_config_complete', 'operator': '==', 'value': 1}]},
            'points': 500,
            'reward_type': 'xp',
            'reward_value': {'xp': 500}
        },
        {
            'slug': 'order_bump_active_silver',
            'name': 'Upseller',
            'description': 'Ative um Order Bump e tenha pelo menos 1 aceitação',
            'icon': 'fa-plus-square',
            'category': 'technical',
            'tier': 2,
            'rarity': 'uncommon',
            'estimated_completion_rate': 0.40,
            'requirements': {
                'AND': [
                    {'type': 'order_bump_enabled', 'operator': '==', 'value': 1},
                    {'type': 'order_bump_accepted', 'operator': '>=', 'value': 1}
                ]
            },
            'points': 2000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 21}
        },
        {
            'slug': 'downsell_conversion_gold',
            'name': 'Mestre do Downsell',
            'description': 'Converta 5 vendas via Downsell',
            'icon': 'fa-layer-group',
            'category': 'technical',
            'tier': 3,
            'rarity': 'rare',
            'estimated_completion_rate': 0.20,
            'requirements': {'AND': [{'type': 'downsell_conversions', 'operator': '>=', 'value': 5}]},
            'points': 8000,
            'reward_type': 'title',
            'reward_value': {'title': 'Estrategista'}
        }
    ])
    
    # ============================================================================
    # CATEGORIA: MARKETING
    # ============================================================================
    
    achievements.extend([
        {
            'slug': 'remarketing_sent_bronze',
            'name': 'Remarketer Iniciante',
            'description': 'Envie sua primeira campanha de remarketing',
            'icon': 'fa-bullhorn',
            'category': 'marketing',
            'tier': 1,
            'rarity': 'common',
            'estimated_completion_rate': 0.50,
            'requirements': {'AND': [{'type': 'remarketing_campaigns_sent', 'operator': '>=', 'value': 1}]},
            'points': 1000,
            'reward_type': 'xp',
            'reward_value': {'xp': 1000}
        },
        {
            'slug': 'remarketing_conversion_silver',
            'name': 'Recuperador',
            'description': 'Converta 10 vendas via remarketing',
            'icon': 'fa-redo',
            'category': 'marketing',
            'tier': 2,
            'rarity': 'uncommon',
            'estimated_completion_rate': 0.25,
            'requirements': {'AND': [{'type': 'remarketing_conversions', 'operator': '>=', 'value': 10}]},
            'points': 5000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 25}
        },
        {
            'slug': 'conversion_rate_20_gold',
            'name': 'Mago da Conversão',
            'description': 'Alcance 20% de taxa de conversão com no mínimo 200 leads',
            'icon': 'fa-magic',
            'category': 'marketing',
            'tier': 3,
            'rarity': 'legendary',
            'estimated_completion_rate': 0.05,
            'requirements': {
                'AND': [
                    {'type': 'conversion_rate', 'operator': '>=', 'value': 20},
                    {'type': 'bot_users', 'operator': '>=', 'value': 200}
                ]
            },
            'points': 30000,
            'reward_type': 'title',
            'reward_value': {'title': 'Mago'}
        }
    ])
    
    # ============================================================================
    # CATEGORIA: RANKING
    # ============================================================================
    
    achievements.extend([
        {
            'slug': 'top100_bronze',
            'name': 'Entre os Melhores',
            'description': 'Entre no Top 100 do ranking geral',
            'icon': 'fa-chart-bar',
            'category': 'ranking',
            'tier': 1,
            'rarity': 'uncommon',
            'estimated_completion_rate': 0.10,
            'requirements': {'AND': [{'type': 'ranking_position', 'operator': '<=', 'value': 100}]},
            'points': 5000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 27}
        },
        {
            'slug': 'top10_silver',
            'name': 'Elite',
            'description': 'Entre no Top 10 do ranking geral',
            'icon': 'fa-award',
            'category': 'ranking',
            'tier': 2,
            'rarity': 'rare',
            'estimated_completion_rate': 0.01,
            'requirements': {'AND': [{'type': 'ranking_position', 'operator': '<=', 'value': 10}]},
            'points': 25000,
            'reward_type': 'title',
            'reward_value': {'title': 'Elite'}
        },
        {
            'slug': 'rank1_gold',
            'name': 'Número 1',
            'description': 'Alcance o 1º lugar no ranking geral',
            'icon': 'fa-crown',
            'category': 'ranking',
            'tier': 3,
            'rarity': 'legendary',
            'estimated_completion_rate': 0.001,
            'requirements': {'AND': [{'type': 'ranking_position', 'operator': '==', 'value': 1}]},
            'points': 100000,
            'reward_type': 'title',
            'reward_value': {'title': 'Campeão'}
        },
        {
            'slug': 'league_promotion_silver',
            'name': 'Promoção',
            'description': 'Seja promovido para uma liga superior',
            'icon': 'fa-level-up-alt',
            'category': 'ranking',
            'tier': 2,
            'rarity': 'common',
            'estimated_completion_rate': 0.30,
            'max_completions': 999,
            'requirements': {'AND': [{'type': 'league_promoted', 'operator': '==', 'value': 1}]},
            'points': 3000,
            'reward_type': 'currency',
            'reward_value': {'currency': 'gems', 'amount': 50}
        }
    ])
    
    # ============================================================================
    # CATEGORIA: CONQUISTAS SECRETAS
    # ============================================================================
    
    achievements.extend([
        {
            'slug': 'midnight_sale_secret',
            'name': 'Coruja Noturna',
            'description': 'Realize uma venda entre 00h e 05h',
            'icon': 'fa-moon',
            'category': 'secret',
            'tier': 2,
            'rarity': 'rare',
            'is_secret': True,
            'estimated_completion_rate': 0.20,
            'requirements': {
                'AND': [
                    {'type': 'sale_hour', 'operator': '>=', 'value': 0},
                    {'type': 'sale_hour', 'operator': '<', 'value': 5}
                ]
            },
            'points': 5000,
            'reward_type': 'title',
            'reward_value': {'title': 'Coruja'}
        },
        {
            'slug': 'perfect_week_secret',
            'name': 'Semana Impecável',
            'description': 'Venda todos os dias da semana sem quebrar o streak',
            'icon': 'fa-calendar-check',
            'category': 'secret',
            'tier': 2,
            'rarity': 'epic',
            'is_secret': True,
            'estimated_completion_rate': 0.15,
            'requirements': {'AND': [{'type': 'perfect_week', 'operator': '==', 'value': 1}]},
            'points': 10000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 32}
        },
        {
            'slug': 'lucky_777_secret',
            'name': 'Jackpot',
            'description': 'Alcance exatamente 777 vendas totais',
            'icon': 'fa-dice',
            'category': 'secret',
            'tier': 3,
            'rarity': 'legendary',
            'is_secret': True,
            'estimated_completion_rate': 0.01,
            'requirements': {'AND': [{'type': 'sales', 'operator': '==', 'value': 777}]},
            'points': 77700,
            'reward_type': 'title',
            'reward_value': {'title': 'Sortudo'}
        },
        {
            'slug': 'all_gateways_secret',
            'name': 'Polivalente',
            'description': 'Configure e use todos os gateways de pagamento disponíveis',
            'icon': 'fa-boxes',
            'category': 'secret',
            'tier': 3,
            'rarity': 'epic',
            'is_secret': True,
            'estimated_completion_rate': 0.10,
            'requirements': {'AND': [{'type': 'all_gateways_configured', 'operator': '==', 'value': 1}]},
            'points': 15000,
            'reward_type': 'badge',
            'reward_value': {'badge_id': 34}
        }
    ])
    
    # ============================================================================
    # CATEGORIA: EVENTOS SAZONAIS
    # ============================================================================
    
    achievements.extend([
        {
            'slug': 'season1_winner',
            'name': 'Campeão da Season 1',
            'description': 'Termine em 1º lugar na Season 1',
            'icon': 'fa-trophy',
            'category': 'seasonal',
            'tier': 5,
            'rarity': 'mythic',
            'is_seasonal': True,
            'season_id': 1,
            'estimated_completion_rate': 0.001,
            'requirements': {
                'AND': [
                    {'type': 'season_rank', 'operator': '==', 'value': 1},
                    {'type': 'season_id', 'operator': '==', 'value': 1}
                ]
            },
            'points': 500000,
            'reward_type': 'title',
            'reward_value': {'title': 'Campeão S1', 'permanent': True}
        },
        {
            'slug': 'black_friday_2025',
            'name': 'Black Friday Master',
            'description': 'Realize 50 vendas durante o evento de Black Friday 2025',
            'icon': 'fa-shopping-cart',
            'category': 'seasonal',
            'tier': 3,
            'rarity': 'epic',
            'is_seasonal': True,
            'estimated_completion_rate': 0.15,
            'requirements': {'AND': [{'type': 'black_friday_sales', 'operator': '>=', 'value': 50}]},
            'points': 20000,
            'reward_type': 'commission_discount',
            'reward_value': {'discount': 2.0, 'duration_days': 60}
        }
    ])
    
    return achievements


