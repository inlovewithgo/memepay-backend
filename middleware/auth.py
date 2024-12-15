from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from bson import ObjectId
from database.database import db
from database.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    config = request.app.state.oauth_config

    try:
        payload = jwt.decode(token, config["secret_key"], algorithms=[config["algorithm"]])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user is None:
            raise credentials_exception

        return User(**user)

    except JWTError:
        raise credentials_exception

# @app.get("/protected")
# async def protected_route(current_user: User = Depends(get_current_user)):
#     return {"message": "This is a protected route", "user": current_user}
