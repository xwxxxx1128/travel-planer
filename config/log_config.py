#日志配置文件 ，负责设置项目的日志格式和输出！
from logging.config import dictConfig
from config import settings


def init_log():
    log_config = {
        'version': 1,
        'disable_existing_loggers': False,# 禁用已存在的日志记录器
        'formatters': {
            'sample': {'format': '%(asctime)s %(levelname)s %(message)s'},
            'verbose': {'format': '%(asctime)s %(levelname)s %(name)s %(process)d %(thread)d %(message)s'},
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            },
        },
        'handlers': {
            "console": {
                "formatter": 'verbose',
                'level': 'DEBUG',
                "class": "logging.StreamHandler",
            },
        },
        'loggers': {
            '': {'level': settings.LOG_LEVEL, 'handlers': ['console']},
        },
    }

    dictConfig(log_config)

# 级别 说明 什么时候用？
#  DEBUG 调试信息 开发时，打印所有细节 
#  INFO 一般信息 正常运行的信息
#  WARNING 警告信息 有问题，但不影响运行
#  ERROR 错误信息 出错了，部分功能不能用
#  CRITICAL 严重错误 严重错误，程序可能崩溃

# 注意： 若配置了 INFO 级别，就会输出 INFO 、 WARNING 、 ERROR 、 CRITICAL ，不会输出 DEBUG ！