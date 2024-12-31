from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from datetime import datetime
from typing import List
from pydantic import BaseModel
from database.database import Database, get_database
from requests import Request
from bson import ObjectId

router = APIRouter(
    prefix="/api/messages",
    tags=["Messages"]
)

class MessageCreate(BaseModel):
    channel: str
    content: str

class Message(MessageCreate):
    id: str
    user_id: str
    timestamp: datetime
    
    class Config:
        from_attributes = True

@router.post("/send")
async def send_message(
    message: MessageCreate,
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

        message_data = {
            "channel": message.channel,
            "content": message.content,
            "user_id": str(user["_id"]),
            "username": user.get("twitter_username", user["username"]),
            "profile_image": user.get("twitter_profile_image"),
            "full_name": user.get("full_name"),
            "timestamp": datetime.utcnow()
        }

        result = await db.messages.insert_one(message_data)
        
        return {
            "status": "success",
            "message": {
                "id": str(result.inserted_id),
                **message_data
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )

@router.get("/channel/{channel_id}")
async def get_channel_messages(
    channel_id: str,
    request: Request,
    limit: int = 50,
    before: datetime = None,
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

        query = {"channel": channel_id}
        if before:
            query["timestamp"] = {"$lt": before}

        messages = await db.messages.find(
            query,
            sort=[("timestamp", -1)],
            limit=limit
        ).to_list(length=limit)

        return {
            "status": "success",
            "messages": [
                {
                    "id": str(msg["_id"]),
                    "content": msg["content"],
                    "user_id": msg["user_id"],
                    "username": msg["username"],
                    "profile_image": msg["profile_image"],
                    "full_name": msg.get("full_name"),
                    "timestamp": msg["timestamp"]
                }
                for msg in messages
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch messages: {str(e)}"
        )
