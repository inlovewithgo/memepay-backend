from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from database.database import Database, get_database
from bson import ObjectId
from requests import Request

router = APIRouter(
    prefix="/api/users",
    tags=["Users"]
)

@router.get("/online")
async def get_online_users(
    request: Request,
    db: Database = Depends(get_database)
):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )

        session_token = auth_header.split(' ')[1]
        
        active_sessions = await db.sessions.find({
            "expires_at": {"$gt": datetime.utcnow()}
        }).to_list(length=100)

        online_users = []
        for session in active_sessions:
            user = await db.users.find_one({"_id": ObjectId(session["user_id"])})
            if user:
                online_users.append({
                    "id": str(user["_id"]),
                    "username": user.get("twitter_username"),
                    "profile_image": user.get("twitter_profile_image"),
                    "full_name": user.get("full_name"),
                    "last_active": session.get("last_accessed")
                })

        return {
            "status": "success",
            "online_users": online_users
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch online users: {str(e)}"
        )

@router.get("/profile")
async def get_user_profile(
    request: Request,
    db: Database = Depends(get_database)
):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )

        session_token = auth_header.split(' ')[1]
        session = await db.sessions.find_one({
            "session_token": session_token,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )

        user = await db.users.find_one({"_id": ObjectId(session["user_id"])})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "status": "success",
            "profile": {
                "id": str(user["_id"]),
                "username": user.get("twitter_username"),
                "full_name": user.get("full_name"),
                "profile_image": user.get("twitter_profile_image"),
                "email": user.get("email"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login")
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user profile: {str(e)}"
        )
