"""
Life Management System — Time Tracker + People CRM + Health + Mind.
Mierzysz każdą minutę. Zarządzasz 50 relacjami. Nigdy nie zapominasz.
"""

from .schema import init_db, get_db
from .time_tracker import TimeTracker
from .people_crm import PeopleCRM
from .reporter import Reporter

__version__ = "0.1.0"
__all__ = ["init_db", "get_db", "TimeTracker", "PeopleCRM", "Reporter"]
