from typing import TypeVar# 泛型类型

from pydantic import BaseModel# Pydantic 模型类 = 用 Python 类定义的"数据模板"

from db import DBModelBase# 数据库模型类

# 先定义三种泛型（通用类型）, 用于在数据库操作的时候更加方便。
# ModelType: 数据库模型类的类型
# CreateSchema: 创建请求的Schema类型
# UpdateSchema: 更新请求的Schema类型
# 以便于在数据库操作的时候更加方便。
ModelType = TypeVar('ModelType', bound=DBModelBase)
CreateSchema = TypeVar('CreateSchema', bound=BaseModel)
UpdateSchema = TypeVar('UpdateSchema', bound=BaseModel)
#schema类型是Pydantic模型类的子类，用于定义请求和响应的模型。
# 例如，CreateSchema是用户创建请求的模型，UpdateSchema是用户更新请求的模型。

# 以便于在数据库操作的时候更加方便。

#ORM 转换基类 "翻译官"，把数据库语言翻译成 Python 语言，让数据库和 API 能沟通
class InDBMixin(BaseModel):
    """
    定义一个基类， 所有响应的模型的父类
    """

    class Config:
        # 有了这个配置，才能把ORM数据库模型类对象转化成Pydantic模型对象
        # orm_mode = True 老版本
        from_attributes = True

# SQLAlchemy ORM 对象（从数据库查出来的）
# user_db = User(name="张三", age=18)
# # Pydantic 模型（API 响应要用的）
# class UserResponse(BaseModel):
#     name: str
#     age: int

# # ❌ 直接这样转换会报错
# user_response = UserResponse(user_db)
# # ✅ 有了 from_attributes = True 就可以了！
# class UserResponse(InDBMixin):  # 继承 InDBMixin
#     name: str
#     age: int
# user_response = UserResponse.model_validate(user_db)  # ✅