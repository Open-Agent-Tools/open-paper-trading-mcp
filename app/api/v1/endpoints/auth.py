from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class UserInDB(User):
    hashed_password: str


def fake_hash_password(password: str):
    return "fakehashed" + password


fake_users_db = {
    "testuser": {
        "username": "testuser",
        "full_name": "Test User",
        "email": "test@example.com",
        "hashed_password": "fakehashed" + "secret",
    }
}


def get_user(username: str):
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)


def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not fake_hash_password(password) == user.hashed_password:
        return False
    return user


@router.post("/token", response_model=Token, deprecated=True)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": user.username, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def read_users_me(token: str = Depends(oauth2_scheme)):
    user = get_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user