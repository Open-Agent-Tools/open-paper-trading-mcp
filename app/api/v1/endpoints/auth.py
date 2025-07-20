from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.exceptions import NotFoundError
from app.services.auth_service import AuthService, auth_service

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None


def get_auth_service() -> AuthService:
    """Dependency to get auth service instance."""
    return auth_service


@router.post("/token", response_model=Token, deprecated=True)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    user = service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=service.access_token_expire_minutes)
    access_token = service.create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def read_users_me(
    token: str = Depends(oauth2_scheme),
    service: AuthService = Depends(get_auth_service),
) -> User:
    try:
        user = service.get_current_user(token)
        return User(
            username=user["username"],
            email=user.get("email"),
            full_name=user.get("full_name"),
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
