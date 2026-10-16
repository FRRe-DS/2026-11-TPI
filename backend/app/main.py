from fastapi import FastAPI

from app.routers import liquidaciones, pagos, tarifas

app = FastAPI(
    title="M7 - Tarifas, Pagos y Liquidaciones",
    description="Microservicio del Grupo 11 - TPI Desarrollo de Software 2026",
    version="0.1.0",
)

for router in (tarifas.router, pagos.router, liquidaciones.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
