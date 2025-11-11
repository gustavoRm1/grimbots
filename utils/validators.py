"""
Utilitários de validação.
"""

import re


def cpf_valido(cpf: str) -> bool:
    """
    Valida CPF (11 dígitos) com cálculo dos dígitos verificadores.

    Args:
        cpf: CPF em qualquer formato (serão considerados apenas dígitos).

    Returns:
        True se CPF for válido, False caso contrário.
    """
    if not cpf:
        return False

    cpf_digits = re.sub(r"\D", "", cpf)

    if len(cpf_digits) != 11 or cpf_digits == cpf_digits[0] * 11:
        return False

    def _calc(digs: str) -> int:
        total = sum(int(digs[i]) * (len(digs) + 1 - i) for i in range(len(digs)))
        resto = (total * 10) % 11
        return resto if resto < 10 else 0

    d1 = _calc(cpf_digits[:9])
    d2 = _calc(cpf_digits[:10])

    return cpf_digits[-2:] == f"{d1}{d2}"


__all__ = ["cpf_valido"]

