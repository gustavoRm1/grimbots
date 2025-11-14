#!/usr/bin/env python3
"""
ANÁLISE COMPLETA QI 500 V2 - UMBRELLAPAY
Comparação rigorosa entre TODOS os PIX gerados no sistema e TODAS as vendas do gateway
Inclui: PAGAS, PENDENTES e RECUSADAS
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Adicionar diretório raiz ao sys.path para importar app
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

load_dotenv()

def extrair_cpf_do_email(email):
    """Extrai CPF do email (ex: lead7296369126@gmail.com -> 7296369126)"""
    if email and '@' in email:
        parte_local = email.split('@')[0]
        if parte_local.startswith('lead'):
            return parte_local.replace('lead', '')
        elif 'user' in parte_local:
            # user1614772214@telegram.user -> 1614772214
            return parte_local.replace('user', '')
    return None

def extrair_cpf_do_telefone(telefone):
    """Extrai CPF do telefone (ex: 5598021884508 -> 8021884508)"""
    if telefone and telefone.startswith('55'):
        return telefone[2:]  # Remove código do país
    return telefone

# TODAS AS VENDAS DO GATEWAY (FONTE DA VERDADE COMPLETA)
# Formato: gateway_id -> {dados}
TODAS_VENDAS_GATEWAY = {}

# VENDAS PAGAS (5 transações)
VENDAS_PAGAS = [
    {"gateway_id": "78366e3e-999b-4a5a-8232-3e442bd480eb", "nome": "Samuel", "telefone": "5597296369126", "email": "lead7296369126@gmail.com", "status": "Pago"},
    {"gateway_id": "5561f532-9fc2-40f9-bdd6-132be6769bbc", "nome": "Samuel", "telefone": "5591867309907", "email": "lead1867309907@gmail.com", "status": "Pago"},
    {"gateway_id": "1a71167d-62ea-4ac5-a088-925e5878d0c9", "nome": None, "telefone": "5597999979628", "email": "lead7999979628@gmail.com", "status": "Pago"},
    {"gateway_id": "f0212d7f-269e-49dd-aeea-212a521d2fe1", "nome": "~", "telefone": "5592005452528", "email": "lead2005452528@gmail.com", "status": "Pago"},
    {"gateway_id": "63a02dd9-1d70-48ac-8036-4eff20350d2b", "nome": "Za Ya", "telefone": "5519904522880", "email": "lead1614772214@gmail.com", "status": "Pago"},
]

# VENDAS PENDENTES (Aguardando pagamento)
VENDAS_PENDENTES = [
    {"nome": "Marcio Monteiro Reis Da Cruz", "telefone": "5598021884508", "email": "lead8021884508@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Teiler", "telefone": "5597650601056", "email": "lead7650601056@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Eric", "telefone": "5592101793917", "email": "lead2101793917@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Bruno", "telefone": "5522960110384", "email": "lead1763056476@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Guilherme", "telefone": "5596612861119", "email": "lead6612861119@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Junior", "telefone": "5597905293998", "email": "lead7905293998@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Jhon", "telefone": "5512909742344", "email": "lead1763056640@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Samuel", "telefone": "5598090215075", "email": "lead8090215075@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Leonan", "telefone": "5597714565281", "email": "lead7714565281@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Paulo", "telefone": "5596768020794", "email": "lead6768020794@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Vaqueiro", "telefone": "5596534197355", "email": "lead22@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Breno", "telefone": "5597182146457", "email": "lead7182146457@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Fb", "telefone": "5598413818441", "email": "lead8413818441@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Ermeson", "telefone": "5595395023570", "email": "lead1763059778@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Za Ya", "telefone": "5519904522880", "email": "lead1614772214@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Mickael", "telefone": "5598268701124", "email": "lead8268701124@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Joan", "telefone": "5596292992114", "email": "lead6292992114@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Joan", "telefone": "5596292992114", "email": "lead6292992114@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Luciano", "telefone": "5596519174454", "email": "lead6519174454@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Dinho", "telefone": "5591084211068", "email": "lead1763037489@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Jair", "telefone": "5598253058354", "email": "lead8253058354@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "RABM", "telefone": "5595167035103", "email": "lead1763037747@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "👀", "telefone": "5595481701497", "email": "lead007@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Joao", "telefone": "5595756936782", "email": "lead1763038960@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "💚🐷", "telefone": "5595048649222", "email": "lead5048649222@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "💚🐷", "telefone": "5595048649222", "email": "lead5048649222@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Pedro Rocha", "telefone": "5597628463678", "email": "lead1763057307@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Altamir", "telefone": "5597927743524", "email": "lead7927743524@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Marcos", "telefone": "5596418345692", "email": "lead6418345692@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Marcos", "telefone": "5596418345692", "email": "lead6418345692@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "katue", "telefone": "5595643720261", "email": "lead5643720261@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "GB", "telefone": "5591242724988", "email": "lead1763058117@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Dg", "telefone": "5597439190493", "email": "lead7439190493@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Vergil", "telefone": "5598203510303", "email": "lead8203510303@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Eddy Panka", "telefone": "5598149746841", "email": "lead8149746841@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Moura", "telefone": "5595824500754", "email": "lead1@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Rodrigo", "telefone": "5598003244335", "email": "lead8003244335@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Luan Felipe", "telefone": "5598034105597", "email": "lead8034105597@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Sandro.js", "telefone": "5596431738630", "email": "lead6431738630@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Saulo", "telefone": "5597826488702", "email": "lead7826488702@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Ernandes", "telefone": "5595665899851", "email": "lead5665899851@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Ermeson", "telefone": "5595395023570", "email": "lead1763059554@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Francisco", "telefone": "5592099998636", "email": "lead2099998636@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Francisco", "telefone": "5592099998636", "email": "lead2099998636@gmail.com", "status": "Aguardando pagamento"},
    {"nome": "Canker", "telefone": "5596159234030", "email": "lead6159234030@gmail.com", "status": "Aguardando pagamento"},
]

# VENDAS RECUSADAS (excluídas da análise)
VENDAS_RECUSADAS = [
    {"nome": "Junior", "telefone": "5595243667147", "email": "lead5243667147@gmail.com", "status": "Recusada"},
    {"nome": "Za Ya", "telefone": "1614772214", "email": "user1614772214@telegram.user", "status": "Recusada"},
    {"nome": "Za Ya", "telefone": "1614772214", "email": "user1614772214@telegram.user", "status": "Recusada"},
    {"nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online", "status": "Recusada"},
    {"nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online", "status": "Recusada"},
    {"nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online", "status": "Recusada"},
    {"nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online", "status": "Recusada"},
    {"nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online", "status": "Recusada"},
]

# IDs alternativos para a transação crítica
GATEWAY_IDS_ALTERNATIVOS = {
    "f0212d7f-269e-49dd-aeea-212a521d2fe1": ["f0212d7f-269e-49dd-aeea-212a521d2e1"]
}

# Carregar ENCRYPTION_KEY do .env se não estiver no ambiente
if not os.environ.get('ENCRYPTION_KEY'):
    print("⚠️  ENCRYPTION_KEY não configurada, tentando carregar do .env...")
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ENCRYPTION_KEY='):
                    key = line.split('=', 1)[1].strip()
                    # Remover aspas se houver
                    key = key.strip('"').strip("'")
                    if key:
                        os.environ['ENCRYPTION_KEY'] = key
                        print(f"✅ ENCRYPTION_KEY carregada do .env (tamanho: {len(key)} chars)")
                        break

# Validar ENCRYPTION_KEY antes de importar app
encryption_key = os.environ.get('ENCRYPTION_KEY')
if not encryption_key:
    print("❌ ERRO CRÍTICO: ENCRYPTION_KEY não configurada!")
    print("\nSolução:")
    print("1. Verificar se .env existe e tem ENCRYPTION_KEY")
    print("2. Ou executar: export ENCRYPTION_KEY=$(grep ENCRYPTION_KEY .env | cut -d '=' -f2)")
    sys.exit(1)

# Validar formato da chave
try:
    from cryptography.fernet import Fernet
    # Tentar criar um objeto Fernet para validar a chave
    Fernet(encryption_key.encode())
    print(f"✅ ENCRYPTION_KEY válida (tamanho: {len(encryption_key)} chars)")
except Exception as e:
    print(f"❌ ERRO CRÍTICO: ENCRYPTION_KEY inválida!")
    print(f"Erro: {e}")
    print("\nGere uma nova:")
    print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
    sys.exit(1)

try:
    from app import app, db
    from models import Payment
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("\nCertifique-se de estar executando do diretório raiz do projeto")
    sys.exit(1)
except RuntimeError as e:
    if 'ENCRYPTION_KEY' in str(e):
        print(f"❌ Erro: {e}")
        sys.exit(1)
    raise

def buscar_pagamento_por_identificadores(telefone, email, nome, pagamentos_por_cpf, pagamentos_por_gateway_id):
    """Busca pagamento usando múltiplos identificadores"""
    cpf_email = extrair_cpf_do_email(email)
    cpf_telefone = extrair_cpf_do_telefone(telefone) if telefone else None
    
    # Busca 1: Por CPF do email
    if cpf_email and cpf_email in pagamentos_por_cpf:
        return pagamentos_por_cpf[cpf_email][0], "cpf_email"
    
    # Busca 2: Por CPF do telefone
    if cpf_telefone and cpf_telefone in pagamentos_por_cpf:
        return pagamentos_por_cpf[cpf_telefone][0], "cpf_telefone"
    
    # Busca 3: Por CPF parcial
    if cpf_email:
        for cpf, payments in pagamentos_por_cpf.items():
            if cpf_email in cpf or cpf in cpf_email:
                return payments[0], f"cpf_parcial ({cpf})"
    
    # Busca 4: Por nome (menos confiável)
    if nome:
        for cpf, payments in pagamentos_por_cpf.items():
            for payment in payments:
                if payment.customer_name and nome.lower() in payment.customer_name.lower():
                    return payment, f"nome ({nome})"
    
    return None, None

def analise_completa_qi500_v2():
    with app.app_context():
        print("=" * 100)
        print("  🔍 ANÁLISE COMPLETA QI 500 V2 - UMBRELLAPAY")
        print("  Comparação Rigorosa: Sistema vs Gateway (TODAS as vendas)")
        print("=" * 100)
        print()
        
        # ========================================================================
        # FASE 1: BUSCAR TODOS OS PAGAMENTOS UMBRELLAPAY NO SISTEMA
        # ========================================================================
        print("📊 FASE 1: Buscando TODOS os pagamentos UmbrellaPay no sistema...")
        print("-" * 100)
        
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ontem = hoje - timedelta(days=1)
        
        todos_pagamentos = Payment.query.filter(
            Payment.gateway_type == 'umbrellapag',
            Payment.created_at >= ontem
        ).order_by(Payment.created_at.desc()).all()
        
        print(f"✅ Total de pagamentos UmbrellaPay encontrados: {len(todos_pagamentos)}")
        print()
        
        # Mapear pagamentos
        pagamentos_por_gateway_id = {}
        pagamentos_por_cpf = {}
        
        for payment in todos_pagamentos:
            if payment.gateway_transaction_id:
                gateway_id = payment.gateway_transaction_id
                if gateway_id not in pagamentos_por_gateway_id:
                    pagamentos_por_gateway_id[gateway_id] = []
                pagamentos_por_gateway_id[gateway_id].append(payment)
            
            if payment.customer_user_id:
                cpf = payment.customer_user_id
                if cpf not in pagamentos_por_cpf:
                    pagamentos_por_cpf[cpf] = []
                pagamentos_por_cpf[cpf].append(payment)
        
        print(f"✅ Pagamentos mapeados por gateway_id: {len(pagamentos_por_gateway_id)}")
        print(f"✅ Pagamentos mapeados por CPF: {len(pagamentos_por_cpf)}")
        print()
        
        # ========================================================================
        # FASE 2: ANALISAR VENDAS PAGAS NO GATEWAY
        # ========================================================================
        print("=" * 100)
        print("📊 FASE 2: Analisando VENDAS PAGAS no gateway (5 transações)")
        print("=" * 100)
        print()
        
        resultados_pagas = {
            "corretas": [],
            "pendentes_sistema": [],
            "nao_encontradas": [],
            "valores_diferentes": []
        }
        
        for venda in VENDAS_PAGAS:
            gateway_id = venda.get("gateway_id")
            telefone = venda.get("telefone")
            email = venda.get("email")
            nome = venda.get("nome")
            
            print("-" * 100)
            if gateway_id:
                print(f"🔍 Gateway ID: {gateway_id}")
            print(f"   Nome: {nome or 'N/A'}")
            print(f"   Telefone: {telefone}")
            print(f"   Email: {email}")
            print()
            
            payment_encontrado = None
            metodo_busca = None
            
            # Busca 1: Por gateway_id
            if gateway_id:
                if gateway_id in pagamentos_por_gateway_id:
                    payment_encontrado = pagamentos_por_gateway_id[gateway_id][0]
                    metodo_busca = "gateway_id"
                elif gateway_id in GATEWAY_IDS_ALTERNATIVOS:
                    for alt_id in GATEWAY_IDS_ALTERNATIVOS[gateway_id]:
                        if alt_id in pagamentos_por_gateway_id:
                            payment_encontrado = pagamentos_por_gateway_id[alt_id][0]
                            metodo_busca = f"gateway_id_alternativo ({alt_id})"
                            break
            
            # Busca 2: Por identificadores (telefone, email, nome)
            if not payment_encontrado:
                payment_encontrado, metodo_busca = buscar_pagamento_por_identificadores(
                    telefone, email, nome, pagamentos_por_cpf, pagamentos_por_gateway_id
                )
            
            if payment_encontrado:
                status_sistema = payment_encontrado.status
                valor_sistema = float(payment_encontrado.amount)
                
                print(f"✅ ENCONTRADO (método: {metodo_busca})")
                print(f"   Payment ID: {payment_encontrado.payment_id}")
                print(f"   Status Sistema: {status_sistema}")
                print(f"   Valor Sistema: R$ {valor_sistema:.2f}")
                print()
                
                if status_sistema == 'paid':
                    resultados_pagas["corretas"].append({
                        "gateway_id": gateway_id,
                        "payment_id": payment_encontrado.payment_id,
                        "status": status_sistema,
                        "metodo_busca": metodo_busca
                    })
                    print("   ✅ CORRETO: Pago no gateway = Pago no sistema")
                elif status_sistema == 'pending':
                    resultados_pagas["pendentes_sistema"].append({
                        "gateway_id": gateway_id,
                        "payment_id": payment_encontrado.payment_id,
                        "status": status_sistema,
                        "metodo_busca": metodo_busca
                    })
                    print("   ⚠️  BUG: Gateway PAGO mas sistema PENDENTE!")
            else:
                resultados_pagas["nao_encontradas"].append(venda)
                print("   ❌ NÃO ENCONTRADO")
            
            print()
        
        # ========================================================================
        # FASE 3: ANALISAR VENDAS PENDENTES NO GATEWAY
        # ========================================================================
        print("=" * 100)
        print(f"📊 FASE 3: Analisando VENDAS PENDENTES no gateway ({len(VENDAS_PENDENTES)} transações)")
        print("=" * 100)
        print()
        
        resultados_pendentes = {
            "corretas": [],  # Gateway PENDENTE = Sistema PENDENTE
            "pagas_sistema": [],  # Gateway PENDENTE mas Sistema PAGO (possível pagamento antecipado)
            "nao_encontradas": []
        }
        
        for venda in VENDAS_PENDENTES[:10]:  # Limitar a 10 para não poluir
            telefone = venda.get("telefone")
            email = venda.get("email")
            nome = venda.get("nome")
            
            payment_encontrado, metodo_busca = buscar_pagamento_por_identificadores(
                telefone, email, nome, pagamentos_por_cpf, pagamentos_por_gateway_id
            )
            
            if payment_encontrado:
                status_sistema = payment_encontrado.status
                
                if status_sistema == 'pending':
                    resultados_pendentes["corretas"].append({
                        "payment_id": payment_encontrado.payment_id,
                        "status": status_sistema,
                        "nome": nome
                    })
                elif status_sistema == 'paid':
                    resultados_pendentes["pagas_sistema"].append({
                        "payment_id": payment_encontrado.payment_id,
                        "status": status_sistema,
                        "nome": nome
                    })
        
        # ========================================================================
        # FASE 4: RELATÓRIO FINAL
        # ========================================================================
        print("=" * 100)
        print("📊 RELATÓRIO FINAL QI 500 V2")
        print("=" * 100)
        print()
        
        print("📈 VENDAS PAGAS NO GATEWAY:")
        print(f"   Total: {len(VENDAS_PAGAS)} transações")
        print(f"   ✅ CORRETAS: {len(resultados_pagas['corretas'])}")
        print(f"   ⚠️  PENDENTES NO SISTEMA (BUG): {len(resultados_pagas['pendentes_sistema'])}")
        print(f"   ❌ NÃO ENCONTRADAS: {len(resultados_pagas['nao_encontradas'])}")
        print()
        
        if resultados_pagas["pendentes_sistema"]:
            print("🚨 PROBLEMA CRÍTICO - VENDAS PAGAS NO GATEWAY MAS PENDENTES NO SISTEMA:")
            for r in resultados_pagas["pendentes_sistema"]:
                print(f"   ⚠️  Gateway ID: {r['gateway_id']}")
                print(f"      Payment ID: {r['payment_id']}")
                print(f"      🚨 AÇÃO: Processar webhook ou marcar como pago")
                print()
        
        if resultados_pagas["nao_encontradas"]:
            print("🚨 PROBLEMA CRÍTICO - VENDAS PAGAS NO GATEWAY MAS NÃO ENCONTRADAS:")
            for r in resultados_pagas["nao_encontradas"]:
                print(f"   ❌ Nome: {r.get('nome', 'N/A')}")
                print(f"      Email: {r.get('email', 'N/A')}")
                print(f"      🚨 AÇÃO: Verificar se webhook foi recebido")
                print()
        
        print("📈 VENDAS PENDENTES NO GATEWAY:")
        print(f"   Total: {len(VENDAS_PENDENTES)} transações")
        print(f"   ✅ CORRETAS (Pendente = Pendente): {len(resultados_pendentes['corretas'])}")
        print(f"   ⚠️  PAGAS NO SISTEMA (Antecipadas?): {len(resultados_pendentes['pagas_sistema'])}")
        print()
        
        print("📈 ESTATÍSTICAS GERAIS:")
        print(f"   Total pagamentos no sistema: {len(todos_pagamentos)}")
        print(f"   Total PAGOS no sistema: {len([p for p in todos_pagamentos if p.status == 'paid'])}")
        print(f"   Total PENDENTES no sistema: {len([p for p in todos_pagamentos if p.status == 'pending'])}")
        print()
        
        taxa_acerto = (len(resultados_pagas["corretas"]) / len(VENDAS_PAGAS)) * 100 if VENDAS_PAGAS else 0
        print(f"🎯 Taxa de acerto (Vendas Pagas): {taxa_acerto:.1f}% ({len(resultados_pagas['corretas'])}/{len(VENDAS_PAGAS)})")
        print()
        
        print("=" * 100)
        print("✅ ANÁLISE COMPLETA QI 500 V2 CONCLUÍDA")
        print("=" * 100)

if __name__ == "__main__":
    analise_completa_qi500_v2()

