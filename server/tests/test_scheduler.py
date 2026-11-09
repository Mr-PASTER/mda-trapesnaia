from app.integrations.ldap.config import LdapSettings
from app.jobs.scheduler import create_scheduler
from app.services import ldap as ldap_service


def test_scheduler_has_daily_maintenance_job():
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    assert any(j.id == "daily_maintenance" for j in jobs)


def test_scheduler_adds_ldap_sync_when_enabled(monkeypatch):
    monkeypatch.setattr(
        ldap_service,
        "get_ldap_settings",
        lambda: LdapSettings(sync_enabled=True, sync_hour=4),
    )

    scheduler = create_scheduler()

    job = scheduler.get_job("ldap_sync")
    assert job is not None
    assert str(job.trigger) == "cron[hour='4', minute='59']"


def test_scheduler_skips_ldap_sync_by_default(monkeypatch):
    monkeypatch.setattr(ldap_service, "get_ldap_settings", lambda: LdapSettings())

    scheduler = create_scheduler()

    assert scheduler.get_job("ldap_sync") is None
