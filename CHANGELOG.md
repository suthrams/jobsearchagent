# Changelog

All notable changes are documented here, grouped by date.

---

## 2026-04-15

### Fixed
- Replace deprecated `datetime.utcnow()` with `datetime.now(tz=timezone.utc)` across all files — `utcnow()` is deprecated in Python 3.12 and emits `DeprecationWarning` on Python 3.13 (`dashboard.py`, `main.py`, `models/profile.py`, `storage/db.py`, `tests/test_adzuna_scraper.py`, `tests/test_db.py`)
- Replace deprecated Pydantic v2 inner `class Config` with `model_config = ConfigDict(...)` in `models/job.py` and `models/profile.py`
