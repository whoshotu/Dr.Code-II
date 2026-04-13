# Hardcoded secrets
API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
DATABASE_PASSWORD = "my_secret_password_123"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# In source code
def connect_to_service():
    token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    return api.connect(token=token)

# Another example
CONFIG = {
    "api_key": "sk-live-abc123def456ghi789jkl012mno345p",
    "secret": "SuperSecretPassword123!",
}