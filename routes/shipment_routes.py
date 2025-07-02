import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request, Query
from fastapi.encoders import jsonable_encoder
from jose import JWTError, jwt
from models.shipment_model import ShipmentCreate
from core.mongo import shipments_collection, users_collection
from bson import ObjectId
from datetime import datetime
import os
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from core.auth import get_current_user, admin_required
import traceback

router = APIRouter()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

templates = Jinja2Templates(directory="frontend")

# 🚚 Create a new shipment
@router.post("/api/shipments", status_code=201)
async def create_shipment(shipment: ShipmentCreate, user=Depends(get_current_user)):
    shipment_data = shipment.dict()
    shipment_data["created_by"] = {
        "id": user["_id"],
        "username": user["username"],
        "role": user["role"]
    }
    shipment_data["created_at"] = datetime.utcnow()

    result = await shipments_collection.insert_one(shipment_data)
    return {"msg": "Shipment created", "shipment_id": str(result.inserted_id)}


# 📄 HTML Page for "My Shipments"
@router.get("/my-shipments", response_class=HTMLResponse)
async def my_shipments_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("my-shipments.html", {"request": request, "user": user})


# 👤 Get shipments created by current user
@router.get("/api/my-shipments")
async def get_my_shipments(user=Depends(get_current_user)):
    try:
        shipments_cursor = shipments_collection.find({
            "created_by.id": user["_id"]
        })

        response_data = []
        async for s in shipments_cursor:
            delivery_date = s.get("delivery_date")
            delivery_date_str = delivery_date.isoformat().split("T")[0] if hasattr(delivery_date, 'isoformat') else str(delivery_date)

            response_data.append({
                "shipment_number": s.get("shipment_number", "N/A"),
                "route": s.get("route", ""),
                "device": s.get("device", ""),
                "goods_type": s.get("goods_type", ""),
                "delivery_date": delivery_date_str,
                "status": s.get("status", "Pending")
            })

        return response_data

    except Exception:
        logging.error(f"Error fetching my shipments: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching your shipments."
        )


# 🧑‍💼 Admin: Get all shipments, with optional filtering by created_by username
@router.get("/api/shipments")
async def get_all_shipments(
    created_by: str = Query(None, description="Filter by creator username"),
    user=Depends(admin_required)
):
    try:
        query = {}
        if created_by:
            query["created_by.username"] = {"$regex": f"^{created_by}", "$options": "i"}  # case-insensitive prefix match

        shipments = await shipments_collection.find(query).to_list(100)

        return [
            {
                "id": str(s["_id"]),
                "shipment_number": s.get("shipment_number", ""),
                "route": s.get("route", ""),
                "goods_type": s.get("goods_type", ""),
                "device": s.get("device", ""),
                "delivery_date": s.get("delivery_date", ""),
                "status": s.get("status", ""),
                "created_by": s.get("created_by", {}).get("username", "")
            }
            for s in shipments
        ]
    except Exception:
        logging.error(f"Error fetching all shipments: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch shipments."
        )


# ✏️ Update shipment by ID
@router.put("/api/shipments/{shipment_id}")
async def update_shipment(shipment_id: str, updates: dict, user=Depends(admin_required)):
    result = await shipments_collection.update_one(
        {"_id": ObjectId(shipment_id)},
        {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Shipment not found")

    return {"msg": "Shipment updated successfully"}


# 🗑️ Delete shipment by ID
@router.delete("/api/shipments/{shipment_id}")
async def delete_shipment(shipment_id: str, user=Depends(admin_required)):
    result = await shipments_collection.delete_one({"_id": ObjectId(shipment_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Shipment not found")

    return {"msg": "Shipment deleted"}
