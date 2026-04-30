from models import PatientScanRequest


def test_patient_scan_request():
    data = {"name": "Alice", "age": 30, "chief_complaint": "cough"}
    req = PatientScanRequest(**data)
    assert req.name == "Alice"
    assert req.age == 30
    assert req.chief_complaint == "cough"
    assert req.wristband_id is None
