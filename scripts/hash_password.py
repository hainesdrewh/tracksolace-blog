"""Generate a password hash for ADMIN_PASSWORD_HASH in .env.

Usage: python scripts/hash_password.py
Prompts for a password and prints the hash to paste into .env.
"""
import getpass
from werkzeug.security import generate_password_hash

if __name__ == "__main__":
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    print(generate_password_hash(password))
