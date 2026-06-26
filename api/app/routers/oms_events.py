from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user

router = APIRouter()

@router.get("/")
async def list_oms_events(user=Depends(get_current_user)):
    return {"data": [], "module": "oms_events"}
