import ast
import sys

with open('bot_manager.py', 'r', encoding='utf-8') as f:
    source = f.read()

def count_try_except(node):
    try_count = 0
    except_count = 0
    
    for child in ast.walk(node):
        if isinstance(child, ast.Try):
            try_count += 1
            # Count except handlers
            except_count += len(child.handlers)
    
    return try_count, except_count

try:
    tree = ast.parse(source)
    try_count, except_count = count_try_except(tree)
    print(f'Try blocks: {try_count}')
    print(f'Except handlers: {except_count}')
    if except_count >= try_count:
        print('Balance: OK')
    else:
        print('Balance: UNBALANCED')
except SyntaxError as e:
    print(f'SYNTAX ERROR at line {e.lineno}: {e.text}')
    sys.exit(1)
