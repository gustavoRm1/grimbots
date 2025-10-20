#!/bin/bash
# 🔬 SMOKE TEST - CLOAKER VALIDATION
# Executa testes básicos de validação do cloaker

BASE="https://app.grimbots.online/go/red1"
PARAM_NAME="grim"
CORRECT="testecamu01"
WRONG="badval"
BOT_UA="facebookexternalhit/1.1"
LEGIT_UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

echo "=========================================="
echo "🔬 CLOAKER SMOKE TEST - GrimBots"
echo "=========================================="
echo "Base URL: $BASE"
echo "Param: $PARAM_NAME=$CORRECT"
echo ""

# Função para extrair status code
get_status() {
    local url="$1"
    local ua="${2:-$LEGIT_UA}"
    local output=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}" -A "$ua" "$url" 2>&1)
    echo "$output"
}

echo "================================================"
echo "TEST 1: ✅ Correct Parameter (Expected: 302/200)"
echo "================================================"
echo "Request: $BASE?${PARAM_NAME}=${CORRECT}"
result=$(get_status "$BASE?${PARAM_NAME}=${CORRECT}")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "302" ] || [ "$code" = "200" ]; then
    echo "✅ PASS: Correct parameter accepted"
else
    echo "❌ FAIL: Expected 302/200, got $code"
fi
echo ""

echo "================================================"
echo "TEST 2: ❌ Missing Parameter (Expected: 403)"
echo "================================================"
echo "Request: $BASE"
result=$(get_status "$BASE")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "403" ]; then
    echo "✅ PASS: Missing parameter blocked"
else
    echo "❌ FAIL: Expected 403, got $code"
fi
echo ""

echo "================================================"
echo "TEST 3: ❌ Wrong Parameter (Expected: 403)"
echo "================================================"
echo "Request: $BASE?${PARAM_NAME}=${WRONG}"
result=$(get_status "$BASE?${PARAM_NAME}=${WRONG}")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "403" ]; then
    echo "✅ PASS: Wrong parameter blocked"
else
    echo "❌ FAIL: Expected 403, got $code"
fi
echo ""

echo "================================================"
echo "TEST 4: 🤖 Bot User-Agent (Expected: 403)"
echo "================================================"
echo "Request: $BASE?${PARAM_NAME}=${CORRECT}"
echo "User-Agent: $BOT_UA"
result=$(get_status "$BASE?${PARAM_NAME}=${CORRECT}" "$BOT_UA")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "403" ]; then
    echo "✅ PASS: Bot UA blocked"
else
    echo "⚠️ WARNING: Expected 403, got $code (Bot detection may not be implemented)"
fi
echo ""

echo "================================================"
echo "TEST 5: ✅ Legit User-Agent (Expected: 302/200)"
echo "================================================"
echo "Request: $BASE?${PARAM_NAME}=${CORRECT}"
echo "User-Agent: $LEGIT_UA"
result=$(get_status "$BASE?${PARAM_NAME}=${CORRECT}" "$LEGIT_UA")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "302" ] || [ "$code" = "200" ]; then
    echo "✅ PASS: Legit UA accepted"
else
    echo "❌ FAIL: Expected 302/200, got $code"
fi
echo ""

echo "================================================"
echo "TEST 6: 🔤 Encoded Parameter with Spaces"
echo "================================================"
echo "Request: $BASE?${PARAM_NAME}=%20${CORRECT}%20"
result=$(get_status "$BASE?${PARAM_NAME}=%20${CORRECT}%20")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "302" ] || [ "$code" = "200" ]; then
    echo "✅ PASS: Encoded param with spaces accepted (strip working)"
else
    echo "⚠️ WARNING: Expected 302/200, got $code (Strip may not be working)"
fi
echo ""

echo "================================================"
echo "TEST 7: 🔢 Very Long Parameter (1024 chars)"
echo "================================================"
long_param=$(python3 -c "print('a' * 1024)")
result=$(get_status "$BASE?${PARAM_NAME}=${long_param}")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "403" ] || [ "$code" = "400" ] || [ "$code" = "414" ]; then
    echo "✅ PASS: Long parameter handled gracefully"
else
    echo "❌ FAIL: Unexpected response $code (potential DoS vector)"
fi
echo ""

echo "================================================"
echo "TEST 8: 💉 SQL Injection-esque Payload"
echo "================================================"
sql_payload="' OR '1'='1"
result=$(get_status "$BASE?${PARAM_NAME}=${sql_payload}")
code=$(echo $result | cut -d'|' -f1)
time=$(echo $result | cut -d'|' -f2)
echo "Status Code: $code"
echo "Response Time: ${time}s"
if [ "$code" = "403" ]; then
    echo "✅ PASS: SQL injection payload blocked"
else
    echo "⚠️ WARNING: Unexpected response $code (review input sanitization)"
fi
echo ""

echo "================================================"
echo "📊 SMOKE TEST SUMMARY"
echo "================================================"
echo "Test suite completed at $(date)"
echo "Review results above for PASS/FAIL status"
echo "Expected pass rate: 100% (all tests)"
echo ""
echo "Next steps:"
echo "1. Run pytest: python -m pytest tests/test_cloaker.py -v"
echo "2. Run load test: locust -f load_test/locustfile.py"
echo "3. Review server logs for detailed request data"
echo "================================================"

