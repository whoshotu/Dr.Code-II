# Weak Cryptography
import hashlib

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hashlib.sha1(password.encode()).hexdigest() == hashed

# Insecure key derivation
def derive_key(secret):
    return hashlib.md5(secret).digest()