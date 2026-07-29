from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.analysis_service import analysis_service


class SchedulerManager:
    def __init__(self) -> None:
        tz = ZoneInfo(settings.timezone)
        self.scheduler = BackgroundScheduler(timezone=tz)

    def start(self) -> None:
        self.scheduler.add_job(
            analysis_service.generate,
            trigger=CronTrigger(
                hour=settings.daily_report_hour,
                minute=settings.daily_report_minute,
                timezone=settings.timezone,
            ),
            id="daily_report",
            replace_existing=True,
        )

        self.scheduler.add_job(
            analysis_service.generate,
            trigger=CronTrigger(
                hour=f"{settings.update_start_hour}-{settings.update_end_hour}",
                minute=settings.update_minute,
                timezone=settings.timezone,
            ),
            id="hourly_updates",
            replace_existing=True,
        )

        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)


scheduler_manager = SchedulerManager()
