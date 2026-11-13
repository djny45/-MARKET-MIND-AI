"""Generate an scrypt owner password hash for MARKET-MIND-AI.

Run from backend with: python create_owner_hash.py
The password is read interactively and is never written to disk.
"""
from getpass import getpass

from app.auth_crypto import hash_password


def main() -> None:
    password = getpass("Owner password: ")
    confirmation = getpass("Confirm owner password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 12:
        raise SystemExit("Use a password with at least 12 characters.")
    print("\nSet this value in your deployment environment as")
    print("MARKET_MIND_OWNER_PASSWORD_HASH:")
    print(hash_password(password))


if __name__ == "__main__":
    main()
