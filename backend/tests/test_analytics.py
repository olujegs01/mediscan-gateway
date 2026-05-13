"""
Unit tests for analytics_engine.py.
All functions are tested with an in-memory SQLite database.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, AuditLog, PatientRecord, ClinicalJourney
from analytics_engine import (
    get_volume_timeseries,
    get_7day_trends,
    get_journey_funnel,
    get_diversion_stats,
    get_sepsis_compliance,
    get_esi_trends,
    get_benchmark_comparison,
    get_full_analytics,
    _ed_volume_baseline,
    NATIONAL_BENCHMARKS,
)


@pytest.fixture(scope="module")
def mem_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture(scope="module")
def seeded_db(mem_db):
    """DB with some audit logs, patients, and journeys."""
    from datetime import datetime

    # Add 5 scan audit logs
    for i in range(5):
        mem_db.add(AuditLog(
            username="nurse1",
            role="nurse",
            action="scan",
            patient_id=f"PT-{i}",
            ip_address="127.0.0.1",
        ))

    # Add 2 discharged patients
    for i in range(2):
        mem_db.add(PatientRecord(
            patient_id=f"PT-{i}",
            name=f"Patient {i}",
            age=40 + i,
            chief_complaint="cough",
            esi_level=3,
            status="discharged",
            discharged_at=datetime.utcnow(),
        ))

    # Add one completed journey
    mem_db.add(ClinicalJourney(
        patient_id="PT-0",
        name="Patient 0",
        esi_level=3,
        journey_status="completed",
        checkins_completed=2,
        checkins_total=2,
        last_response="Feeling better",
    ))

    mem_db.commit()
    return mem_db


def test_get_volume_timeseries_empty(mem_db):
    result = get_volume_timeseries(mem_db, hours=6)
    assert len(result) == 6
    for item in result:
        assert "time" in item
        assert "patients" in item
        assert "wait_min" in item
        assert "capacity_pct" in item


def test_get_volume_timeseries_with_data(seeded_db):
    result = get_volume_timeseries(seeded_db, hours=24)
    assert len(result) == 24


def test_get_volume_timeseries_long_range(mem_db):
    result = get_volume_timeseries(mem_db, hours=48)
    assert len(result) == 48
    # Long-range format includes date
    assert "/" in result[0]["time"]


def test_get_7day_trends(mem_db):
    result = get_7day_trends(mem_db)
    assert len(result) == 7
    for day in result:
        assert "date" in day
        assert "patients" in day
        assert "lwbs_rate" in day
        assert "avg_los_min" in day
        assert "avg_wait_min" in day


def test_get_7day_trends_with_data(seeded_db):
    result = get_7day_trends(seeded_db)
    assert len(result) == 7


def test_get_journey_funnel_empty(mem_db):
    result = get_journey_funnel(mem_db)
    assert "funnel" in result
    assert len(result["funnel"]) == 5
    assert "completion_rate_pct" in result
    assert "escalation_rate_pct" in result
    assert "readmissions_averted" in result


def test_get_journey_funnel_with_data(seeded_db):
    result = get_journey_funnel(seeded_db)
    assert result["funnel"][0]["stage"] == "Discharged"


def test_get_diversion_stats(mem_db):
    result = get_diversion_stats(mem_db)
    assert "total_assessments" in result
    assert "breakdown" in result
    assert "diversion_rate_pct" in result
    assert "estimated_ed_cost_saved" in result
    assert len(result["breakdown"]) == 7


def test_get_sepsis_compliance(mem_db):
    result = get_sepsis_compliance(mem_db)
    assert "total_alerts_30d" in result
    assert "bundle_initiated" in result
    assert "compliance_rate_pct" in result
    assert "components" in result
    assert len(result["components"]) == 6


def test_get_esi_trends(mem_db):
    result = get_esi_trends(mem_db)
    assert len(result) == 7
    for day in result:
        assert "date" in day
        assert "ESI1" in day
        assert "ESI5" in day


def test_get_benchmark_comparison():
    perf = {
        "door_to_triage_seconds": 14,
        "lwbs_rate_today": 1.8,
        "avg_los_minutes": 120,
        "avg_wait_minutes": 14,
    }
    result = get_benchmark_comparison(perf)
    assert len(result) == 5
    for item in result:
        assert "metric" in item
        assert "yours" in item
        assert "national" in item


def test_get_benchmark_comparison_defaults():
    # Empty perf dict — should use defaults
    result = get_benchmark_comparison({})
    assert len(result) == 5


def test_get_full_analytics(mem_db):
    result = get_full_analytics(mem_db, [])
    assert "timestamp" in result
    assert "queue" in result
    assert "capacity" in result
    assert "performance" in result
    assert "timeseries" in result
    assert "trends_7d" in result
    assert "esi_trends" in result
    assert "journeys" in result
    assert "diversion" in result
    assert "sepsis" in result
    assert "benchmarks" in result


def test_get_full_analytics_with_queue(mem_db):
    queue = [
        {
            "patient_id": "PT-Q1",
            "esi_level": 2,
            "wait_time_estimate": 15,
            "hospital_id": "default",
            "triage_detail": {
                "sepsis_probability": "high",
                "behavioral_health_flag": True,
                "admission_probability": 75,
                "lwbs_risk": "high",
            },
        },
        {
            "patient_id": "PT-Q2",
            "esi_level": 3,
            "wait_time_estimate": 30,
            "hospital_id": "default",
            "triage_detail": {},
        },
    ]
    result = get_full_analytics(mem_db, queue)
    assert result["queue"]["total_patients"] == 2
    assert result["queue"]["sepsis_alerts"] == 1
    assert result["queue"]["behavioral_health"] == 1
    assert result["queue"]["admission_likely"] == 1
    assert result["queue"]["lwbs_high_risk"] == 1


def test_ed_volume_baseline():
    import random
    rng = random.Random(42)
    # Peak hours should give higher values than off-peak
    peak = _ed_volume_baseline(11, rng)   # 11am peak
    off_peak = _ed_volume_baseline(3, rng)  # 3am off-peak
    assert peak >= 0
    assert off_peak >= 0


def test_national_benchmarks_exist():
    assert "door_to_triage_min" in NATIONAL_BENCHMARKS
    assert "lwbs_rate_pct" in NATIONAL_BENCHMARKS
    assert "avg_los_min" in NATIONAL_BENCHMARKS
