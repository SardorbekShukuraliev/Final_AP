# backend/api/client.py
from fastapi import APIRouter, Depends, HTTPException, Query
from auth import require_role
from services.reservation import ReservationService, ConflictError, InsufficientIngredientsError
from services.menu_service import get_available_menu
from pydantic import BaseModel

router = APIRouter(dependencies=[Depends(require_role("client"))])

async def get_current_user(current_user = Depends(require_role("client"))):
    return current_user

@router.get("/tables")
async def get_free_tables(
    date: str = Query(...),
    start_time: str = Query(...),
    end_time: str = Query(...)
):
    tables = await ReservationService.get_free_tables(date, start_time, end_time)
    return tables

class HoldRequest(BaseModel):
    date: str
    start_time: str
    end_time: str

@router.post("/tables/{table_id}/hold")
async def hold_table(
    table_id: str,
    body: HoldRequest,
    current_user = Depends(get_current_user)
):
    try:
        result = await ReservationService.hold_table(
            table_id, current_user.username, body.date, body.start_time, body.end_time
        )
        return result
    except ConflictError as e:
        raise HTTPException(409, detail=str(e))
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

class ConfirmRequest(BaseModel):
    payment_success: bool = True
    card_number: str
    total_paid: int
    food_items: list = []

@router.post("/tables/{table_id}/confirm")
async def confirm_booking(
    table_id: str,
    body: ConfirmRequest,
    current_user = Depends(get_current_user)
):
    if not body.payment_success:
        raise HTTPException(402, "Payment failed")
    if len(body.card_number) != 16 or not body.card_number.isdigit():
        raise HTTPException(400, "Invalid card number")
    try:
        result = await ReservationService.confirm_reservation(
            table_id, current_user.username, True, body.food_items
        )
        return result
    except InsufficientIngredientsError as e:
        raise HTTPException(422, detail=str(e))
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

@router.post("/tables/{table_id}/cancel")
async def cancel_hold(
    table_id: str,
    current_user = Depends(get_current_user)
):
    try:
        penalty_info = await ReservationService.cancel_reservation(table_id, current_user.username)
        return penalty_info
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

@router.post("/tables/{table_id}/release")
async def release_table_hold(
    table_id: str,
    current_user = Depends(get_current_user)
):
    success = await ReservationService.release_hold(table_id, current_user.username)
    if not success:
        raise HTTPException(404, detail="No active hold to release")
    return {"status": "released"}

@router.get("/menu")
async def get_menu():
    return await get_available_menu()

@router.get("/reservations")
async def get_my_reservations(current_user = Depends(get_current_user)):
    return await ReservationService.get_user_reservations(current_user.username)

@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking_by_id(
    booking_id: int,
    current_user = Depends(get_current_user)
):
    try:
        penalty_info = await ReservationService.cancel_booking_by_id(booking_id, current_user.username)
        return penalty_info
    except ValueError as e:
        raise HTTPException(400, detail=str(e))