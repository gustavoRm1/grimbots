/**
 * PM2 Ecosystem Configuration
 * Bot Manager SaaS - Produção
 * 
 * Este arquivo configura o PM2 para gerenciar o processo Python/Gunicorn
 * com WebSocket (eventlet) e APScheduler
 */

module.exports = {
  apps: [{
    name: 'bot-manager',
    
    // Script de entrada
    script: 'gunicorn',
    
    // Argumentos do Gunicorn
    args: [
      '--worker-class', 'eventlet',           // Worker para WebSocket
      '--workers', '1',                        // 1 worker (eventlet não suporta múltiplos workers com state compartilhado)
      '--bind', '127.0.0.1:5000',             // Bind local (Nginx Proxy Manager faz proxy)
      '--timeout', '120',                      // Timeout de 120s para requisições longas
      '--keep-alive', '5',                     // Keep-alive para conexões
      '--log-level', 'info',                   // Nível de log
      '--access-logfile', 'logs/access.log',   // Log de acesso
      '--error-logfile', 'logs/error.log',     // Log de erros
      'wsgi:app'                               // Entry point (wsgi.py:app)
    ],
    
    // Interpreter
    interpreter: 'python3',                    // Ou caminho completo: /usr/bin/python3.11
    
    // Diretório de trabalho
    cwd: '/var/www/bot-manager',              // Ajustar para seu caminho
    
    // Variáveis de ambiente (sobrescreve .env)
    env: {
      FLASK_ENV: 'production',
      PYTHONUNBUFFERED: '1',                   // Output imediato (sem buffer)
      LANG: 'C.UTF-8',                         // Encoding UTF-8
      LC_ALL: 'C.UTF-8'
    },
    
    // Reiniciar se usar mais de 500MB
    max_memory_restart: '500M',
    
    // Tentar reiniciar no máximo 10 vezes
    max_restarts: 10,
    
    // Esperar 5 segundos entre reinícios
    min_uptime: '5s',
    
    // Delay entre restarts em caso de falha
    restart_delay: 4000,
    
    // Auto restart se crashar
    autorestart: true,
    
    // Assistir arquivos (desabilitar em produção para performance)
    watch: false,
    
    // Ignorar mudanças nestes arquivos (se watch: true)
    ignore_watch: [
      'node_modules',
      'logs',
      'instance',
      '*.log',
      '*.db'
    ],
    
    // Logs
    output: 'logs/pm2-out.log',
    error: 'logs/pm2-error.log',
    log: 'logs/pm2-combined.log',
    
    // Formato de timestamp nos logs
    time: true,
    
    // Mesclar logs (todos em um arquivo)
    merge_logs: true,
    
    // Rotação de logs (integração com pm2-logrotate)
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    
    // Modo cluster (NÃO usar com eventlet + APScheduler)
    instances: 1,
    exec_mode: 'fork',
    
    // Kill timeout (tempo para processo encerrar gracefully)
    kill_timeout: 5000,
    
    // Delay para considerar app como "online"
    listen_timeout: 10000,
    
    // Graceful shutdown
    shutdown_with_message: true
  }]
};

