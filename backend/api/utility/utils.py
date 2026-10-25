"""
Ce module contient des fonctions utilitaires
- sendSms: Envoi de sms
- sendSocket: Envoi de message via socket
- get_random_string: Génère une chaine de caractère aléatoire
- get_current_date: Retourne la date actuelle
- is_valid_email: Vérifie si l'email est valide
- convert_to_baseX: Conversion de base 10 à base X (X <= 79)
- convert_from_baseX_to_base10: Conversion de base X à base 10 (X <= 79)
"""

from api.services.socket import server


async def sendSocket(event: str, data: dict):
    """
    Envoi de message via socket
    """
    await server.emit(event, {"event": event, "data": data})
    return True


def get_random_string(size: int = 12) -> str:
    """
    Génère une chaine de caractère aléatoire
    """
    import random
    import string

    password = "".join(random.choices(string.ascii_letters + string.digits, k=size))
    return password


def get_current_date() -> str:
    """
    Retourne la date actuelle
    """
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_valid_email(email: str) -> bool:
    """
    Vérifie si l'email est valide
    """
    import re

    pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    return bool(pattern.match(email))


def build_look_up_table() -> tuple[dict[int, str], dict[str, int]]:
    """
    Construit les tables de correspondance pour la conversion de base
    """
    import string

    NUMBERS = tuple(string.digits)
    ALPHABET = tuple(string.ascii_letters)
    SPECIAL = [
        "#",
        "&",
        "%",
        "?",
        "!",
        "-",
        "+",
        "*",
        "=",
        "/",
        ";",
        "(",
        ")",
        ".",
        ",",
        '"',
        "'",
    ]
    TOTAL = [*NUMBERS, *ALPHABET, *SPECIAL]
    LOOK_UP_TABLE_TO_BASE_X = {x: y for x, y in enumerate(TOTAL)}
    LOOK_UP_TABLE_TO_BASE_10 = {y: x for x, y in LOOK_UP_TABLE_TO_BASE_X.items()}
    return LOOK_UP_TABLE_TO_BASE_X, LOOK_UP_TABLE_TO_BASE_10


LOOK_UP_TABLE_TO_BASE_X, LOOK_UP_TABLE_TO_BASE_10 = build_look_up_table()


def convert_to_baseX(number: int, base: int = 79) -> str:
    """
    Conversion de base 10 à base X (X <= 79)
    """
    number = int(number)
    if base > len(LOOK_UP_TABLE_TO_BASE_X) or base < 2:
        raise ValueError(
            f"le base maximale de conversion est :{len(LOOK_UP_TABLE_TO_BASE_X)}"
        )
    BASE = base
    result: str = ""
    while number >= BASE:
        remainder = number % BASE
        number = number // BASE
        result += LOOK_UP_TABLE_TO_BASE_X[remainder]
    result += LOOK_UP_TABLE_TO_BASE_X[number]
    return result[::-1]


def convert_from_baseX_to_base10(number: str, base: int = 79) -> str:
    """
    Conversion de base X à base 10 (X <= 79)
    """
    if base > len(LOOK_UP_TABLE_TO_BASE_10) or base < 2:
        raise ValueError(
            f"le base maximale de conversion est :{len(LOOK_UP_TABLE_TO_BASE_10)}"
        )
    BASE = base
    result = 0
    for index, x in enumerate(number[::-1]):
        result += LOOK_UP_TABLE_TO_BASE_10[x] * int(BASE**index)
    return result


convert_to_baseX(10, 16)
