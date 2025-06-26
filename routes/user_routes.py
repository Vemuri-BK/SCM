from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm # HIGHLIGHT: Import for OAuth2
from models.user_model import UserCreate, TestLoginRequest , UserLogin, UserOut,UserUpdateModel
from core.mongo import users_collection
from core.auth import get_current_user, admin_required, oauth2_scheme # HIGHLIGHT: Import oauth2_scheme
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from bson import ObjectId
import os
from dotenv import load_dotenv
import httpx
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse

load_dotenv()

user_router = APIRouter()

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))  # Default to 1 hour
DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL', 'bharath@example.com')


# Helper: hash password
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Helper: verify password
def verify_password(plain_pwd: str, hashed_pwd: str) -> bool:
    return pwd_context.verify(plain_pwd, hashed_pwd)

# Helper: create token
def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=2)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

# HIGHLIGHT START
@user_router.post("/token", summary="OAuth2 Token Endpoint", tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), response: Response = None):
    """
    OAuth2 compatible token login, returns an access token.
    This endpoint is used by Swagger UI for authentication.
    """
    user = await users_collection.find_one({"email": form_data.username}) # OAuth2PasswordRequestForm uses 'username' for the identifier
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = {
        "sub": str(user["_id"]),
        "username": user["username"],
        "role": user["role"]
    }
    token = create_token(token_data)

    if response: # response is optional here for flexibility
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=False,  # Use True in production with HTTPS
            samesite="Lax",
            max_age=JWT_ACCESS_TOKEN_EXPIRES,
            path="/"
        )
    return {"access_token": token, "token_type": "bearer"}
# HIGHLIGHT END


# POST /signup
@user_router.post("/signup", status_code=201)
async def signup(user: UserCreate):
    if await users_collection.find_one({
        "email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    if await users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already taken")

    user_dict = user.dict()
    user_dict["hashed_password"] = hash_password(user.password)
    user_dict.pop("password")
    user_dict["role"] = "admin" if await users_collection.count_documents({}) == 0 else "user"
    user_dict["created_at"] = datetime.utcnow()

    result = await users_collection.insert_one(user_dict)
    return JSONResponse(status_code=201, content={"msg": "User created", "user_id": str(result.inserted_id)})

# POST /login
# HIGHLIGHT START
# Modified to be a standard POST endpoint, still using UserLogin for reCAPTCHA
@user_router.post("/login")
async def login(credentials: UserLogin, response: Response):
# HIGHLIGHT END
    # ---- Step 1: Verify reCAPTCHA ----
    recaptcha_token = credentials.recaptcha_token
    recaptcha_secret = os.getenv("RECAPTCHA_SECRET_KEY")

    if not recaptcha_token:
        raise HTTPException(status_code=400, detail="Missing reCAPTCHA token")

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": recaptcha_secret, "response": recaptcha_token}
        )
    result = r.json()

    if not result.get("success"):
        raise HTTPException(status_code=400, detail="reCAPTCHA verification failed")

    # ---- Step 2: Verify user credentials ----
    user = await users_collection.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token_data = {
        "sub": str(user["_id"]),
        "username": user["username"],
        "role": user["role"]
    }
    token = create_token(token_data)

    # ---- Step 3: Set token in secure cookie ----
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # use False for local dev if needed
        samesite="Lax",
        max_age=JWT_ACCESS_TOKEN_EXPIRES,
        path="/"
    )

# HIGHLIGHT START
# Return success message, not the token directly for this reCAPTCHA-protected endpoint
    return {"msg": "Login successful"}
# HIGHLIGHT END

# GET /users (admin only)
# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.get("/users", dependencies=[Depends(admin_required), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def list_users(admin=Depends(admin_required)):
    users = await users_collection.find().to_list(100)
    return [
        {
            "id": str(u["_id"]),
            "username": u["username"],
            "email": u["email"],
            "role": u["role"]
        } for u in users
    ]


# PUT /users/{id}/make-admin (admin only)
# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.put("/users/{user_id}/make-admin", dependencies=[Depends(admin_required), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def make_admin(user_id: str, admin=Depends(admin_required)):
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": "admin"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"msg": "User promoted to admin"}

# DELETE /users/{id} (admin only)
# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.delete("/users/{user_id}", dependencies=[Depends(admin_required), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def delete_user(user_id: str, admin=Depends(admin_required)):
    result = await users_collection.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"msg": "User deleted"}



