from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2AuthorizationCodeBearer
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import JWTError, jwt
from datetime import datetime, timedelta
import aiohttp

from database.database import db
from database.models import TokenData, User

router = APIRouter()

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://accounts.google.com/o/oauth2/v2/auth",
    tokenUrl="https://oauth2.googleapis.com/token"
)


async def create_tokens(user_id: str, request: Request) -> TokenData:
    config = request.app.state.oauth_config
    access_token_expires = datetime.utcnow() + timedelta(minutes=config["access_token_expire_minutes"])
    refresh_token_expires = datetime.utcnow() + timedelta(days=7)  # 7 days for refresh token

    access_token = jwt.encode(
        {"sub": str(user_id), "exp": access_token_expires},
        config["secret_key"],
        algorithm=config["algorithm"]
    )

    refresh_token = jwt.encode(
        {"sub": str(user_id), "exp": refresh_token_expires},
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


@router.get("/google/login")
async def google_login(request: Request):
    config = request.app.state.oauth_config
    return {
        "url": f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={config['google_client_id']}&redirect_uri={config['google_redirect_uri']}&scope=openid email profile"
    }


@router.get("/google/callback")
async def google_callback(code: str, request: Request):
    config = request.app.state.oauth_config

    async with aiohttp.ClientSession() as session:
        # Exchange authorization code for tokens
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

                # Create or update user
                user_data = {
                    "email": idinfo["email"],
                    "full_name": idinfo["name"],
                    "username": idinfo["email"].split("@")[0],
                    "is_verified": idinfo["email_verified"],
                    "updated_at": datetime.utcnow(),
                    "last_login": datetime.utcnow()
                }

                result = await db.users.find_one_and_update(
                    {"email": user_data["email"]},
                    {"$set": user_data},
                    upsert=True,
                    return_document=True
                )

                # Create tokens
                tokens = await create_tokens(str(result["_id"]), request)
                return tokens

            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid token"
                )


@router.post("/refresh-token")
async def refresh_token(current_refresh_token: str, request: Request):
    config = request.app.state.oauth_config
    try:
        payload = jwt.decode(
            current_refresh_token,
            config["secret_key"],
            algorithms=[config["algorithm"]]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        tokens = await create_tokens(user_id, request)
        return tokens

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
