#!/bin/bash
# Script para validar se o erro de creationTime foi resolvido

export PGPASSWORD=123sefudeu

echo "=========================================="
echo "  VALIDAÇÃO - CORREÇÃO creationTime"
echo "=========================================="
echo ""

echo "1. Verificar último payment criado:"
echo "----------------------------------------"
psql -U grimbots -d grimbots -c "SELECT payment_id, status, created_at, paid_at FROM payments ORDER BY created_at DESC LIMIT 1;"
echo ""

echo "2. Verificar logs do Meta Pixel (últimas 50 linhas):"
echo "----------------------------------------"
echo "Buscando erros de creationTime ou creation_time..."
tail -n 200 logs/celery.log | grep -iE "creationTime|creation_time|invalid|error.*2804019" | tail -20
echo ""

echo "3. Verificar payload enviado para Meta (último Purchase):"
echo "----------------------------------------"
echo "Buscando payload completo do último Purchase..."
tail -n 500 logs/celery.log | grep -A 50 "META PAYLOAD COMPLETO (Purchase)" | tail -60
echo ""

echo "4. Verificar se event_time está em segundos (não milissegundos):"
echo "----------------------------------------"
# Buscar event_time no log e verificar se está em formato de segundos (10 dígitos)
tail -n 500 logs/celery.log | grep -E "event_time|Purchase ENVIADO" | tail -10
echo ""

echo "5. Verificar se fbc está sendo usado corretamente (não gerado sinteticamente):"
echo "----------------------------------------"
echo "Buscando logs sobre fbc..."
tail -n 200 logs/celery.log | grep -E "fbc|Purchase.*fbc" | tail -10
echo ""

echo "6. Verificar resposta do Meta (último Purchase):"
echo "----------------------------------------"
echo "Buscando resposta do Meta..."
tail -n 500 logs/celery.log | grep -A 10 "META RESPONSE (Purchase)" | tail -15
echo ""

echo "7. Verificar se há erros 400/2804019 nos logs:"
echo "----------------------------------------"
tail -n 500 logs/celery.log | grep -E "400|2804019|Invalid parameter|creationTime" | tail -10
echo ""

echo "=========================================="
echo "  VALIDAÇÃO CONCLUÍDA"
echo "=========================================="
echo ""
echo "📋 O que verificar:"
echo "1. ✅ event_time deve ter 10 dígitos (segundos), não 13 (milissegundos)"
echo "2. ✅ Não deve haver 'creation_time' no payload"
echo "3. ✅ Não deve haver erros '2804019' ou 'Invalid parameter' relacionados a creationTime"
echo "4. ✅ fbc deve vir do tracking_data (não gerado sinteticamente)"
echo "5. ✅ Meta deve responder com 'events_received: 1' sem erros"

