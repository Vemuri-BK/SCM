from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from datetime import datetime
from fastapi.staticfiles import StaticFiles
import os

from core.mongo import users_collection
from routes.user_routes import user_router
from routes.shipment_routes import router as shipment_router
from routes.device_routes import router as device_router
from routes.user_routes import hash_password

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="EXF Backend API")


# Setup CORS - allow credentials for cookie-based auth
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with actual frontend domain in production
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Admin User Setup on Startup ----------
async def create_default_admin():
    default_admin_email = os.getenv("DEFAULT_ADMIN_EMAIL")
    default_admin_username = os.getenv("DEFAULT_ADMIN_USERNAME")
    default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")

    if not all([default_admin_email, default_admin_username, default_admin_password]):
        print("⚠️ Default admin credentials are not fully set in .env")
        return

    existing_user = await users_collection.find_one({"email": default_admin_email})
    if existing_user:
        print("Default admin user already exists.")
        return

    hashed_password = hash_password(default_admin_password)
    new_admin = {
        "username": default_admin_username,
        "email": default_admin_email,
        "hashed_password": hashed_password,
        "role": "admin",
        "created_at": datetime.utcnow()
    }

    await users_collection.insert_one(new_admin)
    print("Default admin user created successfully.")

@app.on_event("startup")
async def startup_event():
    await create_default_admin()

# ---------- Mount Static Folders ----------
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# ---------- HTML File Routes ----------
@app.get("/", include_in_schema=False)
async def serve_signup():
    return FileResponse("frontend/signup.html")

@app.get("/login", include_in_schema=False)
async def serve_login():
    return FileResponse("frontend/login.html")

@app.get("/signup", include_in_schema=False)
async def serve_signup():
    return FileResponse("frontend/signup.html")

@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    return FileResponse("frontend/dashboard.html")

@app.get("/create-shipment", include_in_schema=False)
async def serve_create_shipment():
    return FileResponse("frontend/create-shipment.html")

@app.get("/shipments", include_in_schema=False)
async def serve_shipments():
    return FileResponse("frontend/shipments.html")

@app.get("/my-shipments", include_in_schema=False)
async def serve_my_shipments():
    return FileResponse("frontend/my-shipments.html")

@app.get("/manage-users", include_in_schema=False)
async def serve_manage_users():
    return FileResponse("frontend/manage-users.html")

@app.get("/account", include_in_schema=False)
async def serve_account():
    return FileResponse("frontend/account.html")

# ⚠️ Do NOT statically serve devicedata.html if rendered by Jinja2 in device_routes.py

# ---------- Include All Routers ----------
app.include_router(user_router, prefix="/api", tags=["Users"])
app.include_router(shipment_router, tags=["Shipments"])
app.include_router(device_router, tags=["Devices"])  # Includes Jinja2 rendering
