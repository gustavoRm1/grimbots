#!/usr/bin/env python3
import argparse
import os
import sys
import shutil
from pathlib import Path


RUNTIME_KEEP_DIRS = {
    # App runtime
    'templates',
    'static',
    'utils',
    'tasks',
    'migrations',  # manter se forem necessárias em futuras migrações
    'instance',
}

RUNTIME_KEEP_FILES = {
    # Entradas de aplicação
    'app.py',
    'wsgi.py',
    'models.py',
    'celery_app.py',
    'gunicorn_config.py',
    'requirements.txt',
    # Gateways e integrações
    'gateway_interface.py',
    'gateway_factory.py',
    'gateway_paradise.py',
    'gateway_pushyn.py',
    'gateway_syncpay.py',
    'gateway_wiinpay.py',
    # Arquivos de config/credenciais que o deploy usa
    'paradise.json',
}

# Diretórios/arquivos tipicamente não essenciais para runtime em produção
PURGE_DIRS = [
    'archive',
    'artifacts',
    'backups',
    'docs',
    'load_test',
    'patches',
    'tests',
]

# Padrões de arquivos a considerar para remoção (fora da allowlist)
PURGE_FILE_EXTENSIONS = {
    '.md',  # documentação
    '.log', # logs antigos no workspace
}

OPTIONAL_PURGE_FILES = {
    # Candidatos comuns que não são necessários para execução,
    # mas podem ser úteis no operacional. Avaliar antes de aplicar.
    'DEPLOY_*.md',
    'README.md',
    'ARCHIVE_INDEX.md',
}


def is_within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def human_size(num: int) -> str:
    for unit in ['B','KB','MB','GB','TB']:
        if num < 1024.0:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}PB"


def dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob('*'):
        if p.is_file():
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return total


def collect_candidates(repo_root: Path):
    candidates = []

    # Diretórios inteiros
    for d in PURGE_DIRS:
        p = repo_root / d
        if p.exists() and p.is_dir():
            size = dir_size(p)
            candidates.append({
                'type': 'dir',
                'path': str(p),
                'size': size,
            })

    # Arquivos por extensão
    for ext in PURGE_FILE_EXTENSIONS:
        for p in repo_root.rglob(f'*{ext}'):
            # manter arquivos explicitamente na allowlist
            if p.name in RUNTIME_KEEP_FILES:
                continue
            # pular dentro de diretórios de runtime
            if any(part in RUNTIME_KEEP_DIRS for part in p.parts):
                # documentação dentro de static/templates raramente é crítica, mas seja conservador
                continue
            size = 0
            try:
                size = p.stat().st_size
            except Exception:
                pass
            candidates.append({
                'type': 'file',
                'path': str(p),
                'size': size,
            })

    return sorted(candidates, key=lambda x: x['size'], reverse=True)


def delete_path(path: Path):
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink(missing_ok=True)
        except TypeError:
            # Python < 3.8 compat
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description='Limpeza segura de arquivos não essenciais na VPS (dry-run por padrão).')
    parser.add_argument('--apply', action='store_true', help='Aplica as remoções (sem isso, apenas simula).')
    parser.add_argument('--confirm', action='store_true', help='Confirma remoção sem perguntar (modo não interativo).')
    parser.add_argument('--min-size-mb', type=int, default=0, help='Remover apenas itens com tamanho >= X MB.')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)

    print('=' * 80)
    print('🔍 INVENTÁRIO DE CANDIDATOS À LIMPEZA (dry-run por padrão)')
    print('=' * 80)

    candidates = collect_candidates(repo_root)
    if args.min_size_mb > 0:
        threshold = args.min_size_mb * 1024 * 1024
        candidates = [c for c in candidates if c['size'] >= threshold]

    total = sum(c['size'] for c in candidates)
    for c in candidates:
        print(f"{c['type']:>4}  {human_size(c['size']):>8}  {c['path']}")

    print('-' * 80)
    print(f'Total estimado: {human_size(total)} em {len(candidates)} itens')

    if not args.apply:
        print('\n💡 Execute com --apply para remover. Use --min-size-mb para filtrar.\n')
        return 0

    if not args.confirm:
        ans = input('Tem certeza que deseja REMOVER os itens listados? (yes/NO): ').strip().lower()
        if ans != 'yes':
            print('Operação cancelada.')
            return 1

    removed = 0
    freed = 0
    for c in candidates:
        p = Path(c['path'])
        try:
            delete_path(p)
            removed += 1
            freed += c['size']
        except Exception as e:
            print(f"⚠️ Falha ao remover {p}: {e}")

    print('-' * 80)
    print(f'✅ Removidos: {removed} itens | Espaço liberado: {human_size(freed)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())


