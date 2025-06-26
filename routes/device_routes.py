from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Set up router
router = APIRouter()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="frontend")

# MongoDB connection setup
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME")

if not MONGO_URI or not MONGO_DB:
    raise RuntimeError("Environment variables MONGO_URI and MONGO_DB_NAME must be set")

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]

@router.get("/devicedata", response_class=HTMLResponse)
async def get_device_data_page(request: Request):
    return templates.TemplateResponse("devicedata.html", {"request": request})

@router.get("/api/devicedata", response_class=JSONResponse)
async def get_device_data():
    try:
        collection = db.get_collection("sensor_data")
        data_cursor = collection.find(
            {},
            {
                "Battery_Level": 1,
                "Device_ID": 1,
                "First_Sensor_temperature": 1,
                "Route_From": 1,
                "Route_To": 1,
                "_id": 1
            }
        ).sort("_id", -1).limit(100)

        data = []
        async for document in data_cursor:
            document["_id"] = str(document["_id"])  # Convert ObjectId to string
            data.append(document)

        return JSONResponse(content=data)

    except Exception as e:
        # Log and return error message
        return JSONResponse(status_code=500, content={"error": f"Failed to fetch data: {str(e)}"})
