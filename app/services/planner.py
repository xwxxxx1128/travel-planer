from datetime import datetime, timedelta
from math import ceil

from app.schemas.plan import PlanRequest, TravelPlanResponse, PlanResponse, DayPlanItem


def build_sample_plan(payload: PlanRequest) -> TravelPlanResponse:
    destinations = payload.destinations or ['城市地标', '博物馆', '特色街区']
    if not destinations:
        destinations = ['城市地标', '博物馆', '特色街区']

    sorted_destinations = destinations[:]
    days = []
    cursor = 0
    per_day = max(1, ceil(len(sorted_destinations) / payload.travel_days))

    for day_index in range(1, payload.travel_days + 1):
        chunk = sorted_destinations[cursor:cursor + per_day]
        cursor += per_day
        if not chunk:
            chunk = [f'休闲安排 {day_index}']
        items = []
        base_hour = 9
        for idx, name in enumerate(chunk):
            hour = base_hour + idx * 3
            items.append(DayPlanItem(
                time=f'{hour:02d}:00',
                name=name,
                category='scenic',
                transport_mode='步行/公交/驾车',
                distance_km=round(1.2 + idx * 0.8, 1),
                duration_min=60 + idx * 20,
                note=f'结合{payload.preference}优先级自动排序',
            ))
        days.append(PlanResponse(
            day_index=day_index,
            title=f'第{day_index}天行程',
            items=items,
            meals=['早餐 08:00', '午餐 12:00', '晚餐 18:30'],
            note='预留午休与晚间返程缓冲',
        ))

    summary = f'已为{payload.trip_name}生成{payload.travel_days}天行程，偏好：{payload.preference}。'
    return TravelPlanResponse(
        itinerary_id=None,
        trip_name=payload.trip_name,
        preference=payload.preference,
        summary=summary,
        days=days,
        hotel_suggestions=[{'name': '景区旁舒适酒店', 'rating': 4.8, 'tags': '亲子友好|近地铁'}],
        restaurant_suggestions=[{'name': '本地特色餐馆', 'rating': 4.7, 'tags': '家常菜|排队少'}],
        review_snippets=[{'poi_name': destinations[0], 'content': '评论摘要：适合亲子与打卡。'}],
        transport_summary=[{'from': '起点', 'to': destinations[0], 'mode': '驾车', 'distance_km': 3.2, 'duration_min': 18}],
    )
