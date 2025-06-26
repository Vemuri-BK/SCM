# core/auth.py
from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from core.mongo import users_collection
from bson import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize OAuth2PasswordBearer. The tokenUrl is where clients can obtain a token.
# This is what Swagger UI will use to understand the authentication flow.
# We set auto_error=False so that it doesn't immediately raise an error
# if the Bearer token is not present, allowing our cookie logic to run first.
# HIGHLIGHT START
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token" , auto_error=False) # KEY CHANGE HERE
# HIGHLIGHT END
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))  # Default to 1 hour

async def get_current_user(request: Request, bearer_token: str = Depends(oauth2_scheme)): # Renamed for clarity
    # Prioritize the token from the cookie if it exists.
    cookie_token = request.cookies.get("access_token")

    effective_token = None
    if cookie_token:
        effective_token = cookie_token
    elif bearer_token: # If no cookie, check for bearer token (e.g., from Swagger UI)
        effective_token = bearer_token

    if not effective_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(effective_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, # Changed to 404 as user not found is specific
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, # Token invalid, typically 403
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Admin role check dependency remains the same
async def admin_required(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user