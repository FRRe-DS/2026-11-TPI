from fastapi import APIRouter

from app.api.v1.endpoints import contrato

api_router = APIRouter()

api_router.include_router(contrato.router)
