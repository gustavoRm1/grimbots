#!/usr/bin/env python3
"""
Script para corrigir verify_credentials do UmbrellaPag
Aplica correção diretamente no arquivo gateway_umbrellapag.py
"""

import re
import sys

def fix_verify_credentials(file_path):
    """Aplica correção no método verify_credentials"""
    try:
        # Ler arquivo
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se já tem a correção
        if 'status_code = response.status_code' in content and 'SIMPLIFICADO' in content:
            print("✅ Correção já aplicada!")
            return True
        
        # Padrão para encontrar o método verify_credentials
        # Buscar a linha que verifica o status_code
        pattern = r'(def verify_credentials\(self\) -> bool:.*?)(if response\.status_code in \[200, 201\]:.*?return True|elif response\.status_code in \[401, 403\]:)'
        
        # Verificar se o arquivo tem o método
        if 'def verify_credentials(self) -> bool:' not in content:
            print("❌ Método verify_credentials não encontrado!")
            return False
        
        # Substituir o método inteiro pela versão corrigida
        new_method = '''    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas
        Tenta fazer uma requisição simples à API para buscar dados da empresa
        """
        try:
            # Tentar buscar dados da empresa (endpoint mais simples e confiável)
            # Se conseguir buscar dados, as credenciais são válidas
            response = self._make_request('GET', '/user/sellers')
            
            # Verificar resposta
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais (sem resposta)")
                return False
            
            status_code = response.status_code
            logger.debug(f"🔍 [{self.get_gateway_name()}] Status da resposta: {status_code}")
            
            # Status 200 ou 201 = sucesso (credenciais válidas) - SIMPLIFICADO
            if status_code in [200, 201]:
                logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (status {status_code})")
                # Tentar parsear resposta para log detalhado
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        message = response_data.get('message', '')
                        logger.debug(f"   Mensagem: {message}")
                        if 'data' in response_data:
                            logger.debug(f"   Dados encontrados: {list(response_data.get('data', {}).keys())}")
                except:
                    pass
                return True
            
            # Status 401 ou 403 = credenciais inválidas
            elif status_code in [401, 403]:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (status {status_code})")
                if response.text:
                    logger.error(f"   Resposta: {response.text[:200]}")
                return False
            
            # Outros status = verificar mensagem de sucesso na resposta
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status inesperado {status_code}")
                # Verificar se a resposta indica sucesso mesmo com status diferente
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        message = response_data.get('message', '').lower()
                        # Se tiver mensagem de sucesso ou dados válidos, considerar válido
                        if 'sucesso' in message or 'encontrada' in message or 'data' in response_data:
                            logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (mensagem de sucesso, status {status_code})")
                            return True
                except Exception as e:
                    logger.debug(f"   Erro ao parsear resposta: {e}")
                
                # Se não conseguir verificar, considerar credenciais inválidas
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (status {status_code} não reconhecido)")
                if response.text:
                    logger.error(f"   Resposta: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return False
'''
        
        # Encontrar e substituir o método
        pattern = r'(    def verify_credentials\(self\) -> bool:.*?)(    def _create_product)'
        
        replacement = new_method + r'\n    \2'
        
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        if new_content == content:
            print("❌ Não foi possível aplicar a correção!")
            print("   Tentando método alternativo...")
            
            # Método alternativo: substituir apenas a parte problemática
            # Encontrar a linha que verifica status_code
            lines = content.split('\n')
            new_lines = []
            i = 0
            in_method = False
            method_start = -1
            
            while i < len(lines):
                line = lines[i]
                
                # Encontrar início do método
                if 'def verify_credentials(self) -> bool:' in line:
                    in_method = True
                    method_start = i
                    new_lines.append(line)
                    i += 1
                    continue
                
                # Se estamos no método, encontrar a parte problemática
                if in_method:
                    # Procurar pela verificação de status_code antiga
                    if 'if response.status_code in [200, 201]:' in line:
                        # Substituir pela versão simplificada
                        new_lines.append('            status_code = response.status_code')
                        new_lines.append('            logger.debug(f"🔍 [{self.get_gateway_name()}] Status da resposta: {status_code}")')
                        new_lines.append('')
                        new_lines.append('            # Status 200 ou 201 = sucesso (credenciais válidas) - SIMPLIFICADO')
                        new_lines.append('            if status_code in [200, 201]:')
                        new_lines.append('                logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (status {status_code})")')
                        new_lines.append('                # Tentar parsear resposta para log detalhado')
                        new_lines.append('                try:')
                        new_lines.append('                    response_data = response.json()')
                        new_lines.append('                    if isinstance(response_data, dict):')
                        new_lines.append('                        message = response_data.get(\'message\', \'\')')
                        new_lines.append('                        logger.debug(f"   Mensagem: {message}")')
                        new_lines.append('                        if \'data\' in response_data:')
                        new_lines.append('                            logger.debug(f"   Dados encontrados: {list(response_data.get(\'data\', {}).keys())}")')
                        new_lines.append('                except:')
                        new_lines.append('                    pass')
                        new_lines.append('                return True')
                        new_lines.append('')
                        # Pular as linhas antigas até encontrar o próximo elif ou else
                        i += 1
                        while i < len(lines) and not (lines[i].strip().startswith('elif') or lines[i].strip().startswith('else') or lines[i].strip().startswith('def ')):
                            i += 1
                        continue
                    
                    # Se encontrarmos o próximo método, sair
                    if line.strip().startswith('def ') and 'verify_credentials' not in line:
                        in_method = False
                    
                    new_lines.append(line)
                else:
                    new_lines.append(line)
                
                i += 1
            
            new_content = '\n'.join(new_lines)
        
        # Salvar arquivo
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Correção aplicada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao aplicar correção: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    file_path = 'gateway_umbrellapag.py'
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    print(f"🔧 Aplicando correção em {file_path}...")
    if fix_verify_credentials(file_path):
        print("✅ Correção aplicada! Reinicie a aplicação para aplicar as mudanças.")
    else:
        print("❌ Falha ao aplicar correção!")
        sys.exit(1)

