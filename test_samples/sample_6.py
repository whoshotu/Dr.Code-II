# Insecure Randomness for security purposes
import random
import string

def generate_token():
    return ''.join(random.choice(string.ascii_letters) for _ in range(32))

def generate_session_id():
    return random.randint(1000000, 9999999)

def create_password_reset():
    return ''.join([random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(10)])