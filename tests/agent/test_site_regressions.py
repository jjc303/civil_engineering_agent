from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.main import create_app
from agent.db.base import Database
from agent.db.models import CameraStatusModel, CameraConfigModel, TrainingTaskModel, TrainingSubmissionModel, SafetyReportModel
from agent.services.camera_management import CameraManagementService
from agent.services.learning_service import LearningService


def test_unconfigured_known_camera_is_readable_without_publishing_a_boundary():
    app = create_app(Settings(database_url='sqlite+pysqlite:///:memory:', llm_provider='fake', internal_perception_token='test-token', auto_create_schema=True))
    with TestClient(app) as client:
        with app.state.database.session() as session:
            session.add(CameraStatusModel(camera_id='known', monitor_session_id='test-session', is_online=False,
                fps=0, processed_frame_id=0, active_workers_count=0, reported_at_utc=datetime.now(timezone.utc)))
        result = client.get('/api/v1/cameras/known/zones')
        assert result.status_code == 200
        assert result.json()['config_version'] == 0 and result.json()['zones'] == []
        with app.state.database.session() as session:
            assert session.get(CameraConfigModel, 'known') is None
        assert client.get('/api/v1/cameras/missing/zones').status_code == 404
        assert client.get('/internal/v1/perception/cameras/known/config', headers={'Authorization':'Bearer test-token'}).status_code == 404


@pytest.mark.parametrize('source', [r'E:\private\work\camera.mp4', '/home/private/camera.mp4', r'\\server\private\camera.mp4', r'file://…/E:\private\camera.mp4'])
def test_new_and_legacy_file_sources_expose_only_the_filename(source):
    assert CameraManagementService._mask(source) == 'file://…/camera.mp4'
    response = CameraManagementService._camera_response(SimpleNamespace(camera_id='cam', display_name='test', node_id='cv', source_type='file', source_uri_masked=source, desired_state='STOPPED', monitor_session_id=None))
    assert response.source_uri_masked == 'file://…/camera.mp4'


def test_completion_caps_each_task_without_hiding_incomplete_tasks(tmp_path):
    database = Database('sqlite+pysqlite:///:memory:')
    database.create_schema()
    now = datetime.now(timezone.utc) - timedelta(seconds=1)
    with database.session() as session:
        session.add(SafetyReportModel(report_id='report', period_start_utc=now, period_end_utc=now, statistics_json={}, citations_json=[], content_json={}, created_at_utc=now))
        session.flush()
        for task_id in ('done', 'pending'):
            session.add(TrainingTaskModel(task_id=task_id, report_id='report', status='PUBLISHED', title=task_id,
                target_count=1, question_count=1, pass_score=60, material='test', questions_json=[], created_at_utc=now))
        session.flush()
        for index in range(2):
            session.add(TrainingSubmissionModel(submission_id=str(index), task_id='done', worker_id=str(index), worker_name='test', answers_json=[0], score=100, passed=True, submitted_at_utc=now))
    service = LearningService(database, None, None, str(tmp_path), '')
    overview = service.weekly_overview()
    assert overview['completed_count'] == 2 and overview['target_count'] == 2
    assert overview['completion_rate'] == 50 and overview['excess_completed_count'] == 1
    stats = service.training_statistics('done')
    assert stats['completion_rate'] == 100 and stats['completed_count'] == 2 and stats['excess_completed_count'] == 1


def test_compressed_spa_assets_do_not_buffer_camera_streams(tmp_path, monkeypatch):
    from scripts import serve_demo
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/test.js').write_text('const x = "hello";\n' * 2000)
    (tmp_path / 'index.html').write_text('<html>' + 'x' * 2000 + '</html>')
    app = FastAPI()
    app.state.settings = SimpleNamespace(app_base_path='/helmet')
    @app.get('/api/v1/preview')
    def preview():
        return StreamingResponse(iter([b'--frame\r\n' + b'x' * 2000]), media_type='multipart/x-mixed-replace; boundary=frame')
    monkeypatch.setattr(serve_demo, 'create_app', lambda: app)
    monkeypatch.setattr(serve_demo, 'DIST_DIR', tmp_path)
    with TestClient(serve_demo.create_demo_app()) as client:
        asset = client.get('/helmet/assets/test.js', headers={'Accept-Encoding':'gzip'})
        assert asset.status_code == 200 and asset.headers['content-encoding'] == 'gzip'
        assert 'immutable' in asset.headers['cache-control']
        assert int(asset.headers['content-length']) < len(asset.content) / 4
        assert client.get('/helmet/dashboard').headers['cache-control'] == 'no-store'
        preview = client.get('/helmet/api/v1/preview', headers={'Accept-Encoding':'gzip'})
        assert preview.content.startswith(b'--frame') and 'content-encoding' not in preview.headers
