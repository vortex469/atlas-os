from fastapi import APIRouter, HTTPException

from app.services.proxmox_service import (
    get_proxmox_guests,
    get_proxmox_status,
)


router = APIRouter(
    prefix="/proxmox",
    tags=["Proxmox"],
)


@router.get("/status")
def proxmox_status():
    try:
        return get_proxmox_status()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@router.get("/guests")
def proxmox_guests():
    try:
        return get_proxmox_guests()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
