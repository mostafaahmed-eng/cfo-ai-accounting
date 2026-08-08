#!/usr/bin/env python3
"""Create a platform admin user for the CFO Manager application.

Usage:
    python create_admin.py --email admin@example.com --password '<strong-password>' --name "Admin User"

The password is required and must match the application password policy
(minimum length from MIN_PASSWORD_LENGTH, plus uppercase, lowercase, and a
digit). The password is never logged or echoed back after creation.

Requires DATABASE_URL environment variable or .env file to be configured.
"""

import argparse
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise ValueError("Invalid email address")
    return normalized


def validate_password_strength(password: str) -> None:
    from app.config import get_settings

    min_len = get_settings().MIN_PASSWORD_LENGTH
    if len(password) < min_len:
        raise ValueError(f"Password must be at least {min_len} characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one digit")


async def create_admin(email: str, password: str, name: str) -> None:
    from uuid import uuid4

    from app.core.security import hash_password
    from app.database import async_session
    from app.models.user import User

    normalized = normalize_email(email)
    validate_password_strength(password)

    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.email == normalized))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User with email '{normalized}' already exists (id={existing.id}).")
            return

        user = User(
            id=uuid4(),
            email=normalized,
            name=name,
            password_hash=hash_password(password),
            status="active",
        )
        session.add(user)
        await session.commit()
        print("Admin user created successfully:")
        print(f"  Email:    {normalized}")
        print(f"  ID:       {user.id}")
        print(
            "Platform-admin access is granted by listing this email in "
            "PLATFORM_ADMIN_EMAILS."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user for CFO Manager")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument(
        "--name", default="Admin", help="Admin display name (default: Admin)"
    )
    args = parser.parse_args()

    asyncio.run(create_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
