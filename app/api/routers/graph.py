from fastapi import APIRouter

from app.graph.engine import get_graph_status

router = APIRouter()


@router.get('/status')
def graph_status():
    return get_graph_status()
