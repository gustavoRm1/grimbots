#!/usr/bin/env python3
"""
🧪 PYTEST - CLOAKER COMPREHENSIVE TEST SUITE
Testes automatizados para validação completa do sistema Cloaker

Cobertura:
- Validação de parâmetros (correto, ausente, incorreto)
- Detecção de bots via User-Agent
- Encoding e sanitização
- Edge cases (long strings, special chars)
- Performance (latency)
- Logs estruturados
"""

import requests
import pytest
import time
import json
from typing import Tuple, Optional

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================
BASE_URL = "https://app.grimbots.online"
TEST_SLUG = "red1"  # Pool real com cloaker ativo
PARAM_NAME = "grim"
CORRECT_VALUE = "escalafull"  # Valor real do cloaker
WRONG_VALUE = "wrongvalue"
TIMEOUT = 10

# User-Agents
BOT_USER_AGENTS = [
    "facebookexternalhit/1.1",
    "Twitterbot/1.0",
    "LinkedInBot/1.0",
    "Googlebot/2.1",
    "python-requests/2.28.1",
    "curl/7.68.0",
    "wget/1.20.3"
]

LEGIT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
]

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def base_url():
    """Base URL do sistema"""
    return f"{BASE_URL}/go/{TEST_SLUG}"

@pytest.fixture
def session():
    """Session HTTP com timeout"""
    s = requests.Session()
    s.timeout = TIMEOUT
    return s

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def make_request(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    session: Optional[requests.Session] = None
) -> Tuple[int, dict, str, float]:
    """
    Faz requisição e retorna (status_code, headers, text, latency_ms)
    """
    start = time.time()
    
    if session is None:
        session = requests.Session()
    
    try:
        response = session.get(
            url,
            params=params,
            headers=headers,
            allow_redirects=False,
            timeout=TIMEOUT
        )
        latency = (time.time() - start) * 1000
        
        return (
            response.status_code,
            dict(response.headers),
            response.text,
            latency
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return (0, {}, str(e), latency)

# ============================================================================
# TESTES DE VALIDAÇÃO DE PARÂMETROS
# ============================================================================

class TestParameterValidation:
    """Testes de validação de parâmetros"""
    
    def test_correct_parameter_returns_redirect(self, base_url, session):
        """✅ Parâmetro correto deve retornar 302/200"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: CORRECT_VALUE},
            session=session
        )
        
        assert code in [200, 302], \
            f"Expected 200/302 for correct param, got {code}"
        
        # Verificar latência
        assert latency < 1000, \
            f"Latency too high: {latency}ms (expected < 1000ms)"
    
    def test_missing_parameter_returns_403(self, base_url, session):
        """❌ Parâmetro ausente deve retornar 403"""
        code, headers, text, latency = make_request(
            base_url,
            params=None,
            session=session
        )
        
        assert code == 403, \
            f"Expected 403 for missing param, got {code}"
        
        # Verificar página de bloqueio
        assert "Acesso Restrito" in text or "403" in text, \
            "Block page should contain 'Acesso Restrito' or '403'"
    
    def test_wrong_parameter_returns_403(self, base_url, session):
        """❌ Parâmetro incorreto deve retornar 403"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: WRONG_VALUE},
            session=session
        )
        
        assert code == 403, \
            f"Expected 403 for wrong param, got {code}"
    
    def test_empty_parameter_returns_403(self, base_url, session):
        """❌ Parâmetro vazio deve retornar 403"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: ""},
            session=session
        )
        
        assert code == 403, \
            f"Expected 403 for empty param, got {code}"
    
    def test_parameter_with_spaces_stripped(self, base_url, session):
        """✅ Parâmetro com espaços deve ser aceito (strip)"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: f" {CORRECT_VALUE} "},
            session=session
        )
        
        assert code in [200, 302], \
            f"Expected 200/302 for param with spaces (strip), got {code}"
    
    def test_case_sensitive_parameter(self, base_url, session):
        """🔤 Parâmetro é case-sensitive"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: CORRECT_VALUE.upper()},
            session=session
        )
        
        assert code == 403, \
            f"Expected 403 for case-different param, got {code}"

# ============================================================================
# TESTES DE DETECÇÃO DE BOTS
# ============================================================================

class TestBotDetection:
    """Testes de detecção de bots via User-Agent"""
    
    @pytest.mark.parametrize("bot_ua", BOT_USER_AGENTS)
    def test_bot_user_agents_blocked(self, base_url, session, bot_ua):
        """🤖 Bots conhecidos devem ser bloqueados"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: CORRECT_VALUE},
            headers={"User-Agent": bot_ua},
            session=session
        )
        
        # NOTA: Se o sistema NÃO implementa bot detection,
        # este teste FALHARÁ e indicará necessidade de implementação
        assert code == 403, \
            f"Expected 403 for bot UA '{bot_ua}', got {code} " \
            f"(BOT DETECTION NOT IMPLEMENTED)"
    
    @pytest.mark.parametrize("legit_ua", LEGIT_USER_AGENTS)
    def test_legit_user_agents_allowed(self, base_url, session, legit_ua):
        """✅ User-Agents legítimos devem ser permitidos"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: CORRECT_VALUE},
            headers={"User-Agent": legit_ua},
            session=session
        )
        
        assert code in [200, 302], \
            f"Expected 200/302 for legit UA, got {code}"

# ============================================================================
# TESTES DE EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Testes de casos extremos"""
    
    def test_very_long_parameter(self, base_url, session):
        """🔢 Parâmetro muito longo não deve causar crash"""
        long_value = "a" * 1024
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: long_value},
            session=session
        )
        
        # Deve retornar erro, não crash
        assert code in [400, 403, 414], \
            f"Expected 400/403/414 for long param, got {code}"
    
    def test_special_characters_in_parameter(self, base_url, session):
        """🔣 Caracteres especiais devem ser tratados"""
        special_chars = [
            "' OR '1'='1",  # SQL injection
            "<script>alert(1)</script>",  # XSS
            "../../../etc/passwd",  # Path traversal
            "%00",  # Null byte
            "\x00\x01\x02"  # Binary data
        ]
        
        for char_set in special_chars:
            code, headers, text, latency = make_request(
                base_url,
                params={PARAM_NAME: char_set},
                session=session
            )
            
            # Deve bloquear ou tratar gracefully
            assert code in [403, 400], \
                f"Expected 403/400 for special chars '{char_set}', got {code}"
    
    def test_multiple_parameters_same_name(self, base_url, session):
        """🔄 Múltiplos parâmetros com mesmo nome"""
        # Construir URL manualmente
        url_with_multiple = f"{base_url}?{PARAM_NAME}={CORRECT_VALUE}&{PARAM_NAME}={WRONG_VALUE}"
        
        code, headers, text, latency = make_request(
            url_with_multiple,
            session=session
        )
        
        # Sistema deve lidar gracefully
        assert code in [200, 302, 403], \
            f"Expected valid response for multiple params, got {code}"
    
    def test_url_encoded_parameter(self, base_url, session):
        """🔤 Parâmetro URL-encoded deve funcionar"""
        import urllib.parse
        encoded_value = urllib.parse.quote(CORRECT_VALUE)
        
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: encoded_value},
            session=session
        )
        
        # Deve funcionar normalmente
        assert code in [200, 302], \
            f"Expected 200/302 for URL-encoded param, got {code}"

