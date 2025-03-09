import base64
import logging
import os
import hashlib
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

from core.config import settings

logger = logging.getLogger(__name__)


class CryptoManager:
    """AES-256-CBC 암호화 및 복호화 관리 클래스"""

    def __init__(self):
        # 마스터 키 생성 (환경 변수에서 가져옴)
        master_key = settings.SECRET_KEY.encode() + settings.CRYPTO_SALT.encode()
        self.key = hashlib.sha256(master_key).digest()  # 32바이트 키 생성

    def _encrypt_aes_cbc(self, data: bytes) -> Tuple[bytes, bytes]:
        """AES-256-CBC 암호화 (IV와 암호문 반환)"""
        # 16바이트 IV(초기화 벡터) 생성
        iv = os.urandom(16)

        # PKCS7 패딩 적용
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(data) + padder.finalize()

        # AES-CBC 암호화
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        return iv, ciphertext

    def _decrypt_aes_cbc(self, iv: bytes, ciphertext: bytes) -> bytes:
        """AES-256-CBC 복호화"""
        # AES-CBC 복호화
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        # PKCS7 패딩 제거
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()

    def encrypt(self, plain_text: str) -> Optional[str]:
        """문자열을 AES-256-CBC로 암호화"""
        try:
            if not plain_text:
                return None

            # 바이트로 변환하여 암호화
            iv, ciphertext = self._encrypt_aes_cbc(plain_text.encode())

            # IV와 암호문을 결합하여 하나의 문자열로 인코딩
            combined = iv + ciphertext

            # Base64로 인코딩
            return base64.b64encode(combined).decode()

        except Exception as e:
            logger.error(f"암호화 실패: {e}")
            return None

    def decrypt(self, encrypted_text: Optional[str]) -> Optional[str]:
        """AES-256-CBC로 암호화된 문자열 복호화"""
        try:
            if not encrypted_text:
                return None

            # Base64 디코딩
            combined = base64.b64decode(encrypted_text.encode())

            # IV(16바이트)와 암호문 분리
            iv = combined[:16]
            ciphertext = combined[16:]

            # 복호화 후 문자열로 변환
            decrypted_bytes = self._decrypt_aes_cbc(iv, ciphertext)
            return decrypted_bytes.decode()

        except Exception as e:
            logger.error(f"복호화 실패: {e}")
            return None


# 싱글톤 인스턴스 생성
crypto_manager = CryptoManager()