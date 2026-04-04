# models/__init__.py
# Exposes all models from a single import point.
# Usage: from models import Job, Profile, AppConfig

from models.job import Job, JobSource, WorkMode, ApplicationStatus, CareerTrack, SalaryRange, TrackScore, TrackScores
from models.profile import Profile, Experience, Education, Certification
from models.config_schema import AppConfig
