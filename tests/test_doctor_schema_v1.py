import json
from pathlib import Path
from hermes_forge.collectors.doctor import collect_doctor_report_evidence

def test_system_doctor_010_nested_checks_are_counted(tmp_path):
    fixture=Path(__file__).parent/'fixtures/doctor/v0.1.0-report.json'
    result=collect_doctor_report_evidence(fixture,tmp_path)
    assert 'status=WARN, findings=2' in result[0].fact
    assert 'Synthetic missing evidence' not in result[0].fact

def test_nonobject_doctor_report_is_unparseable_not_crash(tmp_path):
    report=tmp_path/'report.json'; report.write_text('[]')
    result=collect_doctor_report_evidence(report,tmp_path)
    assert 'unparseable_json' in result[0].fact
