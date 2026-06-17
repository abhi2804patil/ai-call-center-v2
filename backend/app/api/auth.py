from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import (
    CompanyRegister,
    CompanyResponse,
    LoginRequest,
    RefreshRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from sqlalchemy import select

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
async def register(data: CompanyRegister, db: AsyncSession = Depends(get_db)):
    company, user, tokens = await AuthService.register_company(db, data)
    return RegisterResponse(
        company=CompanyResponse.model_validate(company),
        user=UserResponse.model_validate(user),
        tokens=tokens,
    )


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user, tokens = await AuthService.login(db, data.email, data.password)
    return {
        "user": UserResponse.model_validate(user),
        "tokens": tokens,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await AuthService.refresh_token(db, data.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.get("/company", response_model=CompanyResponse)
async def get_company(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one_or_none()
    return CompanyResponse.model_validate(company)
