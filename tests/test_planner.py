from app.services.planner import build_sample_plan
from app.schemas.plan import PlanRequest


def test_build_sample_plan():
    result = build_sample_plan(PlanRequest(destinations=['A', 'B', 'C'], travel_days=2))
    assert result.trip_name == '智能行程'
    assert len(result.days) == 2
    assert result.days[0].items[0].name == 'A'
