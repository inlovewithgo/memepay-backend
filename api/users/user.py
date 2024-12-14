from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from bson import ObjectId
import os

from database.database import get_database, Database
from database.models import User, UserInDB, UserUpdate, TokenData

router = APIRouter(prefix="/api/user", tags=["User Management"])

SECRET_KEY = ("JWT_SECRET_KEY", "idk")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Database = Depends(get_database)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise credentials_exception
    return UserInDB(**user)


def create_tokens(user_id: str) -> tuple[str, str]:
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow() + access_token_expires},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    refresh_token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow() + refresh_token_expires, "refresh": True},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return access_token, refresh_token


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserInDB, db: Database = Depends(get_database)):
    existing_user = await db.users.find_one({
        "$or": [
            {"email": user.email},
            {"username": user.username}
        ]
    })
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    user_dict = user.dict(exclude={"id"})
    user_dict["password"] = pwd_context.hash(user_dict["password"])
    user_dict["created_at"] = datetime.utcnow()

    result = await db.users.insert_one(user_dict)
    created_user = await db.users.find_one({"_id": result.inserted_id})
    return User(**created_user)


@router.post("/login", response_model=TokenData)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Database = Depends(get_database)
):
    user = await db.users.find_one({"username": form_data.username})
    if not user or not pwd_context.verify(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    access_token, refresh_token = create_tokens(str(user["_id"]))

    token_data = TokenData(
        user_id=str(user["_id"]),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )

    return token_data


@router.get("/me", response_model=User)
async def get_user_profile(current_user: UserInDB = Depends(get_current_user)):
    return User(**current_user.dict())


@router.patch("/me", response_model=User)
async def update_user_profile(
        update_data: UserUpdate,
        current_user: UserInDB = Depends(get_current_user),
        db: Database = Depends(get_database)
):
    update_dict = update_data.dict(exclude_unset=True)

    if "password" in update_dict:
        update_dict["password"] = pwd_context.hash(update_dict["password"])

    if "email" in update_dict or "username" in update_dict:
        existing_user = await db.users.find_one({
            "_id": {"$ne": current_user.id},
            "$or": [
                {"email": update_dict.get("email", "")},
                {"username": update_dict.get("username", "")}
            ]
        })
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists"
            )

    update_dict["updated_at"] = datetime.utcnow()

    await db.users.update_one(
        {"_id": current_user.id},
        {"$set": update_dict}
    )

    updated_user = await db.users.find_one({"_id": current_user.id})
    return User(**updated_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
        current_user: UserInDB = Depends(get_current_user),
        db: Database = Depends(get_database)
):
    await db.users.delete_one({"_id": current_user.id})
    await db.tokens.delete_many({"user_id": str(current_user.id)})


@router.post("/refresh", response_model=TokenData)
async def refresh_token(
        refresh_token: str,
        db: Database = Depends(get_database)
):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("refresh"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token"
            )
        user_id = payload.get("sub")
        user = await db.users.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        access_token, new_refresh_token = create_tokens(user_id)

        token_data = TokenData(
            user_id=user_id,
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_at=datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return token_data

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