# GET /account (authenticated user)
# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.get("/account", dependencies=[Depends(get_current_user), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def get_account(user=Depends(get_current_user)):
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"].isoformat()
    }


# PUT /account/password (authenticated user)
class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.put("/account/password", dependencies=[Depends(get_current_user), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def change_password(data: PasswordChangeRequest, user=Depends(get_current_user)):
    if not verify_password(data.old_password, user["hashed_password"]):
        raise HTTPException(status_code=403, detail="Incorrect old password")

    hashed_new = hash_password(data.new_password)
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"hashed_password": hashed_new}}
    )
    return {"msg": "Password updated successfully"}


# GET /dashboard (redirect based on role)
# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.get("/dashboard", dependencies=[Depends(get_current_user), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def dashboard_redirect(user=Depends(get_current_user)):
    if user["role"] == "admin":
        return RedirectResponse(url="/dashboard/admin")
    return RedirectResponse(url="/dashboard/user")

# GET /dashboard/admin
# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.get("/dashboard/admin", dependencies=[Depends(admin_required), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def admin_dashboard(admin=Depends(admin_required)):
    return {
        "msg": f"Welcome Admin {admin['username']}",
        "links": [
            {"label": "Create Shipment", "url": "/api/shipments"},
            {"label": "Manage Users", "url": "/api/users"},
            {"label": "Manage Shipments", "url": "/api/shipments/all"},
            {"label": "Logout", "url": "/logout"}  # handled client-side
        ]
    }

# GET /dashboard/user
# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.get("/dashboard/user", dependencies=[Depends(get_current_user), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def user_dashboard(user=Depends(get_current_user)):
    return {
        "msg": f"Welcome {user['username']}",
        "links": [
            {"label": "Create Shipment", "url": "/api/shipments"},
            {"label": "My Shipments", "url": "/api/shipments"},
            {"label": "Account Details", "url": "/api/account"},
            {"label": "Logout", "url": "/logout"}  # handled client-side
        ]
    }

# GET /logout (handled client-side)
@user_router.get("/logout")
async def logout():
    response = JSONResponse(status_code=200, content={"msg": "Logged out successfully"})
    response.delete_cookie("access_token")
    return response

@user_router.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out successfully."})
    response.delete_cookie(key="access_token")
    return response

# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.get("/manage-users", dependencies=[Depends(admin_required), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def get_all_users():
    users = await users_collection.find().to_list(100)
    result = []
    for user in users:
        result.append({
            "id": str(user["_id"]),
            "username": user.get("username", ""),
            "email": user.get("email", ""),
            "role": user.get("role", "user"),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else ""
        })
    return result



# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.put("/manage-users/{user_id}", dependencies=[Depends(admin_required), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def update_user(user_id: str, user_data: UserUpdateModel):
    # Check if user exists
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent modification of default admin
    if user.get("email") == DEFAULT_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Cannot modify default admin user")
    
    # Check if email is already taken by another user
    if user_data.email != user.get("email"):
        existing_user = await users_collection.find_one({"email": user_data.email})
        if existing_user and str(existing_user["_id"]) != user_id:
            raise HTTPException(status_code=400, detail="Email already in use")
    
    # Check if username is already taken by another user
    if user_data.username != user.get("username"):
        existing_user = await users_collection.find_one({"username": user_data.username})
        if existing_user and str(existing_user["_id"]) != user_id:
            raise HTTPException(status_code=400, detail="Username already in use")
    
    # Update user
    update_data = {
        "username": user_data.username,
        "email": user_data.email,
        "role": user_data.role
    }
    
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No changes made")
    
    return {"msg": "User updated successfully"}

# HIGHLIGHT START
# Added oauth2_scheme to the dependencies for Swagger UI compatibility
@user_router.delete("/manage-users/{user_id}", dependencies=[Depends(admin_required), Depends(oauth2_scheme)])
# HIGHLIGHT END
async def delete_user(user_id: str):
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deletion of default admin
    if user.get("email") == DEFAULT_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Cannot delete default admin user")
    
    # Prevent deletion if last admin
    if user.get("role") == "admin":
        admin_count = await users_collection.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete the last admin user. Promote another user first."
            )
    
    result = await users_collection.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Failed to delete user")
    
    return {"msg": "User deleted successfully"}

# [Rest of your existing routes remain the same]


@user_router.get("/clear-token")
async def clear_token():
    response = HTMLResponse(content="Token cleared")
    response.delete_cookie("access_token")
    return response