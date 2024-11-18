import os
from cryptography.fernet import Fernet


# TODO: Fernet Is Not Deterministic So It Will Not Work
fernet = Fernet(os.environ['FERNET_KEY'])


async def encrypt_id(id: int) -> str:
    # return fernet.encrypt(bytes(str(id), 'utf-8')).decode('utf-8')
    return str(id)


async def decrypt_id(token: str) -> int:
    # return int(fernet.decrypt(token))
    return int(token)