# ============================================================================
# TESTES DE PERFORMANCE
# ============================================================================

class TestPerformance:
    """Testes de performance e latência"""
    
    def test_latency_under_100ms_p95(self, base_url, session):
        """⏱️ Latência p95 deve ser < 100ms"""
        latencies = []
        
        # Fazer 100 requests
        for _ in range(100):
            code, headers, text, latency = make_request(
                base_url,
                params={PARAM_NAME: CORRECT_VALUE},
                session=session
            )
            latencies.append(latency)
        
        # Calcular p95
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        
        assert p95 < 100, \
            f"P95 latency is {p95}ms (expected < 100ms)"
    
    def test_concurrent_requests(self, base_url):
        """🔄 Requests concorrentes devem ser tratados"""
        import concurrent.futures
        
        def make_test_request():
            code, headers, text, latency = make_request(
                base_url,
                params={PARAM_NAME: CORRECT_VALUE}
            )
            return code
        
        # 10 requests concorrentes
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_test_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # Todos devem retornar 200/302
        assert all(code in [200, 302] for code in results), \
            f"Some concurrent requests failed: {results}"

# ============================================================================
# TESTES DE SEGURANÇA
# ============================================================================

class TestSecurity:
    """Testes de segurança"""
    
    def test_no_sensitive_data_in_error_page(self, base_url, session):
        """🔒 Página de erro não deve expor dados sensíveis"""
        code, headers, text, latency = make_request(
            base_url,
            params={PARAM_NAME: WRONG_VALUE},
            session=session
        )
        
        # Verificar se não expõe informações sensíveis
        sensitive_keywords = [
            "password",
            "secret",
            "token",
            "api_key",
            "database",
            "stacktrace",
            "traceback"
        ]
        
        text_lower = text.lower()
        for keyword in sensitive_keywords:
            assert keyword not in text_lower, \
                f"Error page exposes sensitive data: '{keyword}'"
    
    def test_no_sql_injection(self, base_url, session):
        """💉 Sistema deve ser resistente a SQL injection"""
        sql_payloads = [
            "' OR '1'='1",
            "1'; DROP TABLE users--",
            "1' UNION SELECT * FROM users--"
        ]
        
        for payload in sql_payloads:
            code, headers, text, latency = make_request(
                base_url,
                params={PARAM_NAME: payload},
                session=session
            )
            
            # Não deve retornar 500 (erro de servidor)
            assert code != 500, \
                f"SQL injection payload caused server error: {payload}"
    
    def test_proper_http_status_codes(self, base_url, session):
        """📊 Status codes HTTP devem ser apropriados"""
        test_cases = [
            ({PARAM_NAME: CORRECT_VALUE}, [200, 302]),  # Correto
            ({}, [403]),  # Ausente
            ({PARAM_NAME: WRONG_VALUE}, [403]),  # Incorreto
        ]
        
        for params, expected_codes in test_cases:
            code, headers, text, latency = make_request(
                base_url,
                params=params if params else None,
                session=session
            )
            
            assert code in expected_codes, \
                f"Expected {expected_codes}, got {code} for params {params}"

# ============================================================================
# RELATÓRIO FINAL
# ============================================================================

def pytest_sessionfinish(session, exitstatus):
    """Hook executado após todos os testes"""
    print("\n" + "=" * 60)
    print("📊 CLOAKER TEST SUITE - FINAL REPORT")
    print("=" * 60)
    print(f"Exit Status: {exitstatus}")
    print("=" * 60)

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

