from fastapi import APIRouter

from app.api.v1.endpoints import contrato, liquidaciones, pagos, tarifas

api_router = APIRouter()

api_router.include_router(tarifas.router)
api_router.include_router(pagos.router)
api_router.include_router(liquidaciones.router)
api_router.include_router(contrato.router)
