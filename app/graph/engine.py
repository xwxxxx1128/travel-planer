from app.graph.agents.route_planner import RoutePlannerAgent
from app.graph.agents.lodging import LodgingAgent
from app.graph.agents.review_rag import ReviewRAGAgent
from app.graph.agents.store_agent import TravelStoreAgent
from app.schemas.plan import PlanRequest, TravelPlanResponse
from app.services.planner import build_sample_plan

_graph_state = {'built': False}
_route_agent = RoutePlannerAgent()
_lodging_agent = LodgingAgent()
_review_agent = ReviewRAGAgent()
_store_agent = TravelStoreAgent()


def build_graph() -> dict:
    _graph_state['built'] = True
    return _graph_state


def run_travel_graph(payload: PlanRequest) -> dict:
    plan = build_sample_plan(payload).model_dump()
    plan['hotel_suggestions'] = _lodging_agent.run(payload)
    plan['review_snippets'] = _review_agent.run(payload)
    plan['store_preview'] = _store_agent.run(payload, plan)
    return plan


def get_graph_status() -> dict:
    return {
        'built': _graph_state['built'],
        'agents': ['route_planner', 'lodging', 'review_rag', 'store'],
    }
