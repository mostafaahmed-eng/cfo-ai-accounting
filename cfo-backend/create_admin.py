#!/usr/bin/env python3
"""Create an admin user for the CFO Manager application.

Usage:
    python create_admin.py
    python create_admin.py --email admin@example.com --password changeme123 --name "Admin User"

Requires DATABASE_URL environment variable or .env file to be configured.
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def create_admin(email: str, password: str, name: str):
    from uuid import uuid4
    from app.database import async_session
    from app.models.user import User
    from app.core.security import hash_password

    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User with email '{email}' already exists (id={existing.id}).")
            return

        user = User(
            id=uuid4(),
            email=email,
            name=name,
            password_hash=hash_password(password),
            status="active",
        )
        session.add(user)
        await session.commit()
        print(f"Admin user created successfully:")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")
        print(f"  ID:       {user.id}")


def main():
    parser = argparse.ArgumentParser(description="Create an admin user for CFO Manager")
    parser.add_argument("--email", default="admin@example.com", help="Admin email (default: admin@example.com)")
    parser.add_argument("--password", default="changeme123", help="Admin password (default: changeme123)")
    parser.add_argument("--name", default="Admin", help="Admin display name (default: Admin)")
    args = parser.parse_args()

    asyncio.run(create_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
