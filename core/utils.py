import re
from typing import Tuple, Optional


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    패스워드 유효성을 검사합니다.

    규칙:
    - 20자리 이하
    - 최소 1개의 영어 대문자 포함
    - 최소 1개의 특수문자 포함
    - 최소 1개의 숫자 포함

    Args:
        password: 검사할 패스워드

    Returns:
        Tuple[bool, Optional[str]]: (유효성 여부, 오류 메시지)
    """
    # 길이 검사
    if len(password) > 20:
        return False, "패스워드는 20자리 이하여야 합니다."

    # 각 조건 검사
    has_uppercase = bool(re.search(r'[A-Z]', password))
    has_special_char = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>/?]', password))
    has_digit = bool(re.search(r'\d', password))

    # 모든 조건을 만족하는지 확인
    if not has_uppercase:
        return False, "패스워드는 최소 하나의 영어 대문자를 포함해야 합니다."

    if not has_special_char:
        return False, "패스워드는 최소 하나의 특수문자를 포함해야 합니다."

    if not has_digit:
        return False, "패스워드는 최소 하나의 숫자를 포함해야 합니다."

    return True, None