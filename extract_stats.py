import re

# Read the file with error handling
try:
    with open('old_app_before_refactor.py', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Find the get_bot_stats function
    pattern = r'@app\.route\([\'\"]\/api\/bots\/<int:bot_id>\/stats[\'\"].*?def get_bot_stats\(bot_id\):.*?(?=@app\.route|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        print('=== FUNCTION get_bot_stats FOUND ===')
        print(match.group(0))
    else:
        print('Function not found with pattern, trying alternative...')
        
        # Try to find by line numbers using grep results
        lines = content.split('\n')
        
        # Find the line with get_bot_stats
        for i, line in enumerate(lines):
            if 'def get_bot_stats(bot_id):' in line:
                print(f'Found get_bot_stats at line {i+1}')
                
                # Extract function (next ~200 lines or until next @app.route)
                func_lines = []
                for j in range(i, min(i+200, len(lines))):
                    func_lines.append(lines[j])
                    if j > i and lines[j].strip().startswith('@app.route'):
                        break
                
                print('\n=== FUNCTION get_bot_stats ===')
                print('\n'.join(func_lines))
                break
        else:
            print('get_bot_stats function not found')
            
except Exception as e:
    print('Error reading file:', e)
