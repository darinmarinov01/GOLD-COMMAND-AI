from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.analysis_service import analysis_service

router = APIRouter(prefix="/api/v1", tags=["analysis"])


class PriceOverrideRequest(BaseModel):
    price: float = Field(..., gt=0)
    source: str = "manual_override"


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/analysis/latest")
def analysis_latest():
    return analysis_service.latest()


@router.post("/analysis/generate")
def analysis_generate():
    return analysis_service.generate()


@router.post("/price/override")
def set_price_override(payload: PriceOverrideRequest):
    analysis_service.set_price_override(price=payload.price, source=payload.source)
    return {
        "status": "ok",
        "message": "Price override set",
        "price": round(payload.price, 2),
        "source": payload.source,
    }


@router.delete("/price/override")
def clear_price_override():
    analysis_service.clear_price_override()
    return {"status": "ok", "message": "Price override cleared"}


@router.get("/providers/status")
def providers_status(probe: bool = False):
    return analysis_service.provider_status(probe=probe)
