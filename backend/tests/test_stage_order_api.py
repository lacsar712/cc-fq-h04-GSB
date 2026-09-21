"""Read-order tests: both stage read endpoints must return stages ascending
and in the same order as the Actor chain (Parse → QualityHist → NContent → Report).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Job, JobStage
from app.pipeline.actors import ACTOR_CHAIN
from app.pipeline.runner import create_job_stages


CHAIN_NAMES = [cls.name for cls in ACTOR_CHAIN]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    job = Job(
        sample_id=None,
        sample_name="自定义输入",
        status="success",
        created_by="tester",
        fastq_snapshot="@A\nACGT\n+\nIIII\n",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    create_job_stages(db, job.id)

    yield db, job.id, TestingSession
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    _db, _job_id, TestingSession = db_session

    def _override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "tester",
        "role": "bioops",
    }
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_created_stage_orders_match_actor_chain(db_session):
    db, job_id, _ = db_session
    rows = (
        db.query(JobStage)
        .filter(JobStage.job_id == job_id)
        .order_by(JobStage.stage_order)
        .all()
    )
    assert [r.actor_name for r in rows] == CHAIN_NAMES
    assert [r.stage_order for r in rows] == list(range(len(ACTOR_CHAIN)))


def test_stages_endpoint_ascending_and_stable(client, db_session):
    _db, job_id, _s = db_session
    resp1 = client.get(f"/api/jobs/{job_id}/stages")
    resp2 = client.get(f"/api/jobs/{job_id}/stages")
    assert resp1.status_code == 200
    names1 = [s["actor_name"] for s in resp1.json()]
    orders1 = [s["stage_order"] for s in resp1.json()]
    assert names1 == CHAIN_NAMES
    assert orders1 == sorted(orders1) == [0, 1, 2, 3]
    # Refreshing the endpoint must give the same order
    assert [s["actor_name"] for s in resp2.json()] == names1
    assert [s["stage_order"] for s in resp2.json()] == orders1


def test_job_detail_embedded_stages_ascending_and_stable(client, db_session):
    _db, job_id, _s = db_session
    resp1 = client.get(f"/api/jobs/{job_id}")
    resp2 = client.get(f"/api/jobs/{job_id}")
    assert resp1.status_code == 200
    names1 = [s["actor_name"] for s in resp1.json()["stages"]]
    orders1 = [s["stage_order"] for s in resp1.json()["stages"]]
    assert names1 == CHAIN_NAMES
    assert orders1 == sorted(orders1) == [0, 1, 2, 3]
    assert [s["actor_name"] for s in resp2.json()["stages"]] == names1
    assert [s["stage_order"] for s in resp2.json()["stages"]] == orders1


def test_two_read_paths_agree(client, db_session):
    """Single-stage endpoint and embedded list in job detail must match each other."""
    _db, job_id, _s = db_session
    standalone = client.get(f"/api/jobs/{job_id}/stages").json()
    embedded = client.get(f"/api/jobs/{job_id}").json()["stages"]
    assert [s["actor_name"] for s in standalone] == [s["actor_name"] for s in embedded]
    assert [s["stage_order"] for s in standalone] == [
        s["stage_order"] for s in embedded
    ]
