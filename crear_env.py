content = (
    "SECRET_KEY=30b6362f90cfc67c7698a65aaaaa19c3e1e87e0c625dc0ca1693e2a1037523a327a9a500af2ced0e825a45c14f21570a52ef\n"
    "DEBUG=True\n"
    "ALLOWED_HOSTS=localhost,127.0.0.1\n"
    "DATABASE_URL=postgres://postgres:elian123@localhost:5432/sales_a2\n"
    "CSRF_TRUSTED_ORIGINS=\n"
    "PAYPHONE_TOKEN=\n"
    "PAYPHONE_STORE_ID=\n"
)
with open('.env', 'w', encoding='utf-8') as f:
    f.write(content)
print('Listo - .env creado en UTF-8')