#!/usr/bin/env python3
"""
ANÁLISE COMPLETA QI 500 - UMBRELLAPAY
Comparação rigorosa entre todos os PIX gerados no sistema e vendas pagas no gateway
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

# VENDAS PAGAS NO GATEWAY (FONTE DA VERDADE)
VENDAS_GATEWAY_PAGAS = {
    "78366e3e-999b-4a5a-8232-3e442bd480eb": {
        "valor": 32.86,
        "email": "lead7296369126@gmail.com",
        "cpf_email": "7296369126",
        "nome": "Samuel",
        "data_gateway": "13 de novembro às 15:22"
    },
    "5561f532-9fc2-40f9-bdd6-132be6769bbc": {
        "valor": 14.97,
        "email": "lead1867309907@gmail.com",
        "cpf_email": "1867309907",
        "nome": "Rodrigo",
        "data_gateway": "13 de novembro às 14:56"
    },
    "1a71167d-62ea-4ac5-a088-925e5878d0c9": {
        "valor": 32.86,
        "email": "lead7999979628@gmail.com",
        "cpf_email": "7999979628",
        "nome": None,
        "data_gateway": "13 de novembro às 10:06"
    },
    "f0212d7f-269e-49dd-aeea-212a521d2fe1": {  # Pode ser também f0212d7f-269e-49dd-aeea-212a521d2e1
        "valor": 177.94,
        "email": "lead2005452528@gmail.com",
        "cpf_email": "2005452528",
        "nome": "~",
        "data_gateway": "13 de novembro às 09:34"
    },
    "63a02dd9-1d70-48ac-8036-4eff20350d2b": {
        "valor": 2.00,
        "email": "lead1614772214@gmail.com",
        "cpf_email": "1614772214",
        "nome": "Za Ya",
        "data_gateway": "13 de novembro às 03:08"
    }
}

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

def analise_completa_qi500():
    with app.app_context():
        print("=" * 100)
        print("  🔍 ANÁLISE COMPLETA QI 500 - UMBRELLAPAY")
        print("  Comparação Rigorosa: Sistema vs Gateway")
        print("=" * 100)
        print()
        
        # ========================================================================
        # FASE 1: BUSCAR TODOS OS PAGAMENTOS UMBRELLAPAY NO SISTEMA
        # ========================================================================
        print("📊 FASE 1: Buscando TODOS os pagamentos UmbrellaPay no sistema...")
        print("-" * 100)
        
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ontem = hoje - timedelta(days=1)
        
        # Buscar todos os pagamentos UmbrellaPay (últimos 2 dias para garantir)
        todos_pagamentos = Payment.query.filter(
            Payment.gateway_type == 'umbrellapag',
            Payment.created_at >= ontem
        ).order_by(Payment.created_at.desc()).all()
        
        print(f"✅ Total de pagamentos UmbrellaPay encontrados: {len(todos_pagamentos)}")
        print()
        
        # ========================================================================
        # FASE 2: MAPEAR PAGAMENTOS POR GATEWAY_ID E CPF
        # ========================================================================
        print("📊 FASE 2: Mapeando pagamentos por gateway_id e CPF...")
        print("-" * 100)
        
        pagamentos_por_gateway_id = {}
        pagamentos_por_cpf = {}
        
        for payment in todos_pagamentos:
            # Mapear por gateway_transaction_id
            if payment.gateway_transaction_id:
                gateway_id = payment.gateway_transaction_id
                if gateway_id not in pagamentos_por_gateway_id:
                    pagamentos_por_gateway_id[gateway_id] = []
                pagamentos_por_gateway_id[gateway_id].append(payment)
            
            # Mapear por CPF (customer_user_id)
            if payment.customer_user_id:
                cpf = payment.customer_user_id
                if cpf not in pagamentos_por_cpf:
                    pagamentos_por_cpf[cpf] = []
                pagamentos_por_cpf[cpf].append(payment)
        
        print(f"✅ Pagamentos mapeados por gateway_id: {len(pagamentos_por_gateway_id)}")
        print(f"✅ Pagamentos mapeados por CPF: {len(pagamentos_por_cpf)}")
        print()
        
        # ========================================================================
        # FASE 3: COMPARAR CADA VENDA DO GATEWAY COM O SISTEMA
        # ========================================================================
        print("📊 FASE 3: Comparando vendas do gateway com o sistema...")
        print("=" * 100)
        print()
        
        resultados = {
            "corretas": [],           # Gateway PAGO = Sistema PAGO
            "pendentes_sistema": [],  # Gateway PAGO mas Sistema PENDENTE (BUG!)
            "nao_encontradas": [],     # Gateway PAGO mas não existe no sistema
            "valores_diferentes": []  # Gateway PAGO mas valor diferente
        }
        
        total_gateway = sum(v["valor"] for v in VENDAS_GATEWAY_PAGAS.values())
        
        for gateway_id, dados_gateway in VENDAS_GATEWAY_PAGAS.items():
            valor_gateway = dados_gateway["valor"]
            cpf_email = dados_gateway["cpf_email"]
            
            print("-" * 100)
            print(f"🔍 Analisando: {gateway_id}")
            print(f"   Gateway: R$ {valor_gateway:.2f} | CPF: {cpf_email} | Nome: {dados_gateway.get('nome', 'N/A')}")
            print()
            
            payment_encontrado = None
            metodo_busca = None
            
            # Busca 1: Por gateway_transaction_id exato
            if gateway_id in pagamentos_por_gateway_id:
                payment_encontrado = pagamentos_por_gateway_id[gateway_id][0]
                metodo_busca = "gateway_id_exato"
            
            # Busca 2: Por gateway_transaction_id alternativo (para a transação crítica)
            if not payment_encontrado and gateway_id in GATEWAY_IDS_ALTERNATIVOS:
                for alt_id in GATEWAY_IDS_ALTERNATIVOS[gateway_id]:
                    if alt_id in pagamentos_por_gateway_id:
                        payment_encontrado = pagamentos_por_gateway_id[alt_id][0]
                        metodo_busca = f"gateway_id_alternativo ({alt_id})"
                        break
            
            # Busca 3: Por CPF e valor aproximado
            if not payment_encontrado and cpf_email in pagamentos_por_cpf:
                for payment in pagamentos_por_cpf[cpf_email]:
                    if abs(float(payment.amount) - valor_gateway) <= 0.10:
                        payment_encontrado = payment
                        metodo_busca = "cpf_valor"
                        break
            
            # Busca 4: Por CPF parcial (caso CPF esteja truncado ou formatado)
            if not payment_encontrado:
                for cpf, payments in pagamentos_por_cpf.items():
                    if cpf_email in cpf or cpf in cpf_email:
                        for payment in payments:
                            if abs(float(payment.amount) - valor_gateway) <= 0.10:
                                payment_encontrado = payment
                                metodo_busca = f"cpf_parcial ({cpf})"
                                break
                        if payment_encontrado:
                            break
            
            if payment_encontrado:
                valor_sistema = float(payment_encontrado.amount)
                status_sistema = payment_encontrado.status
                diferenca_valor = abs(valor_sistema - valor_gateway)
                
                print(f"✅ ENCONTRADO NO SISTEMA (método: {metodo_busca})")
                print(f"   Payment ID: {payment_encontrado.payment_id}")
                print(f"   Gateway ID Sistema: {payment_encontrado.gateway_transaction_id}")
                print(f"   Status Sistema: {status_sistema}")
                print(f"   Valor Sistema: R$ {valor_sistema:.2f}")
                print(f"   Valor Gateway: R$ {valor_gateway:.2f}")
                print(f"   CPF Sistema: {payment_encontrado.customer_user_id}")
                print(f"   Nome Sistema: {payment_encontrado.customer_name}")
                print(f"   Criado em: {payment_encontrado.created_at}")
                if payment_encontrado.paid_at:
                    print(f"   Pago em: {payment_encontrado.paid_at}")
                print()
                
                # Classificar resultado
                if status_sistema == 'paid' and diferenca_valor <= 0.10:
                    resultados["corretas"].append({
                        "gateway_id": gateway_id,
                        "payment_id": payment_encontrado.payment_id,
                        "valor_gateway": valor_gateway,
                        "valor_sistema": valor_sistema,
                        "status": status_sistema,
                        "metodo_busca": metodo_busca
                    })
                    print("   ✅ STATUS: CORRETO (Pago no gateway = Pago no sistema)")
                elif status_sistema == 'pending':
                    resultados["pendentes_sistema"].append({
                        "gateway_id": gateway_id,
                        "payment_id": payment_encontrado.payment_id,
                        "valor_gateway": valor_gateway,
                        "valor_sistema": valor_sistema,
                        "status": status_sistema,
                        "metodo_busca": metodo_busca
                    })
                    print("   ⚠️  STATUS: BUG! Gateway marca como PAGO mas sistema está PENDENTE")
                    print("   🚨 AÇÃO NECESSÁRIA: Processar webhook ou marcar como pago manualmente")
                elif diferenca_valor > 0.10:
                    resultados["valores_diferentes"].append({
                        "gateway_id": gateway_id,
                        "payment_id": payment_encontrado.payment_id,
                        "valor_gateway": valor_gateway,
                        "valor_sistema": valor_sistema,
                        "diferenca": diferenca_valor,
                        "status": status_sistema,
                        "metodo_busca": metodo_busca
                    })
                    print(f"   ⚠️  STATUS: VALOR DIFERENTE (diferença: R$ {diferenca_valor:.2f})")
                else:
                    resultados["corretas"].append({
                        "gateway_id": gateway_id,
                        "payment_id": payment_encontrado.payment_id,
                        "valor_gateway": valor_gateway,
                        "valor_sistema": valor_sistema,
                        "status": status_sistema,
                        "metodo_busca": metodo_busca
                    })
                    print("   ✅ STATUS: CORRETO")
            else:
                resultados["nao_encontradas"].append({
                    "gateway_id": gateway_id,
                    "valor": valor_gateway,
                    "cpf": cpf_email,
                    "nome": dados_gateway.get('nome'),
                    "email": dados_gateway["email"]
                })
                print("   ❌ NÃO ENCONTRADO NO SISTEMA")
                print("   🚨 AÇÃO NECESSÁRIA: Verificar se webhook foi recebido")
                print("   🚨 AÇÃO NECESSÁRIA: Verificar se pagamento foi criado")
            
            print()
        
        # ========================================================================
        # FASE 4: ANÁLISE REVERSA - PAGAMENTOS PAGOS NO SISTEMA QUE NÃO ESTÃO NO GATEWAY
        # ========================================================================
        print("=" * 100)
        print("📊 FASE 4: Análise Reversa - Pagamentos PAGOS no sistema que NÃO estão no gateway...")
        print("-" * 100)
        print()
        
        pagamentos_pagos_sistema = [p for p in todos_pagamentos if p.status == 'paid']
        gateway_ids_encontrados = set()
        
        for resultado in resultados["corretas"] + resultados["pendentes_sistema"] + resultados["valores_diferentes"]:
            if "payment_id" in resultado:
                # Buscar payment_id no banco para pegar gateway_id
                payment = Payment.query.filter_by(payment_id=resultado["payment_id"]).first()
                if payment and payment.gateway_transaction_id:
                    gateway_ids_encontrados.add(payment.gateway_transaction_id)
        
        pagamentos_nao_no_gateway = []
        for payment in pagamentos_pagos_sistema:
            if payment.gateway_transaction_id and payment.gateway_transaction_id not in VENDAS_GATEWAY_PAGAS:
                if payment.gateway_transaction_id not in gateway_ids_encontrados:
                    # Verificar se não é um ID alternativo
                    is_alternativo = False
                    for main_id, alt_ids in GATEWAY_IDS_ALTERNATIVOS.items():
                        if payment.gateway_transaction_id in alt_ids:
                            is_alternativo = True
                            break
                    
                    if not is_alternativo:
                        pagamentos_nao_no_gateway.append(payment)
        
        if pagamentos_nao_no_gateway:
            print(f"⚠️  Encontrados {len(pagamentos_nao_no_gateway)} pagamento(s) PAGO(S) no sistema que NÃO estão na lista do gateway:")
            for payment in pagamentos_nao_no_gateway[:10]:  # Limitar a 10 para não poluir
                print(f"   ⚠️  {payment.payment_id}")
                print(f"      Gateway ID: {payment.gateway_transaction_id}")
                print(f"      Valor: R$ {payment.amount:.2f}")
                print(f"      CPF: {payment.customer_user_id}")
                print(f"      Criado em: {payment.created_at}")
                print()
        else:
            print("✅ Nenhum pagamento PAGO no sistema que não esteja no gateway")
            print()
        
        # ========================================================================
        # FASE 5: RELATÓRIO FINAL QI 500
        # ========================================================================
        print("=" * 100)
        print("📊 FASE 5: RELATÓRIO FINAL QI 500")
        print("=" * 100)
        print()
        
        total_corretas = sum(r["valor_sistema"] for r in resultados["corretas"])
        total_pendentes = sum(r["valor_sistema"] for r in resultados["pendentes_sistema"])
        total_nao_encontradas = sum(r["valor"] for r in resultados["nao_encontradas"])
        
        print("📈 RESUMO EXECUTIVO:")
        print("-" * 100)
        print(f"Total no Gateway (PAGAS): {len(VENDAS_GATEWAY_PAGAS)} transações - R$ {total_gateway:.2f}")
        print()
        print(f"✅ CORRETAS (Gateway PAGO = Sistema PAGO): {len(resultados['corretas'])} transações - R$ {total_corretas:.2f}")
        print(f"⚠️  PENDENTES NO SISTEMA (BUG!): {len(resultados['pendentes_sistema'])} transações - R$ {total_pendentes:.2f}")
        print(f"❌ NÃO ENCONTRADAS: {len(resultados['nao_encontradas'])} transações - R$ {total_nao_encontradas:.2f}")
        print(f"⚠️  VALORES DIFERENTES: {len(resultados['valores_diferentes'])} transações")
        print()
        
        # Detalhamento
        if resultados["corretas"]:
            print("✅ TRANSAÇÕES CORRETAS:")
            for r in resultados["corretas"]:
                print(f"   ✅ {r['gateway_id']}")
                print(f"      Payment ID: {r['payment_id']}")
                print(f"      Valor: R$ {r['valor_sistema']:.2f}")
                print(f"      Método busca: {r['metodo_busca']}")
                print()
        
        if resultados["pendentes_sistema"]:
            print("⚠️  TRANSAÇÕES PENDENTES NO SISTEMA (BUG CRÍTICO!):")
            for r in resultados["pendentes_sistema"]:
                print(f"   ⚠️  {r['gateway_id']}")
                print(f"      Payment ID: {r['payment_id']}")
                print(f"      Valor: R$ {r['valor_sistema']:.2f}")
                print(f"      Status: {r['status']}")
                print(f"      Método busca: {r['metodo_busca']}")
                print(f"      🚨 AÇÃO: Processar webhook ou marcar como pago manualmente")
                print()
        
        if resultados["nao_encontradas"]:
            print("❌ TRANSAÇÕES NÃO ENCONTRADAS:")
            for r in resultados["nao_encontradas"]:
                print(f"   ❌ {r['gateway_id']}")
                print(f"      Valor: R$ {r['valor']:.2f}")
                print(f"      CPF: {r['cpf']}")
                print(f"      Email: {r['email']}")
                print(f"      🚨 AÇÃO: Verificar se webhook foi recebido")
                print(f"      🚨 AÇÃO: Verificar se pagamento foi criado")
                print()
        
        if resultados["valores_diferentes"]:
            print("⚠️  TRANSAÇÕES COM VALORES DIFERENTES:")
            for r in resultados["valores_diferentes"]:
                print(f"   ⚠️  {r['gateway_id']}")
                print(f"      Gateway: R$ {r['valor_gateway']:.2f}")
                print(f"      Sistema: R$ {r['valor_sistema']:.2f}")
                print(f"      Diferença: R$ {r['diferenca']:.2f}")
                print()
        
        # Estatísticas gerais
        print("=" * 100)
        print("📊 ESTATÍSTICAS GERAIS:")
        print("-" * 100)
        print(f"Total de pagamentos UmbrellaPay no sistema: {len(todos_pagamentos)}")
        print(f"Total de pagamentos PAGOS no sistema: {len(pagamentos_pagos_sistema)}")
        print(f"Total de pagamentos PENDENTES no sistema: {len([p for p in todos_pagamentos if p.status == 'pending'])}")
        print()
        
        # Taxa de acerto
        taxa_acerto = (len(resultados["corretas"]) / len(VENDAS_GATEWAY_PAGAS)) * 100 if VENDAS_GATEWAY_PAGAS else 0
        print(f"Taxa de acerto: {taxa_acerto:.1f}% ({len(resultados['corretas'])}/{len(VENDAS_GATEWAY_PAGAS)})")
        print()
        
        # Conclusão
        print("=" * 100)
        print("🎯 CONCLUSÃO:")
        print("-" * 100)
        
        if len(resultados["corretas"]) == len(VENDAS_GATEWAY_PAGAS):
            print("✅ PERFEITO: Todas as vendas do gateway estão corretas no sistema!")
        elif resultados["pendentes_sistema"]:
            print(f"⚠️  PROBLEMA CRÍTICO: {len(resultados['pendentes_sistema'])} venda(s) está(ão) PENDENTE(s) no sistema")
            print("   mas o gateway marca como PAGO. WEBHOOK NÃO PROCESSOU!")
        elif resultados["nao_encontradas"]:
            print(f"❌ PROBLEMA CRÍTICO: {len(resultados['nao_encontradas'])} venda(s) não foi(ram) encontrada(s) no sistema")
            print("   WEBHOOK NÃO FOI RECEBIDO ou PAGAMENTO NÃO FOI CRIADO!")
        else:
            print("✅ Sistema está sincronizado com o gateway")
        
        print()
        print("=" * 100)
        print("✅ ANÁLISE COMPLETA QI 500 CONCLUÍDA")
        print("=" * 100)

if __name__ == "__main__":
    analise_completa_qi500()

