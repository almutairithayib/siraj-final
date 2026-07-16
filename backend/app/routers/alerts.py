import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, func

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.alert import Alert
from backend.app.schemas.alert import AlertCreate, AlertResponse, AlertUnreadCountResponse
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == current_user.id)
        .order_by(Alert.created_at.desc())
    )
    return result.scalars().all()

@router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_alert(
    alert_in: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_alert = Alert(
        user_id=current_user.id,
        alert_type=alert_in.alert_type,
        category=alert_in.category,
        threshold_amount=alert_in.threshold_amount,
        message=alert_in.message,
        is_read=False,
        is_active=alert_in.is_active
    )
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)
    return new_alert

@router.put("/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_as_read(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Alert).where(
            and_(Alert.id == alert_id, Alert.user_id == current_user.id)
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="التنبيه غير موجود"
        )
        
    alert.is_read = True
    await db.commit()
    await db.refresh(alert)
    return alert

@router.get("/unread-count", response_model=AlertUnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(func.count(Alert.id)).where(
            and_(Alert.user_id == current_user.id, Alert.is_read == False)
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}
