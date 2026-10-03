from app.jobs.scheduler import create_scheduler


def test_scheduler_has_daily_maintenance_job():
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    assert any(j.id == "daily_maintenance" for j in jobs)
