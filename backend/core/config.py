# Required environment variables:
# SECRET_KEY          - ESP32 WebSocket/push authentication key
# JWT_SECRET          - Random 32+ char string for JWT signing
# ADMIN_USERNAME      - Login username
# ADMIN_PASSWORD_HASH - bcrypt hash of password
# Generate password hash: python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"

import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
# 30 gun: kisisel tek-kullanicili kamera uygulamasinda gunluk yeniden giris
# gereksiz surtunmeydi (iOS standalone'da ozellikle rahatsiz edici).
JWT_EXPIRE_HOURS = 24 * 30
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

BAN_WINDOW = 15 * 60
MAX_ATTEMPTS = 5
