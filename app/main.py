from fastapi import FastAPI

from app.api.payments import router as payments_router

app = FastAPI(title="Async Payment Processing Service", version="1.0.0")
app.include_router(payments_router)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
