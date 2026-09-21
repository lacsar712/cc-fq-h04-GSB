"""Stage ordering: create writes ascending stage_order and every read path
returns stages in Actor-chain order (Parse → QualityHist → NContent → Report).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.StageOrderPolicy import create_order_index, order_stages
from app.StageOrderSerializer import stages_for_response
from app.api import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models import Job, JobStage
from app.pipeline.actors import ACTOR_CHAIN
from app.pipeline.runner import create_job_stages

CHAIN_NAMES = [cls.name for cls in ACTOR_CHAIN]
CHAIN_ORDERS = list(range(len(ACTOR_CHAIN)))


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture()
def db_session(session_factory):
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(session_factory):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    token = create_access_token("auditor", "auditor")
    return {"Authorization": f"Bearer {token}"}


def _make_job_with_stages(db) -> Job:
    job = Job(
        sample_id=None,
        sample_name="单测样例",
        status="pending",
        created_by="bioops",
        fastq_snapshot="@A\nACGT\n+\nIIII\n",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    create_job_stages(db, job.id)
    return job


def test_create_order_index_is_ascending_identity():
    assert [create_order_index(4, i) for i in range(4)] == [0, 1, 2, 3]


def test_order_stages_ascending():
    class _S:
        def __init__(self, name, order):
            self.actor_name = name
            self.stage_order = order

    rows = [
        _S("ReportActor", 3),
        _S("ParseActor", 0),
        _S("NContentActor", 2),
        _S("QualityHistActor", 1),
    ]
    assert [s.actor_name for s in order_stages(rows)] == CHAIN_NAMES
    assert [s.actor_name for s in stages_for_response(rows)] == CHAIN_NAMES


def test_create_job_stages_matches_actor_chain(db_session):
    job = _make_job_with_stages(db_session)
    rows = (
        db_session.query(JobStage)
        .filter(JobStage.job_id == job.id)
        .order_by(JobStage.stage_order)
        .all()
    )
    assert [s.stage_order for s in rows] == CHAIN_ORDERS
    assert [s.actor_name for s in rows] == CHAIN_NAMES


def test_job_detail_stages_follow_actor_chain(client, db_session, auth_headers):
    job = _make_job_with_stages(db_session)
    resp = client.get(f"/api/jobs/{job.id}", headers=auth_headers)
    assert resp.status_code == 200
    stages = resp.json()["stages"]
    assert [s["actor_name"] for s in stages] == CHAIN_NAMES
    assert [s["stage_order"] for s in stages] == CHAIN_ORDERS


def test_job_stages_endpoint_follows_actor_chain(client, db_session, auth_headers):
    job = _make_job_with_stages(db_session)
    resp = client.get(f"/api/jobs/{job.id}/stages", headers=auth_headers)
    assert resp.status_code == 200
    stages = resp.json()
    assert [s["actor_name"] for s in stages] == CHAIN_NAMES
    assert [s["stage_order"] for s in stages] == CHAIN_ORDERS


def test_both_read_paths_stable_across_refreshes(client, db_session, auth_headers):
    job = _make_job_with_stages(db_session)
    for _ in range(2):
        detail = client.get(f"/api/jobs/{job.id}", headers=auth_headers).json()["stages"]
        listing = client.get(f"/api/jobs/{job.id}/stages", headers=auth_headers).json()
        assert [s["actor_name"] for s in detail] == CHAIN_NAMES
        assert [s["actor_name"] for s in listing] == CHAIN_NAMES
