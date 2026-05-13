from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, PatientRecord


def test_patient_record_crud():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    p = PatientRecord(patient_id="p1", name="Bob", age=45, chief_complaint="fever")
    session.add(p)
    session.commit()
    got = session.query(PatientRecord).filter_by(patient_id="p1").first()
    assert got is not None
    assert got.name == "Bob"
    session.close()
