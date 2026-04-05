"""
Sistema de carregamento seguro de secrets multiline.
Suporta: arquivos externos, Base64, e fallback para env vars diretas.
"""
import os
import base64
from pathlib import Path
from typing import Optional


class SecretsLoader:
    """Loader profissional para secrets multiline compatível com Systemd."""
    
    @staticmethod
    def load_multiline_key(env_var_path: str, env_var_base64: str = None, 
                          env_var_direct: str = None, default: str = None) -> Optional[str]:
        """
        Carrega uma chave multiline seguindo a ordem de prioridade:
        1. Arquivo externo (path no .env)
        2. Base64 encoded (compatível Systemd)
        3. Variável direta (legacy)
        4. Default
        """
        # Prioridade 1: Arquivo externo
        key_path = os.environ.get(env_var_path)
        if key_path:
            path = Path(key_path)
            if path.exists():
                content = path.read_text().strip()
                if content:
                    return content
            else:
                raise FileNotFoundError(
                    f"Arquivo de chave não encontrado: {key_path}\n"
                    f"Configure {env_var_path} apontando para um arquivo existente."
                )
        
        # Prioridade 2: Base64 encoded (Systemd-friendly)
        if env_var_base64:
            b64_content = os.environ.get(env_var_base64)
            if b64_content:
                try:
                    return base64.b64decode(b64_content).decode('utf-8').strip()
                except Exception as e:
                    raise ValueError(f"Base64 inválido em {env_var_base64}: {e}")
        
        # Prioridade 3: Direto (legacy, pode ter problemas multiline)
        if env_var_direct:
            direct = os.environ.get(env_var_direct)
            if direct:
                return direct.strip()
        
        # Prioridade 4: Default
        if default:
            return default
            
        return None
    
    @staticmethod
    def setup_secrets_directory(base_path: str = "/etc/grpay/secrets") -> Path:
        """Cria estrutura de diretório segura para secrets."""
        path = Path(base_path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Permissões restritivas (owner only)
        import stat
        os.chmod(path, stat.S_IRWXU)  # 0o700
        
        return path
    
    @staticmethod
    def save_key_to_file(key_content: str, filename: str, 
                         base_path: str = "/etc/grpay/secrets") -> Path:
        """Salva uma chave em arquivo com permissões seguras."""
        path = Path(base_path) / filename
        path.write_text(key_content.strip())
        
        # Permissões restritivas
        import stat
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        
        return path


def get_vapid_private_key() -> str:
    """Carrega VAPID_PRIVATE_KEY de arquivo ou Base64."""
    key = SecretsLoader.load_multiline_key(
        env_var_path="VAPID_PRIVATE_KEY_PATH",
        env_var_base64="VAPID_PRIVATE_KEY_BASE64",
        env_var_direct="VAPID_PRIVATE_KEY"
    )
    if not key:
        raise ValueError(
            "VAPID_PRIVATE_KEY não configurado. "
            "Use VAPID_PRIVATE_KEY_PATH=/etc/grpay/secrets/vapid_private.pem "
            "ou VAPID_PRIVATE_KEY_BASE64=<base64-encoded>"
        )
    return key


def get_vapid_public_key() -> str:
    """Carrega VAPID_PUBLIC_KEY de arquivo ou Base64."""
    key = SecretsLoader.load_multiline_key(
        env_var_path="VAPID_PUBLIC_KEY_PATH",
        env_var_base64="VAPID_PUBLIC_KEY_BASE64",
        env_var_direct="VAPID_PUBLIC_KEY"
    )
    if not key:
        raise ValueError(
            "VAPID_PUBLIC_KEY não configurado. "
            "Use VAPID_PUBLIC_KEY_PATH=/etc/grpay/secrets/vapid_public.pem "
            "ou VAPID_PUBLIC_KEY_BASE64=<base64-encoded>"
        )
    return key


def get_encryption_key() -> str:
    """Carrega ENCRYPTION_KEY de arquivo ou Base64."""
    key = SecretsLoader.load_multiline_key(
        env_var_path="ENCRYPTION_KEY_PATH",
        env_var_base64="ENCRYPTION_KEY_BASE64",
        env_var_direct="ENCRYPTION_KEY"
    )
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY não configurado. "
            "Use ENCRYPTION_KEY_PATH=/etc/grpay/secrets/master.key "
            "ou ENCRYPTION_KEY_BASE64=<base64-encoded>"
        )
    return key
