"""
Comandos CLI do Flask - Administração do Sistema
===============================================

Comandos para gerenciamento de webhooks, sincronização e manutenção.
"""

import click
from flask.cli import with_appcontext


@click.command('sync-webhooks')
@with_appcontext
def sync_webhooks_command():
    """
    Enfileira a sincronização de todos os webhooks no RQ Worker.
    
    Garante que todos os bots estejam sempre online recebendo webhooks.
    
    Uso:
        flask sync-webhooks
    
    O comando enfileira a tarefa no RQ - o processamento real
    acontece no worker em background, sem bloquear o servidor.
    """
    from tasks_async import task_queue
    from internal_logic.tasks.telegram_tasks import task_sync_all_webhooks
    
    try:
        if not task_queue:
            click.echo("❌ ERRO: Fila RQ não está disponível. Verifique a conexão com Redis.")
            return
        
        # Enfileirar tarefa de sincronização em massa
        job = task_queue.enqueue(task_sync_all_webhooks)
        
        click.echo("✅ Tarefa de sincronização em massa enviada para o RQ Worker!")
        click.echo(f"   Job ID: {job.id}")
        click.echo(f"   Fila: tasks")
        click.echo(f"   Status: {job.get_status()}")
        click.echo("")
        click.echo("Para acompanhar o progresso, verifique os logs do worker:")
        click.echo("   python start_rq_worker.py tasks")
        
    except Exception as e:
        click.echo(f"❌ ERRO ao enfileirar tarefa: {e}")
        import traceback
        click.echo(traceback.format_exc())


@click.command('sync-webhook')
@click.argument('bot_id', type=int)
@with_appcontext
def sync_single_webhook_command(bot_id):
    """
    Enfileira sincronização de webhook para um bot específico.
    
    Uso:
        flask sync-webhook 123
    
    Args:
        bot_id: ID do bot no banco de dados
    """
    from tasks_async import task_queue
    from internal_logic.tasks.telegram_tasks import task_sync_single_webhook
    
    try:
        if not task_queue:
            click.echo("❌ ERRO: Fila RQ não está disponível.")
            return
        
        job = task_queue.enqueue(task_sync_single_webhook, bot_id)
        
        click.echo(f"✅ Sincronização enfileirada para bot {bot_id}")
        click.echo(f"   Job ID: {job.id}")
        
    except Exception as e:
        click.echo(f"❌ ERRO: {e}")


def register_commands(app):
    """
    Registra todos os comandos CLI na aplicação Flask.
    
    Args:
        app: Instância da aplicação Flask
    """
    app.cli.add_command(sync_webhooks_command)
    app.cli.add_command(sync_single_webhook_command)
    
    # Registrar outros comandos aqui conforme necessário
