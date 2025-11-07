#!/bin/bash
# Script para corrigir DNS e conectividade com Telegram

echo "=========================================="
echo "  CORRIGIR DNS - TELEGRAM"
echo "=========================================="
echo ""

# 1. Testar DNS atual
echo "🔍 Testando DNS atual..."
if nslookup api.telegram.org > /dev/null 2>&1; then
    echo "✅ DNS funcionando"
    nslookup api.telegram.org
else
    echo "❌ DNS NÃO está resolvendo api.telegram.org"
    
    # Configurar DNS do Google
    echo ""
    echo "🔧 Configurando DNS do Google..."
    
    # Backup resolv.conf
    sudo cp /etc/resolv.conf /etc/resolv.conf.backup
    
    # Adicionar DNS do Google
    echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
    echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf > /dev/null
    echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf > /dev/null
    
    echo "✅ DNS configurado"
    
    # Testar novamente
    echo ""
    echo "🔍 Testando DNS novamente..."
    if nslookup api.telegram.org; then
        echo "✅ DNS agora está funcionando"
    else
        echo "❌ DNS ainda não funciona - verificar configuração de rede"
    fi
fi

# 2. Testar conectividade
echo ""
echo "🌐 Testando conectividade com Telegram..."
if ping -c 3 api.telegram.org > /dev/null 2>&1; then
    echo "✅ Ping para api.telegram.org OK"
else
    echo "⚠️  Ping falhou - pode ser firewall"
fi

# 3. Testar HTTPS
echo ""
echo "🔐 Testando HTTPS com Telegram..."
if curl -s --max-time 5 https://api.telegram.org > /dev/null 2>&1; then
    echo "✅ HTTPS para api.telegram.org OK"
else
    echo "❌ HTTPS falhou - verificar firewall/proxy"
fi

# 4. Resumo
echo ""
echo "=========================================="
echo "  RESUMO"
echo "=========================================="
echo ""
echo "Testes:"
echo "  DNS: $(nslookup api.telegram.org > /dev/null 2>&1 && echo '✅ OK' || echo '❌ FALHOU')"
echo "  Ping: $(ping -c 1 api.telegram.org > /dev/null 2>&1 && echo '✅ OK' || echo '⚠️  FALHOU')"
echo "  HTTPS: $(curl -s --max-time 5 https://api.telegram.org > /dev/null 2>&1 && echo '✅ OK' || echo '❌ FALHOU')"
echo ""
echo "Se todos os testes passaram, o problema de DNS está resolvido."
echo "Se HTTPS ainda falha, verifique firewall/proxy."
echo ""

