from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select

from ..core.security import create_qr_token
from ..dependencies import CurrentUser, DbSession, require_roles
from ..models import ParkingSession, ParkingSessionStatus, ParkingSlot, ParkingZone, SlotStatus, User, UserRole
from ..schemas.resources import SlotCreate, SlotQRResponse, SlotRead, SlotUpdate
from ..services.audit import record_audit
from ..services.qr import qr_png_base64, qr_png_bytes


router = APIRouter(prefix="/api", tags=["slots"])
AdminUser = Depends(require_roles(UserRole.ADMIN))


def _slot_or_404(db: DbSession, slot_id: int) -> ParkingSlot:
    slot = db.get(ParkingSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Parking slot not found")
    return slot


@router.post("/zones/{zone_id}/slots", response_model=SlotRead, status_code=status.HTTP_201_CREATED)
def create_slot(zone_id: int, data: SlotCreate, db: DbSession, admin: User = AdminUser) -> ParkingSlot:
    zone = db.get(ParkingZone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Parking zone not found")
    count = int(db.scalar(select(func.count(ParkingSlot.id)).where(ParkingSlot.zone_id == zone_id)) or 0)
    if count >= zone.capacity:
        raise HTTPException(status_code=409, detail="Zone slot capacity has been reached")
    duplicate = db.scalar(
        select(ParkingSlot.id).where(
            ParkingSlot.zone_id == zone_id, ParkingSlot.slot_code == data.slot_code
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Slot code already exists in this zone")
    slot = ParkingSlot(zone_id=zone_id, **data.model_dump())
    db.add(slot)
    db.flush()
    record_audit(db, actor_user_id=admin.id, action="CREATE", entity_type="slot", entity_id=slot.id)
    db.commit()
    db.refresh(slot)
    return slot


@router.get("/zones/{zone_id}/slots", response_model=list[SlotRead])
def list_slots(zone_id: int, user: CurrentUser, db: DbSession) -> list[ParkingSlot]:
    if not db.get(ParkingZone, zone_id):
        raise HTTPException(status_code=404, detail="Parking zone not found")
    return list(db.scalars(select(ParkingSlot).where(ParkingSlot.zone_id == zone_id).order_by(ParkingSlot.slot_code)))


@router.put("/slots/{slot_id}", response_model=SlotRead)
def update_slot(slot_id: int, data: SlotUpdate, db: DbSession, admin: User = AdminUser) -> ParkingSlot:
    slot = _slot_or_404(db, slot_id)
    values = data.model_dump(exclude_unset=True)
    active = db.scalar(
        select(ParkingSession.id).where(
            ParkingSession.slot_id == slot.id,
            ParkingSession.status == ParkingSessionStatus.ACTIVE,
        ).limit(1)
    )
    if active and values.get("status", slot.status) != SlotStatus.OCCUPIED:
        raise HTTPException(status_code=409, detail="An active session occupies this slot")
    if not active and values.get("status") == SlotStatus.OCCUPIED:
        raise HTTPException(status_code=409, detail="Slots become occupied only through parking entry")
    for key, value in values.items():
        setattr(slot, key, value)
    record_audit(db, actor_user_id=admin.id, action="UPDATE", entity_type="slot", entity_id=slot.id)
    db.commit()
    db.refresh(slot)
    return slot


@router.post("/slots/{slot_id}/qr", response_model=SlotQRResponse)
def generate_slot_qr(slot_id: int, db: DbSession, admin: User = AdminUser) -> SlotQRResponse:
    slot = _slot_or_404(db, slot_id)
    token = create_qr_token(str(slot.id), "slot_qr")
    slot.qr_code_value = token
    record_audit(db, actor_user_id=admin.id, action="GENERATE_QR", entity_type="slot", entity_id=slot.id)
    db.commit()
    return SlotQRResponse(slot_id=slot.id, qr_token=token, png_base64=qr_png_base64(token))


@router.get("/slots/{slot_id}/qr.png")
def download_slot_qr(slot_id: int, user: CurrentUser, db: DbSession) -> Response:
    slot = _slot_or_404(db, slot_id)
    token = slot.qr_code_value or create_qr_token(str(slot.id), "slot_qr")
    return Response(
        qr_png_bytes(token),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="slot-{slot.slot_code}.png"'},
    )


@router.get("/slots/{slot_id}/status", response_model=SlotRead)
def slot_status(slot_id: int, user: CurrentUser, db: DbSession) -> ParkingSlot:
    return _slot_or_404(db, slot_id)
