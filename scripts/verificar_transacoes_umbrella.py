#!/usr/bin/env python3
"""
Script para verificar transações do UmbrellaPay no sistema
Compara IDs do gateway com o banco de dados local
"""

import os
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ✅ CRÍTICO: Carregar variáveis de ambiente ANTES de importar app
from dotenv import load_dotenv
load_dotenv()

# Verificar se ENCRYPTION_KEY está configurada
if not os.environ.get('ENCRYPTION_KEY'):
    print("⚠️  ENCRYPTION_KEY não configurada, tentando carregar do .env...")
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('ENCRYPTION_KEY='):
                    key = line.split('=', 1)[1].strip()
                    os.environ['ENCRYPTION_KEY'] = key
                    break

try:
    from app import app, db
    from models import Payment
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("Certifique-se de estar executando do diretório raiz do projeto")
    sys.exit(1)
except RuntimeError as e:
    if 'ENCRYPTION_KEY' in str(e):
        print(f"❌ Erro: {e}")
        print("\nSolução:")
        print("1. Verificar se .env existe e tem ENCRYPTION_KEY")
        print("2. Ou executar: export ENCRYPTION_KEY=$(grep ENCRYPTION_KEY .env | cut -d '=' -f2)")
        sys.exit(1)
    raise

# IDs das transações fornecidas pelo gateway
TRANSACOES_GATEWAY = [
    {"id": "454ae28b-fafe-4248-aae5-12fada764bf5", "valor": 24.87, "cpf": "04986407953", "nome": "Marcio Monteiro Reis Da Cruz", "telefone": "5598021884508", "email": "lead8021884508@gmail.com"},
    {"id": "c88246c2-cb24-4f90-8625-8608676ee09a", "valor": 19.97, "cpf": "68528827488", "nome": "Teiler", "telefone": "5597650601056", "email": "lead7650601056@gmail.com"},
    {"id": "5c172285-b9ea-4793-a941-afe151b22801", "valor": 19.97, "cpf": "27621028807", "nome": "Eric", "telefone": "5592101793917", "email": "lead2101793917@gmail.com"},
    {"id": "722664db-384a-4342-94cf-603c0eea2702", "valor": 14.97, "cpf": "72037508174", "nome": "Junior", "telefone": "5595243667147", "email": "lead5243667147@gmail.com"},
    {"id": "bdee31e2-7da6-4825-ae54-5d9a5bd48f04", "valor": 32.86, "cpf": "74369846242", "nome": "Bruno", "telefone": "5522960110384", "email": "lead1763056476@gmail.com"},
    {"id": "e98fe6ca-4f29-4847-9c94-6ca8e2bb4b7e", "valor": 19.97, "cpf": "76495660057", "nome": "Guilherme", "telefone": "5596612861119", "email": "lead6612861119@gmail.com"},
    {"id": "86315068-8540-48c9-8979-d98303ad9892", "valor": 32.86, "cpf": "52735525910", "nome": "Junior", "telefone": "5597905293998", "email": "lead7905293998@gmail.com"},
    {"id": "bd9634b4-5898-4ef5-b360-44ec0a2e1e6a", "valor": 177.94, "cpf": "02086511604", "nome": "Jhon", "telefone": "5512909742344", "email": "lead1763056640@gmail.com"},
    {"id": "5561f532-9fc2-40f9-bdd6-132be6769bbc", "valor": 14.97, "cpf": "21367127726", "nome": "Samuel", "telefone": "5591867309907", "email": "lead1867309907@gmail.com"},
    {"id": "6cff8262-b2fd-43d5-9501-7d7cb57fbfef", "valor": 19.97, "cpf": "95396488662", "nome": "Samuel", "telefone": "5598090215075", "email": "lead8090215075@gmail.com"},
    {"id": "e7fa25e1-98c1-4acc-8ff4-6e6c21d9b35e", "valor": 14.97, "cpf": "09858113315", "nome": "Leonan", "telefone": "5597714565281", "email": "lead7714565281@gmail.com"},
    {"id": "3420c849-7dea-494d-bd75-e553776f5318", "valor": 32.86, "cpf": "16524673352", "nome": "Paulo", "telefone": "5596768020794", "email": "lead6768020794@gmail.com"},
    {"id": "65a6d20a-3a2a-4ded-a035-9969659f42c1", "valor": 32.86, "cpf": "34551590363", "nome": "Vaqueiro", "telefone": "5596534197355", "email": "lead22@gmail.com"},
    {"id": "a0cd464c-7361-449c-bcac-286d2e7aa853", "valor": 24.87, "cpf": "79928433127", "nome": "Breno", "telefone": "5597182146457", "email": "lead7182146457@gmail.com"},
    {"id": "92998f88-70a6-470a-b5e6-3145ae9cbe90", "valor": 32.86, "cpf": "30116599901", "nome": "Fb", "telefone": "5598413818441", "email": "lead8413818441@gmail.com"},
    {"id": "18b3488b-b030-417a-9cb5-274c41143609", "valor": 69.90, "cpf": "91338590944", "nome": "Ermeson", "telefone": "5595395023570", "email": "lead1763059778@gmail.com"},
    {"id": "80211675-fdd4-4edc-9af2-f719278b08ad", "valor": 24.87, "cpf": "16147722140", "nome": "Za Ya", "telefone": "1614772214", "email": "user1614772214@telegram.user"},
    {"id": "b425c8ba-accf-42a8-8bf7-734bbc6145f0", "valor": 24.87, "cpf": "16147722140", "nome": "Za Ya", "telefone": "1614772214", "email": "user1614772214@telegram.user"},
    {"id": "358d6cb7-84eb-49f7-b9fe-0adbb67377f2", "valor": 14.97, "cpf": "21064388156", "nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online"},
    {"id": "df22dff0-388e-4a20-8161-a541fe72fd98", "valor": 14.97, "cpf": "21064388156", "nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online"},
    {"id": "f68dd1f7-700c-4de4-b626-d05c2136ffea", "valor": 19.97, "cpf": "21064388156", "nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online"},
    {"id": "62d3863f-e747-4b67-92de-a49689bd6bbe", "valor": 32.86, "cpf": "21064388156", "nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online"},
    {"id": "fd2ffd9e-ac58-44a0-b0d0-9cf28cf64b99", "valor": 32.86, "cpf": "21064388156", "nome": "Za Ya", "telefone": "5591614772214", "email": "user1614772214@grimbots.online"},
    {"id": "d0dde35f-fed1-4645-8e56-81d226fc1914", "valor": 69.97, "cpf": "20129103608", "nome": "Za Ya", "telefone": "5519904522880", "email": "lead1614772214@gmail.com"},
    {"id": "63a02dd9-1d70-48ac-8036-4eff20350d2b", "valor": 2.00, "cpf": "20129103608", "nome": "Za Ya", "telefone": "5519904522880", "email": "lead1614772214@gmail.com"},
    {"id": "feac4996-713b-48ad-929d-2d0c30f856f7", "valor": 19.97, "cpf": "08110241301", "nome": "Mickael", "telefone": "5598268701124", "email": "lead8268701124@gmail.com"},
    {"id": "27deeea7-7f4a-4a1b-9145-9a9d558eeacb", "valor": 24.87, "cpf": "34969265208", "nome": "Joan", "telefone": "5596292992114", "email": "lead6292992114@gmail.com"},
    {"id": "f0212d7f-269e-49dd-aeea-212a521d2e1", "valor": 177.94, "cpf": "76664441926", "nome": "~", "telefone": "5592005452528", "email": "lead2005452528@gmail.com"},
    {"id": "8c15646f-3b76-49ea-8dd9-00339536099c", "valor": 14.97, "cpf": "34969265208", "nome": "Joan", "telefone": "5596292992114", "email": "lead6292992114@gmail.com"},
    {"id": "6330117a-cda7-4da7-a65e-82d7d086d95e", "valor": 19.97, "cpf": "77287406527", "nome": "Luciano", "telefone": "5596519174454", "email": "lead6519174454@gmail.com"},
    {"id": "425a5f31-7733-4682-a07c-4152e2945182", "valor": 19.97, "cpf": "21442345403", "nome": "Dinho", "telefone": "5591084211068", "email": "lead1763037489@gmail.com"},
    {"id": "283f2b4b-f0f4-4460-a405-259443a5cb1f", "valor": 19.97, "cpf": "70940748916", "nome": "Jair", "telefone": "5598253058354", "email": "lead8253058354@gmail.com"},
    {"id": "61e95772-4cd5-48bd-a3de-4176e29a2569", "valor": 32.86, "cpf": "53092378520", "nome": "RABM", "telefone": "5595167035103", "email": "lead1763037747@gmail.com"},
    {"id": "d5b97666-9eaf-442e-aaba-eee53e96cad8", "valor": 19.97, "cpf": "93193548715", "nome": "👀", "telefone": "5595481701497", "email": "lead007@gmail.com"},
    {"id": "b4eba878-a6a5-472e-9feb-ad3e4f434513", "valor": 19.97, "cpf": "83644176736", "nome": "Joao", "telefone": "5595756936782", "email": "lead1763038960@gmail.com"},
    {"id": "bfc9a555-113b-432f-8c1b-f7963308d325", "valor": 19.97, "cpf": "72629301176", "nome": "💚🐷", "telefone": "5595048649222", "email": "lead5048649222@gmail.com"},
    {"id": "bba23567-908a-41e0-8051-586869655ebe", "valor": 19.97, "cpf": "72629301176", "nome": "💚🐷", "telefone": "5595048649222", "email": "lead5048649222@gmail.com"},
    {"id": "1a71167d-62ea-4ac5-a088-925e5878d0c9", "valor": 32.86, "cpf": "62979277070", "nome": "Rodrigo", "telefone": "5597999979628", "email": "lead7999979628@gmail.com"},
    {"id": "78366e3e-999b-4a5a-8232-3e442bd480eb", "valor": 32.86, "cpf": "22932285254", "nome": ".", "telefone": "5597296369126", "email": "lead7296369126@gmail.com"},
    {"id": "4ee2b3c0-0910-41aa-9aa4-64af9b387028", "valor": 19.97, "cpf": "99130564891", "nome": "Pedro Rocha", "telefone": "5597628463678", "email": "lead1763057307@gmail.com"},
    {"id": "f4d8d570-3de9-4ebf-b74e-0f8991acf989", "valor": 24.87, "cpf": "65879128180", "nome": "Altamir", "telefone": "5597927743524", "email": "lead7927743524@gmail.com"},
    {"id": "1e988422-d007-43b9-9b73-c5beae715404", "valor": 32.86, "cpf": "34551590363", "nome": "Vaqueiro", "telefone": "5596534197355", "email": "lead22@gmail.com"},
    {"id": "748651d6-ad22-4459-9763-a97f5aa63572", "valor": 24.87, "cpf": "28265402031", "nome": "Marcos", "telefone": "5596418345692", "email": "lead6418345692@gmail.com"},
    {"id": "7c9a5e2d-a584-49f4-bc8f-0a4e7f6d9934", "valor": 149.97, "cpf": "28265402031", "nome": "Marcos", "telefone": "5596418345692", "email": "lead6418345692@gmail.com"},
    {"id": "8739b70e-a3f9-425f-8f8a-f2db1945bde9", "valor": 19.97, "cpf": "93849763501", "nome": "katue", "telefone": "5595643720261", "email": "lead5643720261@gmail.com"},
    {"id": "eccb8530-7667-4642-89d7-fa9f60871445", "valor": 19.97, "cpf": "78907079080", "nome": "GB", "telefone": "5591242724988", "email": "lead1763058117@gmail.com"},
    {"id": "828b626d-b31e-4405-9607-303331b36ef0", "valor": 19.97, "cpf": "88008017570", "nome": "Dg", "telefone": "5597439190493", "email": "lead7439190493@gmail.com"},
    {"id": "870957c7-8440-44bc-b8ec-dea5863304fa", "valor": 32.86, "cpf": "30683572334", "nome": "Vergil", "telefone": "5598203510303", "email": "lead8203510303@gmail.com"},
    {"id": "4515f361-d30f-4496-aa6b-682cd48a4e5c", "valor": 19.97, "cpf": "69383114800", "nome": "Eddy Panka", "telefone": "5598149746841", "email": "lead8149746841@gmail.com"},
    {"id": "e30aef35-be81-4eb6-a890-0deb76cf1016", "valor": 32.86, "cpf": "44183124557", "nome": "Moura", "telefone": "5595824500754", "email": "lead1@gmail.com"},
    {"id": "65a4184d-54b5-438f-8091-bf067297394f", "valor": 32.86, "cpf": "38698194303", "nome": "Rodrigo", "telefone": "5598003244335", "email": "lead8003244335@gmail.com"},
    {"id": "09895fa4-854f-40a5-8bf2-6501c7286919", "valor": 24.87, "cpf": "93766491334", "nome": "Luan Felipe", "telefone": "5598034105597", "email": "lead8034105597@gmail.com"},
    {"id": "ff651b4f-6f6a-42cf-bb91-4658b8c1576c", "valor": 24.87, "cpf": "71086233581", "nome": "Sandro.js", "telefone": "5596431738630", "email": "lead6431738630@gmail.com"},
    {"id": "9e7e184e-9c29-4fa2-8020-12e4aedfbd11", "valor": 19.97, "cpf": "19725891058", "nome": "Saulo", "telefone": "5597826488702", "email": "lead7826488702@gmail.com"},
    {"id": "a14a152b-aa62-473d-af81-2142c1d64483", "valor": 32.86, "cpf": "85061998596", "nome": "Ernandes", "telefone": "5595665899851", "email": "lead5665899851@gmail.com"},
    {"id": "d8dbb9f9-ec93-46ff-a788-2b32c640bd80", "valor": 24.87, "cpf": "90341120200", "nome": "Ermeson", "telefone": "5595395023570", "email": "lead1763059554@gmail.com"},
    {"id": "4b82d6f4-464d-44a2-8fb6-dd095d4d3dd5", "valor": 32.86, "cpf": "35829215144", "nome": "Francisco", "telefone": "5592099998636", "email": "lead2099998636@gmail.com"},
    {"id": "eefedc4d-fa76-4589-8043-6f800ee46995", "valor": 19.97, "cpf": "35829215144", "nome": "Francisco", "telefone": "5592099998636", "email": "lead2099998636@gmail.com"},
    {"id": "063a0a5d-eed1-4f7e-bbf2-bb353dee5d82", "valor": 32.86, "cpf": "97096922830", "nome": "Canker", "telefone": "5596159234030", "email": "lead6159234030@gmail.com"},
]

