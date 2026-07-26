import json
import redis
from typing import Optional, Any
from functools import wraps
from config import settings


class RedisCache:
    """Redis缓存工具类"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存"""
        try:
            json_value = json.dumps(value, ensure_ascii=False)
            return self.redis_client.setex(key, expire, json_value)
        except Exception as e:
            print(f"Redis set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            return self.redis_client.delete(key) > 0
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            print(f"Redis exists error: {e}")
            return False


# 全局缓存实例
cache = RedisCache()


def cache_result(key_prefix: str, expire: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{str(args)}:{str(kwargs)}"
            
            # 尝试从缓存获取
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator
