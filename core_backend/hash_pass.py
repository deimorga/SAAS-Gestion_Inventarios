from app.core.security import pwd_context
hash_str = pwd_context.hash("cris1234")
print(f"UPDATE users SET password_hash = '{hash_str}' WHERE email = 'cristian@superadmin.com';")
