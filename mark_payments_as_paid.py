"""
Marca pagamentos pendentes como pagos (APENAS PARA TESTE)
USO: python mark_payments_as_paid.py <quantidade>
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import sys

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'

def mark_as_paid(quantity=None):
    """Marca pagamentos como pagos"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Contar pending
    cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    total_pending = cursor.fetchone()[0]
    
    print(f"Total de pagamentos pendentes: {total_pending}")
    
    if total_pending == 0:
        print("   Nenhum pagamento pendente!")
        conn.close()
        return
    
    # Definir quantidade
    if quantity is None:
        print(f"\nQuantos deseja marcar como PAGO? (1-{total_pending}) ou 'todos':")
        response = input().strip()
        
        if response.lower() == 'todos':
            quantity = total_pending
        else:
            try:
                quantity = int(response)
            except:
                print("   Quantidade invalida!")
                conn.close()
                return
    
    if quantity > total_pending:
        quantity = total_pending
    
    print(f"\n   Marcando {quantity} pagamento(s) como PAGO...")
    
    # Buscar IDs
    cursor.execute(f"SELECT id FROM payments WHERE status = 'pending' ORDER BY id DESC LIMIT {quantity}")
    payment_ids = [row[0] for row in cursor.fetchall()]
    
    now = datetime.now().isoformat()
    
    # Atualizar status
    for payment_id in payment_ids:
        cursor.execute("""
            UPDATE payments 
            SET status = 'paid', paid_at = ? 
            WHERE id = ?
        """, (now, payment_id))
        print(f"      Pagamento #{payment_id} -> PAID")
    
    conn.commit()
    conn.close()
    
    print(f"\n   {quantity} pagamento(s) marcado(s) como PAGO!")
    print("\n   IMPORTANTE: Execute 'python check_achievements_all_users.py' para desbloquear conquistas!")

if __name__ == '__main__':
    # Aceitar quantidade via argumento
    qty = int(sys.argv[1]) if len(sys.argv) > 1 else None
    mark_as_paid(qty)

