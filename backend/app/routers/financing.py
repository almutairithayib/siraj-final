import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.financing import FinancingRequest
from backend.app.schemas.financing import FinancingProductResponse, FinancingRequestCreate, FinancingRequestResponse
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/financing", tags=["Financing"])

# Mock financing products for MVP
FINANCING_PRODUCTS = [
    {
        "id": "prod_personal",
        "name": "التمويل الشخصي المتوافق مع الشريعة",
        "product_type": "personal",
        "profit_rate": 2.99,
        "min_amount": 10000.0,
        "max_amount": 250000.0,
        "min_term_months": 12,
        "max_term_months": 60,
        "description": "تمويل شخصي مرن بهامش ربح تنافسي وفترة سداد تصل إلى 5 سنوات، متوافق بالكامل مع أحكام الشريعة الإسلامية."
    },
    {
        "id": "prod_auto",
        "name": "تمويل السيارات (المرابحة)",
        "product_type": "auto",
        "profit_rate": 3.49,
        "min_amount": 30000.0,
        "max_amount": 500000.0,
        "min_term_months": 12,
        "max_term_months": 60,
        "description": "امتلك سيارة أحلامك بنظام المرابحة الإسلامية بأقساط ميسرة وسرعة في إتمام الإجراءات."
    },
    {
        "id": "prod_home",
        "name": "التمويل العقاري (الإجارة الموصوفة في الذمة)",
        "product_type": "home",
        "profit_rate": 4.19,
        "min_amount": 200000.0,
        "max_amount": 5000000.0,
        "min_term_months": 60,
        "max_term_months": 300,
        "description": "حلول تمويل عقاري متكاملة لشراء أرض أو فيلا أو شقة سكنية متوافقة مع ضوابط اللجنة الشرعية."
    },
    {
        "id": "prod_edu",
        "name": "تمويل التعليم بدون هامش ربح",
        "product_type": "education",
        "profit_rate": 0.00,
        "min_amount": 5000.0,
        "max_amount": 100000.0,
        "min_term_months": 6,
        "max_term_months": 24,
        "description": "تمويل مخصص للرسوم الدراسية للمدارس والجامعات بهامش ربح 0٪ لمساعدتك في الاستثمار في مستقبل أبنائك."
    },
    {
        "id": "prod_biz",
        "name": "تمويل المنشآت الصغيرة والمتوسطة",
        "product_type": "business",
        "profit_rate": 4.99,
        "min_amount": 50000.0,
        "max_amount": 2000000.0,
        "min_term_months": 12,
        "max_term_months": 48,
        "description": "ادعم نمو وتوسع شركتك الناشئة بتمويل متوافق مع أحكام الشريعة بالتعاون مع برنامج كفالة."
    }
]

@router.get("/products", response_model=List[FinancingProductResponse])
async def list_products(current_user: User = Depends(get_current_user)):
    return FINANCING_PRODUCTS

@router.post("/requests", response_model=FinancingRequestResponse, status_code=status.HTTP_201_CREATED)
async def submit_financing_request(
    request_in: FinancingRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify product_type matches one of our products
    valid_types = [p["product_type"] for p in FINANCING_PRODUCTS]
    if request_in.product_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع المنتج التمويلي غير صالح"
        )
        
    new_request = FinancingRequest(
        user_id=current_user.id,
        product_type=request_in.product_type,
        amount=request_in.amount,
        term_months=request_in.term_months,
        notes=request_in.notes,
        status="pending"
    )
    db.add(new_request)
    await db.commit()
    await db.refresh(new_request)
    return new_request

@router.get("/requests", response_model=List[FinancingRequestResponse])
async def list_user_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(FinancingRequest).where(FinancingRequest.user_id == current_user.id)
    )
    return result.scalars().all()

@router.get("/requests/{request_id}", response_model=FinancingRequestResponse)
async def get_request_details(
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(FinancingRequest).where(
            and_(FinancingRequest.id == request_id, FinancingRequest.user_id == current_user.id)
        )
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="طلب التمويل غير موجود"
        )
    return request
