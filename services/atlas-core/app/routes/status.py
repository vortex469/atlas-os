from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def root():
    return {
        "atlas": "online",
        "assistant": "Orion",
        "engine": "Hermes",
        "release": "Foundry",
    }
