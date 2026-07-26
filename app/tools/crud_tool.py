from dataclasses import dataclass


@dataclass
class TravelDatabaseTool:
    """统一 CRUD 入口；后续可替换为完整 DAO 层。"""

    def save_itinerary(self, payload: dict) -> dict:
        return {'saved': True, 'payload': payload}
