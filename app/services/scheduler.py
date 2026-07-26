try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover
    BackgroundScheduler = None

_scheduler = BackgroundScheduler(timezone='Asia/Shanghai') if BackgroundScheduler else None
_started = False


def start_scheduler() -> None:
    global _started
    if _started or _scheduler is None:
        return
    if not _scheduler.get_jobs():
        _scheduler.add_job(lambda: None, 'interval', minutes=60, id='crawler_refresh', replace_existing=True)
    _scheduler.start()
    _started = True


def shutdown_scheduler() -> None:
    global _started
    if _started and _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _started = False
