from fastapi import APIRouter, Depends, HTTPException

from app.schemas.plan import PlanRequest, TravelPlanResponse
from app.graph.engine import run_travel_graph

router = APIRouter()


@router.post('/plan', response_model=TravelPlanResponse)
def create_plan(payload: PlanRequest):
    return TravelPlanResponse.model_validate(run_travel_graph(payload))


@router.get('/plan/demo', response_model=TravelPlanResponse)
def demo_plan():
    return create_plan(PlanRequest(destinations=['外滩', '豫园', '东方明珠'], travel_days=1, preference='省时'))
