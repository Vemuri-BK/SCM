from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os
from typing import Union

router = APIRouter()
templates = Jinja2Templates(directory="frontend")

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
async def get_device_data(
    limit: int = Query(100, ge=1, le=1000),
    device_id: Optional[Union[int, str]] = Query(None)
):
    try:
        collection = db.get_collection("sensor_data")
        query = {}

        if device_id:
            try:
                query["Device_ID"] = int(device_id)
            except ValueError:
                return JSONResponse(status_code=400, content={"error": "Device ID must be numeric"})

        print("Mongo query:", query)

        cursor = collection.find(
            query,
            {
                "Battery_Level": 1,
                "Device_ID": 1,
                "First_Sensor_temperature": 1,
                "Route_From": 1,
                "Route_To": 1,
                "_id": 1
            }
        ).sort("_id", -1).limit(limit)

        data = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            data.append(doc)

        return JSONResponse(content=data)

    except Exception as e:
        print("Error:", e)
        return JSONResponse(status_code=500, content={"error": f"Failed to fetch data: {str(e)}"})