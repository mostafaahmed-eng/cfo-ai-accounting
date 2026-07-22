import asyncio
from uuid import uuid4

from passlib.context import CryptContext

from app.database import async_session
from app.models.user import User
from app.enums import UserStatus, Language

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def main():
    async with async_session() as session:
        user = User(
            id=uuid4(),
            email="admin@example.com",
            name="Admin",
            password_hash=pwd.hash("changeme123"),
            language=Language.en,
            timezone="UTC",
            status=UserStatus.active,
        )
        session.add(user)
        await session.commit()
        print("✅ User created successfully")
        print("Email: admin@example.com")
        print("Password: changeme123")


asyncio.run(main())
