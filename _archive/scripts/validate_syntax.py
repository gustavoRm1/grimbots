import ast
import sys

files_to_check = [
    'internal_logic/core/models.py',
    'internal_logic/blueprints/bots/routes_rewritten.py',
    'internal_logic/blueprints/api/routes.py'
]

all_ok = True

for filepath in files_to_check:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        print(f'✅ {filepath} - SINTAXE OK')
    except SyntaxError as e:
        print(f'❌ {filepath} - SYNTAX ERROR at line {e.lineno}: {e.text}')
        all_ok = False
    except Exception as e:
        print(f'❌ {filepath} - ERROR: {e}')
        all_ok = False

if all_ok:
    print('\n🎉 TODOS OS ARQUIVOS VALIDADOS COM SUCESSO!')
    sys.exit(0)
else:
    print('\n⚠️  HÁ ERROS DE SINTAXE!')
    sys.exit(1)
