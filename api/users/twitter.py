from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
from datetime import datetime
import tweepy
import json
from uuid import uuid4
from datetime import timedelta

from database.database import Database, get_database
from database.models import TwitterTokenData

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

TWITTER_API_KEY = "w44a559b3SZ6aZv4BQf5vF7w4"
TWITTER_API_SECRET = "FQgrfQ8Rw3qUYTjGo4ZqFNNIIOY5n5hadHqdSsgYE4yOOYYrzz"
TWITTER_CALLBACK_URL = "http://localhost:3000/twitterlogin"

class TwitterAuth:
    def __init__(self):
        try:
            self.auth = tweepy.OAuthHandler(
                TWITTER_API_KEY, 
                TWITTER_API_SECRET, 
                TWITTER_CALLBACK_URL
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize Twitter auth: {str(e)}"
            )

    def get_auth_url(self):
        try:
            auth_url = self.auth.get_authorization_url()
            return auth_url, {
                'oauth_token': self.auth.request_token['oauth_token'],
                'oauth_token_secret': self.auth.request_token['oauth_token_secret']
            }
        except tweepy.TweepError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to get Twitter auth URL: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}"
            )

@router.get("/twitter/login")
async def twitter_login(request: Request):
    twitter_auth = TwitterAuth()
    try:
        auth_url, token_data = twitter_auth.get_auth_url()
        request.session['oauth_token'] = token_data['oauth_token']
        request.session['oauth_token_secret'] = token_data['oauth_token_secret']
        return {
            "auth_url": auth_url,
            "oauth_token": token_data['oauth_token']
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/verify-session")
async def verify_session(
    request: Request,
    db: Database = Depends(get_database)
):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        session_token = auth_header.split(' ')[1]
        session = await db.sessions.find_one({
            "session_token": session_token,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not session:
            return {"isValid": False}

        await db.sessions.update_one(
            {"session_token": session_token},
            {"$set": {"last_accessed": datetime.utcnow()}}
        )

        return {"isValid": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/twitter/callback")
async def twitter_callback(
    request: Request,
    db: Database = Depends(get_database)
):
    try:
        oauth_verifier = request.query_params.get('oauth_verifier')
        oauth_token = request.query_params.get('oauth_token')
        
        if not oauth_verifier or not oauth_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing OAuth parameters"
            )
        
        stored_oauth_token = request.session.get('oauth_token')
        if oauth_token != stored_oauth_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth token mismatch"
            )

        twitter_auth = TwitterAuth()
        oauth_token_secret = request.session.get('oauth_token_secret')
        if not oauth_token_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing OAuth token secret"
            )

        twitter_auth.auth.request_token = {
            'oauth_token': oauth_token,
            'oauth_token_secret': oauth_token_secret
        }

        try:
            access_token, access_token_secret = twitter_auth.auth.get_access_token(oauth_verifier)
            twitter_auth.auth.set_access_token(access_token, access_token_secret)
        except tweepy.TweepError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to get access token: {str(e)}"
            )

        api = tweepy.API(twitter_auth.auth)
        twitter_user = api.verify_credentials()
        
        user_data = {
            "username": twitter_user.screen_name,
            "email": f"{twitter_user.screen_name}@memepay.me",
            "full_name": twitter_user.name,
            "twitter_id": str(twitter_user.id),
            "twitter_username": twitter_user.screen_name,
            "twitter_profile_image": twitter_user.profile_image_url_https,
            "updated_at": datetime.utcnow(),
            "last_login": datetime.utcnow()
        }

        result = await db.users.update_one(
            {"twitter_id": str(twitter_user.id)},
            {"$set": user_data},
            upsert=True
        )

        user = await db.users.find_one({"twitter_id": str(twitter_user.id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create/update user"
            )

        token_data = TwitterTokenData(
            user_id=str(user["_id"]),
            access_token=access_token,
            refresh_token=access_token_secret,
            token_type="bearer",
            expires_at=datetime.utcnow()
        )

        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "twitter_token": token_data.model_dump(),
                "last_login": datetime.utcnow()
            }}
        )

        session_token = str(uuid4())
        await db.sessions.insert_one({
            "session_token": session_token,
            "user_id": str(user["_id"]),
            "twitter_id": twitter_user.id,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "last_accessed": datetime.utcnow(),
            "user_agent": request.headers.get("user-agent"),
            "ip_address": request.client.host if request.client else None
        })

        request.session.pop('oauth_token', None)
        request.session.pop('oauth_token_secret', None)

        return {
            "status": "success",
            "user": {
                "id": str(user["_id"]),
                "username": user["username"],
                "full_name": user["full_name"],
                "twitter_username": twitter_user.screen_name,
                "profile_image": twitter_user.profile_image_url_https
            },
            "session_token": session_token
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Twitter authentication failed: {str(e)}"
        )
