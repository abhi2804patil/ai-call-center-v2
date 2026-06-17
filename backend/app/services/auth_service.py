import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.user import User
from app.schemas.auth import CompanyRegister, TokenResponse
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    async def register_company(db: AsyncSession, data: CompanyRegister) -> tuple[Company, User, TokenResponse]:
        existing = await db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        existing_company = await db.execute(select(Company).where(Company.email == data.email))
        if existing_company.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company email already registered",
            )

        company = Company(
            name=data.name,
            email=data.email,
            api_key=generate_api_key(),
            settings={
                "default_language": "hi",
                "max_concurrent_calls": 10,
                "webhook_url": "",
            },
        )
        db.add(company)
        await db.flush()

        user = User(
            company_id=company.id,
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            role="admin",
        )
        db.add(user)
        await db.flush()

        token_data = {
            "user_id": str(user.id),
            "company_id": str(company.id),
            "role": user.role,
        }
        tokens = TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

        logger.info(f"Company registered: {company.name} ({company.email})")
        return company, user, tokens

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> tuple[User, TokenResponse]:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )

        user.last_login = datetime.now(timezone.utc)
        await db.flush()

        token_data = {
            "user_id": str(user.id),
            "company_id": str(user.company_id),
            "role": user.role,
        }
        tokens = TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

        logger.info(f"User logged in: {user.email}")
        return user, tokens

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user_id = payload.get("user_id")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        token_data = {
            "user_id": str(user.id),
            "company_id": str(user.company_id),
            "role": user.role,
        }
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

    @staticmethod
    async def get_current_user(db: AsyncSession, user_id: str) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user
