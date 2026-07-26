from dataclasses import dataclass

from app.schemas.plan import PlanRequest
from app.services.planner import build_sample_plan


@dataclass
class RoutePlannerAgent:
    def run(self, payload: PlanRequest) -> dict:
        return build_sample_plan(payload).model_dump()
