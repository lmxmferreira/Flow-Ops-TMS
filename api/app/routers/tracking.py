from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user

router = APIRouter()

@router.get("/")
async def list_tracking(user=Depends(get_current_user)):
    return {"data": [], "module": "tracking"}
