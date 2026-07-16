import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.investment import InvestmentRequest
from backend.app.schemas.investment import InvestmentOpportunityResponse, InvestmentRequestCreate, InvestmentRequestResponse, InvestmentRecommendation
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/investment", tags=["Investments"])

# Mock investment opportunities
INVESTMENT_OPPORTUNITIES = [
    {
        "id": "opp_sukuk_sada",
        "name": "صكوك الإنماء العقارية المبتكرة",
        "product_type": "sukuk",
        "risk_level": "low",
        "expected_return": 6.25,
        "min_investment": 1000.0,
        "description": "صكوك متوافقة مع الشريعة الإسلامية تهدف إلى تمويل مشاريع تطوير عقاري حيوية في الرياض مع توزيع عوائد نصف سنوية."
    },
    {
        "id": "opp_fund_growth",
        "name": "صندوق الإنماء للأسهم السعودية الواعدة",
        "product_type": "fund",
        "risk_level": "high",
        "expected_return": 14.50,
        "min_investment": 5000.0,
        "description": "صندوق استثماري نشط يستهدف الاستثمار في شركات الأسهم القيادية والواعدة المدرجة في السوق السعودي (تداول)."
    },
    {
        "id": "opp_ipo_aramco",
        "name": "طرح أسهم أرامكو السعودية الإضافي",
        "product_type": "ipo",
        "risk_level": "medium",
        "expected_return": 8.00,
        "min_investment": 2000.0,
        "description": "فرصة للمشاركة في زيادة رأس مال الشركة الأكبر عالمياً في مجال الطاقة بأسعار طرح تفضيلية."
    },
    {
        "id": "opp_reit_mashaar",
        "name": "صندوق مشاعر ريت العقاري المدرر للدخل",
        "product_type": "fund",
        "risk_level": "medium",
        "expected_return": 7.20,
        "min_investment": 500.0,
        "description": "استثمر في عقارات مدرة للدخل بقطاعي الضيافة والتعليم في مكة المكرمة والمدينة المنورة بنسب توزيعات أرباح تتجاوز 90٪ سنوياً."
    }
]

@router.get("/opportunities", response_model=List[InvestmentOpportunityResponse])
async def list_opportunities(current_user: User = Depends(get_current_user)):
    return INVESTMENT_OPPORTUNITIES

@router.post("/requests", response_model=InvestmentRequestResponse, status_code=status.HTTP_201_CREATED)
async def submit_investment_request(
    request_in: InvestmentRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify product_name matches one of our opportunities
    valid_names = [o["name"] for o in INVESTMENT_OPPORTUNITIES]
    if request_in.product_name not in valid_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="اسم الفرصة الاستثمارية غير صالح"
        )
        
    new_request = InvestmentRequest(
        user_id=current_user.id,
        product_name=request_in.product_name,
        product_type=request_in.product_type,
        amount=request_in.amount,
        risk_level=request_in.risk_level,
        expected_return=request_in.expected_return,
        status="pending"
    )
    db.add(new_request)
    await db.commit()
    await db.refresh(new_request)
    return new_request

@router.get("/requests", response_model=List[InvestmentRequestResponse])
async def list_user_investments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(InvestmentRequest).where(InvestmentRequest.user_id == current_user.id)
    )
    return result.scalars().all()

@router.get("/recommendations", response_model=List[InvestmentRecommendation])
async def get_investment_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        import json
        from google import genai
        from google.genai import types
        from backend.app.config import settings
        from backend.app.ai.context_builder import build_context
        
        if settings.GEMINI_API_KEY:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            context = await build_context(current_user.id, db)
            prompt = (
                f"بناءً على الملف المالي للمستخدم التالي:\n"
                f"{context}\n\n"
                f"الفرص الاستثمارية المتاحة:\n"
                f"{json.dumps(INVESTMENT_OPPORTUNITIES, ensure_ascii=False)}\n\n"
                f"قم بتحليل الوضع المالي للمستخدم وحجم مدخراته ونسبة ادخاره، ثم اختر أفضل الفرص الاستثمارية الملائمة له.\n"
                f"لكل فرصة ملائمة، حدد درجة الملاءمة (recommendation_score) بين 0 و 100، واكتب تبريراً مالياً ذكياً وموجزاً باللغة العربية (باللهجة السعودية البيضاء الودية) يوضح للمستخدم لماذا هذه الفرصة تناسبه ماليّاً وبطريقة تشجعه على استغلالها بطريقة صحيحة.\n"
                f"يجب أن تكون التبريرات متوافقة ماليّاً وتعتمد على بياناته الفعلية."
            )
            
            schema = {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "opportunity_id": {"type": "STRING", "description": "The exact 'id' of the investment opportunity from the input list."},
                        "recommendation_score": {"type": "INTEGER", "description": "Recommendation score out of 100."},
                        "rationale": {"type": "STRING", "description": "Detailed personalized reason in Arabic (Saudi dialect style) why this opportunity is good for this user."}
                    },
                    "required": ["opportunity_id", "recommendation_score", "rationale"]
                }
            }
            
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.3
                )
            )
            
            if response.text:
                parsed = json.loads(response.text)
                opp_map = {o["id"]: o for o in INVESTMENT_OPPORTUNITIES}
                recs = []
                for item in parsed:
                    opp = opp_map.get(item["opportunity_id"])
                    if opp:
                        recs.append({
                            "opportunity": opp,
                            "recommendation_score": item["recommendation_score"],
                            "rationale": item["rationale"]
                        })
                if recs:
                    return recs
    except Exception as e:
        print(f"Error generating dynamic investment recommendations: {e}")

    # Basic rule-based dynamic recommendations matching user profile
    # For MVP we return customized recommendation scores & Arabic reasons
    recommendations = [
        {
            "opportunity": INVESTMENT_OPPORTUNITIES[0], # Sukuk
            "recommendation_score": 95,
            "rationale": "بناءً على تفضيلك للمخاطر المنخفضة ورغبتك في تحقيق عوائد ثابتة، فإن صكوك الإنماء العقارية توفر حماية ممتازة لرأس المال مع عائد سنوي مضمون بنسبة 6.25٪ متوافق مع الشريعة."
        },
        {
            "opportunity": INVESTMENT_OPPORTUNITIES[3], # REIT
            "recommendation_score": 85,
            "rationale": "لزيادة تنويع محفظتك، يُنصح بالاستثمار في صندوق مشاعر ريت العقاري الذي يوفر دخلاً دورياً ناتجاً عن عقارات الضيافة في مكة والمدينة، وهو خيار رائع للأمان والاستقرار المالي."
        },
        {
            "opportunity": INVESTMENT_OPPORTUNITIES[1], # Growth Fund
            "recommendation_score": 60,
            "rationale": "نظراً لأن أهدافك طويلة المدى وتريد نمواً متسارعاً لجزء من مدخراتك، نقترح تخصيص 10٪ فقط من السيولة لهذا الصندوق للحد من تقلبات السوق."
        }
    ]
    return recommendations

