from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ShipmentCreate(BaseModel):
    shipment_number: str = Field(..., min_length=1)
    route: str
    device: str
    po_number: str
    ndc_number: str
    serial_number: str
    container_number: str
    goods_type: str
    delivery_date: str  # ISO string from frontend
    delivery_number: str
    batch_id: str
    description: str
    status: Optional[str] = Field(default="In Transit")


class ShipmentOut(BaseModel):
    id: Optional[str]
    shipment_number: str
    route: str
    device: str
    goods_type: str
    delivery_date: str
    created_by: str
    created_at: datetime
