import bcrypt


class PasswordHasher:
    def verify(self, raw_password: str, hashed_password: bytes) -> bool:
        return bcrypt.checkpw(raw_password.encode(), hashed_password)

    def hash(self, raw_password: str) -> bytes:
        return bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt())