def verificar_transacoes():
    """Verifica transações do UmbrellaPay no sistema"""
    with app.app_context():
        print("=" * 80)
        print("  VERIFICAÇÃO DE TRANSAÇÕES UMBRELLAPAY")
        print("=" * 80)
        print(f"Total de transações no gateway: {len(TRANSACOES_GATEWAY)}")
        print("")
        
        # Separar transações encontradas e não encontradas
        encontradas_pagas = []
        encontradas_pendentes = []
        nao_encontradas = []
        valores_diferentes = []
        
        valor_total_gateway = 0
        valor_total_pagas = 0
        valor_total_pendentes = 0
        valor_total_nao_encontradas = 0
        
        for transacao in TRANSACOES_GATEWAY:
            gateway_id = transacao["id"]
            gateway_valor = transacao["valor"]
            gateway_cpf = transacao["cpf"]
            gateway_nome = transacao["nome"]
            gateway_telefone = transacao["telefone"]
            gateway_email = transacao["email"]
            
            valor_total_gateway += gateway_valor
            
            # Buscar por gateway_transaction_id (prioridade 1)
            payment = Payment.query.filter_by(
                gateway_type='umbrellapag',
                gateway_transaction_id=gateway_id
            ).first()
            
            if not payment:
                # Buscar por gateway_transaction_hash (prioridade 2)
                payment = Payment.query.filter_by(
                    gateway_type='umbrellapag',
                    gateway_transaction_hash=gateway_id
                ).first()
            
            if not payment:
                # Buscar por CPF e valor aproximado (prioridade 3)
                payment = Payment.query.filter(
                    Payment.gateway_type == 'umbrellapag',
                    Payment.customer_user_id.like(f'%{gateway_cpf}%'),
                    Payment.amount >= gateway_valor - 0.01,
                    Payment.amount <= gateway_valor + 0.01
                ).first()
            
            if not payment:
                # Buscar por telefone e valor aproximado (prioridade 4)
                # Remover símbolo + e espaços do telefone
                telefone_limpo = gateway_telefone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                payment = Payment.query.filter(
                    Payment.gateway_type == 'umbrellapag',
                    Payment.customer_username.like(f'%{telefone_limpo}%'),
                    Payment.amount >= gateway_valor - 0.01,
                    Payment.amount <= gateway_valor + 0.01
                ).first()
            
            if payment:
                # Verificar se o valor está correto
                valor_diferenca = abs(payment.amount - gateway_valor)
                
                if payment.status == 'paid':
                    encontradas_pagas.append({
                        'gateway_id': gateway_id,
                        'gateway_valor': gateway_valor,
                        'payment_id': payment.payment_id,
                        'payment_status': payment.status,
                        'payment_valor': payment.amount,
                        'payment_cpf': payment.customer_user_id,
                        'payment_nome': payment.customer_name,
                        'payment_telefone': payment.customer_username,
                        'payment_gateway_transaction_id': payment.gateway_transaction_id,
                        'payment_gateway_transaction_hash': payment.gateway_transaction_hash,
                        'created_at': payment.created_at,
                        'paid_at': payment.paid_at,
                        'valor_diferenca': valor_diferenca
                    })
                    valor_total_pagas += gateway_valor
                    
                    if valor_diferenca > 0.01:
                        valores_diferentes.append({
                            'gateway_id': gateway_id,
                            'gateway_valor': gateway_valor,
                            'payment_valor': payment.amount,
                            'diferenca': valor_diferenca
                        })
                else:
                    encontradas_pendentes.append({
                        'gateway_id': gateway_id,
                        'gateway_valor': gateway_valor,
                        'payment_id': payment.payment_id,
                        'payment_status': payment.status,
                        'payment_valor': payment.amount,
                        'payment_cpf': payment.customer_user_id,
                        'payment_nome': payment.customer_name,
                        'payment_telefone': payment.customer_username,
                        'payment_gateway_transaction_id': payment.gateway_transaction_id,
                        'payment_gateway_transaction_hash': payment.gateway_transaction_hash,
                        'created_at': payment.created_at,
                        'paid_at': payment.paid_at,
                        'valor_diferenca': valor_diferenca
                    })
                    valor_total_pendentes += gateway_valor
            else:
                nao_encontradas.append({
                    'gateway_id': gateway_id,
                    'gateway_valor': gateway_valor,
                    'gateway_cpf': gateway_cpf,
                    'gateway_nome': gateway_nome,
                    'gateway_telefone': gateway_telefone,
                    'gateway_email': gateway_email
                })
                valor_total_nao_encontradas += gateway_valor
        
        # Relatório
        print("=" * 80)
        print("  RESUMO")
        print("=" * 80)
        print(f"Total no Gateway: {len(TRANSACOES_GATEWAY)} transações - R$ {valor_total_gateway:.2f}")
        print(f"✅ Encontradas (PAID): {len(encontradas_pagas)} transações - R$ {valor_total_pagas:.2f}")
        print(f"⚠️  Encontradas (PENDING): {len(encontradas_pendentes)} transações - R$ {valor_total_pendentes:.2f}")
        print(f"❌ Não Encontradas: {len(nao_encontradas)} transações - R$ {valor_total_nao_encontradas:.2f}")
        print(f"🔴 Valores Diferentes: {len(valores_diferentes)} transações")
        print("")
        
        # Detalhes das transações PAGAS
        print("=" * 80)
        print("  TRANSAÇÕES PAGAS (PAID)")
        print("=" * 80)
        if encontradas_pagas:
            for i, trans in enumerate(encontradas_pagas, 1):
                print(f"\n{i}. Gateway ID: {trans['gateway_id']}")
                print(f"   Payment ID: {trans['payment_id']}")
                print(f"   Status: {trans['payment_status']}")
                print(f"   Valor Gateway: R$ {trans['gateway_valor']:.2f}")
                print(f"   Valor Payment: R$ {trans['payment_valor']:.2f}")
                if trans['valor_diferenca'] > 0.01:
                    print(f"   ⚠️  DIFERENÇA: R$ {trans['valor_diferenca']:.2f}")
                print(f"   CPF: {trans['payment_cpf']}")
                print(f"   Nome: {trans['payment_nome']}")
                print(f"   Telefone: {trans['payment_telefone']}")
                print(f"   Criado em: {trans['created_at']}")
                print(f"   Pago em: {trans['paid_at']}")
        else:
            print("Nenhuma transação paga encontrada")
        print("")
        
        # Detalhes das transações PENDENTES
        print("=" * 80)
        print("  TRANSAÇÕES PENDENTES (PENDING)")
        print("=" * 80)
        if encontradas_pendentes:
            for i, trans in enumerate(encontradas_pendentes, 1):
                print(f"\n{i}. Gateway ID: {trans['gateway_id']}")
                print(f"   Payment ID: {trans['payment_id']}")
                print(f"   Status: {trans['payment_status']}")
                print(f"   Valor Gateway: R$ {trans['gateway_valor']:.2f}")
                print(f"   Valor Payment: R$ {trans['payment_valor']:.2f}")
                if trans['valor_diferenca'] > 0.01:
                    print(f"   ⚠️  DIFERENÇA: R$ {trans['valor_diferenca']:.2f}")
                print(f"   CPF: {trans['payment_cpf']}")
                print(f"   Nome: {trans['payment_nome']}")
                print(f"   Telefone: {trans['payment_telefone']}")
                print(f"   Criado em: {trans['created_at']}")
        else:
            print("Nenhuma transação pendente encontrada")
        print("")
        
        # Detalhes das transações NÃO ENCONTRADAS
        print("=" * 80)
        print("  TRANSAÇÕES NÃO ENCONTRADAS")
        print("=" * 80)
        if nao_encontradas:
            for i, trans in enumerate(nao_encontradas, 1):
                print(f"\n{i}. Gateway ID: {trans['gateway_id']}")
                print(f"   Valor: R$ {trans['gateway_valor']:.2f}")
                print(f"   CPF: {trans['gateway_cpf']}")
                print(f"   Nome: {trans['gateway_nome']}")
                print(f"   Telefone: {trans['gateway_telefone']}")
                print(f"   Email: {trans['gateway_email']}")
        else:
            print("Todas as transações foram encontradas")
        print("")
        
        # Valores diferentes
        if valores_diferentes:
            print("=" * 80)
            print("  VALORES DIFERENTES")
            print("=" * 80)
            for i, trans in enumerate(valores_diferentes, 1):
                print(f"\n{i}. Gateway ID: {trans['gateway_id']}")
                print(f"   Valor Gateway: R$ {trans['gateway_valor']:.2f}")
                print(f"   Valor Payment: R$ {trans['payment_valor']:.2f}")
                print(f"   Diferença: R$ {trans['diferenca']:.2f}")
            print("")
        
        # Exportar para CSV
        import csv
        from datetime import datetime
        from pathlib import Path
        
        output_dir = Path("./exports")
        output_dir.mkdir(exist_ok=True)
        
        data_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        
        # CSV de transações pagas
        if encontradas_pagas:
            csv_file_pagas = output_dir / f"transacoes_pagas_{data_str}.csv"
            with open(csv_file_pagas, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['gateway_id', 'payment_id', 'status', 'valor_gateway', 'valor_payment', 'diferenca', 'cpf', 'nome', 'telefone', 'created_at', 'paid_at', 'gateway_transaction_id', 'gateway_transaction_hash']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for trans in encontradas_pagas:
                    writer.writerow({
                        'gateway_id': trans['gateway_id'],
                        'payment_id': trans['payment_id'],
                        'status': trans['payment_status'],
                        'valor_gateway': trans['gateway_valor'],
                        'valor_payment': trans['payment_valor'],
                        'diferenca': trans['valor_diferenca'],
                        'cpf': trans['payment_cpf'] or '',
                        'nome': trans['payment_nome'] or '',
                        'telefone': trans['payment_telefone'] or '',
                        'created_at': trans['created_at'].isoformat() if trans['created_at'] else '',
                        'paid_at': trans['paid_at'].isoformat() if trans['paid_at'] else '',
                        'gateway_transaction_id': trans['payment_gateway_transaction_id'] or '',
                        'gateway_transaction_hash': trans['payment_gateway_transaction_hash'] or ''
                    })
            print(f"✅ CSV de transações pagas salvo: {csv_file_pagas}")
        
        # CSV de transações pendentes
        if encontradas_pendentes:
            csv_file_pendentes = output_dir / f"transacoes_pendentes_{data_str}.csv"
            with open(csv_file_pendentes, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['gateway_id', 'payment_id', 'status', 'valor_gateway', 'valor_payment', 'diferenca', 'cpf', 'nome', 'telefone', 'created_at', 'gateway_transaction_id', 'gateway_transaction_hash']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for trans in encontradas_pendentes:
                    writer.writerow({
                        'gateway_id': trans['gateway_id'],
                        'payment_id': trans['payment_id'],
                        'status': trans['payment_status'],
                        'valor_gateway': trans['gateway_valor'],
                        'valor_payment': trans['payment_valor'],
                        'diferenca': trans['valor_diferenca'],
                        'cpf': trans['payment_cpf'] or '',
                        'nome': trans['payment_nome'] or '',
                        'telefone': trans['payment_telefone'] or '',
                        'created_at': trans['created_at'].isoformat() if trans['created_at'] else '',
                        'gateway_transaction_id': trans['payment_gateway_transaction_id'] or '',
                        'gateway_transaction_hash': trans['payment_gateway_transaction_hash'] or ''
                    })
            print(f"✅ CSV de transações pendentes salvo: {csv_file_pendentes}")
        
        # CSV de transações não encontradas
        if nao_encontradas:
            csv_file_nao_encontradas = output_dir / f"transacoes_nao_encontradas_{data_str}.csv"
            with open(csv_file_nao_encontradas, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['gateway_id', 'valor', 'cpf', 'nome', 'telefone', 'email']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for trans in nao_encontradas:
                    writer.writerow({
                        'gateway_id': trans['gateway_id'],
                        'valor': trans['gateway_valor'],
                        'cpf': trans['gateway_cpf'],
                        'nome': trans['gateway_nome'],
                        'telefone': trans['gateway_telefone'],
                        'email': trans['gateway_email']
                    })
            print(f"✅ CSV de transações não encontradas salvo: {csv_file_nao_encontradas}")
        
        print("")
        print("=" * 80)
        print("  VERIFICAÇÃO CONCLUÍDA")
        print("=" * 80)

if __name__ == '__main__':
    try:
        verificar_transacoes()
    except Exception as e:
        print(f"❌ Erro ao verificar transações: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

