from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, OAuth2AuthorizationCodeBearer
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from google.oauth2 import id_token
from google.auth.transport import requests
import aiohttp
from typing import Optional
from database.database import get_database, Database, db
from database.models import User, UserInDB, TokenData

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
google_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://accounts.google.com/o/oauth2/v2/auth",
    tokenUrl="https://oauth2.googleapis.com/token"
)

SECRET_KEY = ""
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
        user = await db.users.find_one({"username": username})
        if not user:
            raise credentials_exception
        return UserInDB(**user)
    except JWTError:
        raise credentials_exception

async def create_tokens(user_id: str, request: Request) -> TokenData:
    config = request.app.state.oauth_config
    access_token_expires = datetime.utcnow() + timedelta(minutes=config["access_token_expire_minutes"])
    refresh_token_expires = datetime.utcnow() + timedelta(days=7)
    
    access_token = jwt.encode(
        {"sub": str(user_id), "exp": access_token_expires},
        config["secret_key"],
        algorithm=config["algorithm"]
    )
    
    refresh_token = jwt.encode(
        {"sub": str(user_id), "exp": refresh_token_expires, "refresh": True},
        config["secret_key"],
        algorithm=config["algorithm"]
    )
    
    token_data = TokenData(
        user_id=str(user_id),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=access_token_expires
    )
    await db.tokens.insert_one(token_data.dict())
    return token_data

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserInDB, request: Request, db: Database = Depends(get_database)):
    existing_user = await db.users.find_one({
        "$or": [
            {"email": user_data.email},
            {"username": user_data.username}
        ]
    })
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    user_dict = user_data.model_dump(exclude={"id"})
    user_dict["password"] = pwd_context.hash(user_dict["password"])
    user_dict["created_at"] = datetime.utcnow()
    user_dict["updated_at"] = datetime.utcnow()
    user_dict["auth_provider"] = "local"

    try:
        result = await db.users.insert_one(user_dict)
        created_user = await db.users.find_one({"_id": result.inserted_id})
        if created_user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        return User(**created_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user = await db.users.find_one({"email": form_data.username})
        if user is None:
            user = await db.users.find_one({"username": form_data.username})
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )

        if not verify_password(form_data.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["_id"])},
            expires_delta=access_token_expires
        )

        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": str(user["_id"])
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )




@router.get("/google/login")
async def google_login(request: Request):
    config = request.app.state.oauth_config
    return {
        "url": f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={config['google_client_id']}&redirect_uri={config['google_redirect_uri']}&scope=openid email profile"
    }

@router.get("/google/callback")
async def google_callback(code: str, request: Request, db: Database = Depends(get_database)):
    config = request.app.state.oauth_config

    async with aiohttp.ClientSession() as session:
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": config["google_client_id"],
            "client_secret": config["google_client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config["google_redirect_uri"]
        }

        async with session.post(token_url, data=token_data) as response:
            tokens = await response.json()

            if "error" in tokens:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=tokens["error_description"]
                )

            try:
                idinfo = id_token.verify_oauth2_token(
                    tokens["id_token"],
                    requests.Request(),
                    config["google_client_id"]
                )

                user_data = {
                    "email": idinfo["email"],
                    "full_name": idinfo["name"],
                    "username": idinfo["email"].split("@")[0],
                    "is_verified": idinfo["email_verified"],
                    "updated_at": datetime.utcnow(),
                    "last_login": datetime.utcnow(),
                    "auth_provider": "google"
                }

                result = await db.users.find_one_and_update(
                    {"email": user_data["email"]},
                    {"$set": user_data},
                    upsert=True,
                    return_document=True
                )

                tokens = await create_tokens(str(result["_id"]), request)
                return tokens

            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid token"
                )

@router.get("/me", response_model=User)
async def get_user_profile(current_user: UserInDB = Depends(get_current_user)):
    return User(**current_user.dict())

@router.post("/refresh-token")
async def refresh_token(current_refresh_token: str, request: Request, db: Database = Depends(get_database)):
    config = request.app.state.oauth_config
    try:
        payload = jwt.decode(
            current_refresh_token,
            config["secret_key"],
            algorithms=[config["algorithm"]]
        )
        if not payload.get("refresh"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token"
            )
        user_id = payload.get("sub")
        tokens = await create_tokens(user_id, request)
        return tokens

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
