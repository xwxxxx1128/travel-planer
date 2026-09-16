from pydantic import BaseModel, Field


class CompleteOrEscalate(BaseModel):  # 定义数据模型类
    """
    一个工具，用于标记当前任务为已完成和/或将对话的控制权升级到主助理，
    主助理可以根据用户的需求重新路由对话。
    """

    cancel: bool = True  # 默认取消任务
    reason: str  # 取消或升级的原因说明

    class Config:  # 内部类 Config: json_schema_extra: 这个字段包含了一些示例数据
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "用户改变了对当前任务的想法。",
            },
            "example2": {
                "cancel": True,
                "reason": "我已经完成了任务。",
            },
            "example3": {
                "cancel": False,
                "reason": "我需要搜索用户的电子邮件或日历以获取更多信息。",
            },
        }


class ToFlightBookingAssistant(BaseModel):
    """
    将工作转交给专门处理航班查询，更新和取消的助理。
    """

    request: str = Field(
        description="更新航班助理在继续之前需要澄清的任何后续问题。"
    )


class ToHotelBookingAssistant(BaseModel):
    """
    将工作转交给专门处理酒店预订的助理。
    """

    location: str = Field(
        description="用户想要预订酒店的位置。"
    )
    checkin_date: str = Field(description="酒店入住日期。")
    checkout_date: str = Field(description="酒店退房日期。")
    request: str = Field(
        description="用户关于酒店预订的任何额外信息或请求。"
    )

    class Config:
        json_schema_extra = {
            "示例": {
                "location": "苏黎世",
                "checkin_date": "2023-08-15",
                "checkout_date": "2023-08-20",
                "request": "我偏好靠近市中心且房间有景观的酒店。",
            }
        }


class ToTravelList(BaseModel):
    """
    将工作转交给专门处理「旅行清单」的助理：为用户的旅行清单推荐景点，
    并支持把景点加入 / 移出清单、查看清单。
    """

    location: str = Field(
        description="用户想要获取景点推荐的城市或目的地。"
    )
    request: str = Field(
        description="用户关于景点推荐或旅行清单的任何额外信息或请求。"
    )

    class Config:
        json_schema_extra = {
            "示例": {
                "location": "成都",
                "request": "用户想看看有什么好玩的景点，并挑几个加入旅行清单。",
            }
        }
