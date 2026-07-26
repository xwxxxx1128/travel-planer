from dataclasses import dataclass

from app.schemas.plan import PlanRequest


@dataclass
class LodgingAgent:
    def run(self, payload: PlanRequest) -> list[dict]:
        city = payload.city or '目的地'
        return [
            {'name': f'{city} 景区酒店', 'rating': 4.8, 'price_level': 3, 'tags': '亲子友好|近景区'},
            {'name': f'{city} 轻奢酒店', 'rating': 4.6, 'price_level': 4, 'tags': '安静|早餐好'},
        ]
