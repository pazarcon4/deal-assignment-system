"""
Seeds users from seed_users.json (gitignored -- keeps real names/emails out of
this public repo). Copy seed_users.example.json to seed_users.json and fill
in your real roster, then run:
    python3 seed.py

Safe to re-run: existing emails are skipped, only missing users are added.
Generated passwords are printed once at the end -- share them with each
person and have them change their password after first login.
"""
import json
import os
import secrets
import string
import sys

from werkzeug.security import generate_password_hash

from db import get_connection, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_USERS_PATH = os.path.join(BASE_DIR, "seed_users.json")


def load_seed_users():
    if not os.path.exists(SEED_USERS_PATH):
        sys.exit(
            f"Missing {SEED_USERS_PATH}.\n"
            "Copy seed_users.example.json to seed_users.json and fill in your real roster first."
        )
    with open(SEED_USERS_PATH) as f:
        return json.load(f)


def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    seed_users = load_seed_users()
    init_db()
    conn = get_connection()
    created = []

    for user in seed_users:
        existing = conn.execute(
            "SELECT id FROM users WHERE lower(email) = %s", (user["email"].lower(),)
        ).fetchone()
        if existing:
            continue

        password = generate_password()
        conn.execute(
            "INSERT INTO users (name, email, role, password_hash) VALUES (%s, %s, %s, %s)",
            (
                user["name"],
                user["email"],
                user["role"],
                generate_password_hash(password, method="pbkdf2:sha256"),
            ),
        )
        created.append((user["name"], user["email"], user["role"], password))

    conn.commit()
    conn.close()

    if not created:
        print("No new users created -- all seed emails already exist.")
        return

    print("Created accounts (share these credentials, then have each person change their password):\n")
    print(f"{'Name':<20}{'Email':<28}{'Role':<12}{'Password'}")
    for name, email, role, password in created:
        print(f"{name:<20}{email:<28}{role:<12}{password}")


if __name__ == "__main__":
    main()
