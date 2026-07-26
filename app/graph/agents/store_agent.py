from dataclasses import dataclass

from app.schemas.plan import PlanRequest


@dataclass
class TravelStoreAgent:
    def run(self, payload: PlanRequest, plan: dict) -> dict:
        return {
            'saved': True,
            'trip_name': payload.trip_name,
            'destination_count': len(payload.destinations),
            'summary': plan.get('summary', ''),
        }
