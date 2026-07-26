from fastapi import APIRouter

from app.schemas.pois import POIResponse, HotelResponse, RestaurantResponse, ReviewResponse

router = APIRouter()


@router.get('/pois', response_model=list[POIResponse])
def list_pois():
    return [POIResponse(id=1, name='外滩', city='上海', address='上海市黄浦区', lat=31.24, lng=121.49, tags='地标|风景', description='经典城市景观')]


@router.get('/hotels', response_model=list[HotelResponse])
def list_hotels():
    return [HotelResponse(id=1, name='景区旁舒适酒店', rating=4.8, price_level=3, tags='亲子友好|近地铁', address='景区附近', note='评论高分')]


@router.get('/restaurants', response_model=list[RestaurantResponse])
def list_restaurants():
    return [RestaurantResponse(id=1, name='本地特色餐馆', rating=4.7, price_level=2, cuisine='本帮菜', tags='家常菜|排队少', note='适合家庭')]


@router.get('/reviews', response_model=list[ReviewResponse])
def list_reviews():
    return [ReviewResponse(id=1, poi_name='外滩', source='crawler', rating=4.9, label='推荐', content='适合夜景与拍照')]
