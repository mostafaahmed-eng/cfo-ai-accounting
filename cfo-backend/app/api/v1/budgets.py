from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.budget import Budget, BudgetLine
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetResponse, BudgetUpdate
from app.schemas.pagination import PageParams, get_page_params

router = APIRouter()


@router.get("", response_model=list[BudgetResponse])
async def list_budgets(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
):
    filters = (Budget.company_id == company_id,)
    total = await db.scalar(select(func.count()).select_from(Budget).where(*filters))
    result = await db.execute(
        select(Budget)
        .where(*filters)
        .order_by(Budget.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
    )
    budgets = result.scalars().all()
    response.headers["X-Total-Count"] = str(total)
    response_budgets = []
    for budget in budgets:
        await db.refresh(budget, ["lines"])
        response_budgets.append(BudgetResponse.model_validate(budget))
    return response_budgets


@router.post("", response_model=BudgetResponse)
async def create_budget(
    data: BudgetCreate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    budget = Budget(
        id=uuid4(),
        company_id=company_id,
        name=data.name,
        period_type=data.period_type,
        start_date=data.start_date,
        end_date=data.end_date,
        currency=data.currency,
        status="draft",
        created_by=str(user.id),
    )
    db.add(budget)
    await db.flush()

    for line in data.lines:
        db.add(
            BudgetLine(
                id=uuid4(),
                budget_id=str(budget.id),
                account_id=str(line.account_id),
                planned_amount=line.planned_amount,
                alert_percentage=line.alert_percentage,
            )
        )
    await db.flush()

    await db.refresh(budget, ["lines"])
    return BudgetResponse.model_validate(budget)


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.company_id == company_id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    await db.refresh(budget, ["lines"])
    return BudgetResponse.model_validate(budget)


@router.patch("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str,
    data: BudgetUpdate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.company_id == company_id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status == "closed":
        raise HTTPException(status_code=400, detail="Cannot edit closed budget")
    if data.name is not None:
        budget.name = data.name
    if data.status is not None:
        budget.status = data.status
    if data.lines is not None:
        for old_line in budget.lines:
            await db.delete(old_line)
        for line in data.lines:
            db.add(
                BudgetLine(
                    id=uuid4(),
                    budget_id=str(budget.id),
                    account_id=str(line.account_id),
                    planned_amount=line.planned_amount,
                    alert_percentage=line.alert_percentage,
                )
            )
    await db.flush()
    await db.refresh(budget, ["lines"])
    return BudgetResponse.model_validate(budget)


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.company_id == company_id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status == "active":
        raise HTTPException(
            status_code=400, detail="Cannot delete active budget. Close it first."
        )
    await db.delete(budget)
    await db.flush()
    return {"message": "Budget deleted"}
