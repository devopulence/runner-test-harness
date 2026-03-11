"""
GitHub Actions Monitoring Module

Collects, stores, and analyzes GitHub Actions workflow and runner metrics
for capacity planning and performance monitoring.
"""

from .storage import DailyStatsStore, StatsRecord
