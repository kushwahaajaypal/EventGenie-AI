"""
EventGenie AI - Automated Tests
Run with: python -m pytest tests/ -v
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from app import create_app
from config import TestingConfig
from extensions import db as _db


@pytest.fixture(scope='session')
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Clean database between tests."""
    with app.app_context():
        yield
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


# ─── Health ───────────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['app'] == 'EventGenie AI'


# ─── Event CRUD ───────────────────────────────────────────────────────────────

def test_create_event_success(client):
    payload = {
        'name': 'Priya Wedding',
        'event_type': 'wedding',
        'location': 'Mumbai',
        'event_date': '2027-02-14',
        'guest_count': 300,
        'budget': 500000,
        'theme': 'Royal Blue',
    }
    resp = client.post('/api/events', json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['success'] is True
    assert data['data']['name'] == 'Priya Wedding'
    assert data['data']['event_type'] == 'wedding'
    assert data['data']['id'] is not None


def test_create_event_missing_name(client):
    resp = client.post('/api/events', json={'event_type': 'wedding'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False
    assert 'name' in data['error'].lower()


def test_create_event_missing_type(client):
    resp = client.post('/api/events', json={'name': 'Test Event'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False


def test_create_event_invalid_type(client):
    resp = client.post('/api/events', json={'name': 'Test', 'event_type': 'invalid'})
    assert resp.status_code == 400


def test_create_event_negative_budget(client):
    resp = client.post('/api/events', json={'name': 'Test', 'event_type': 'birthday', 'budget': -100})
    assert resp.status_code == 400


def test_list_events_empty(client):
    resp = client.get('/api/events')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['data'] == []


def test_list_events_with_data(client):
    client.post('/api/events', json={'name': 'Birthday Bash', 'event_type': 'birthday'})
    client.post('/api/events', json={'name': 'College Fest', 'event_type': 'college'})
    resp = client.get('/api/events')
    assert resp.status_code == 200
    assert len(resp.get_json()['data']) == 2


def test_get_event(client):
    create = client.post('/api/events', json={'name': 'Farewell', 'event_type': 'college'})
    event_id = create.get_json()['data']['id']
    resp = client.get(f'/api/events/{event_id}')
    assert resp.status_code == 200
    assert resp.get_json()['data']['name'] == 'Farewell'


def test_get_event_not_found(client):
    resp = client.get('/api/events/99999')
    assert resp.status_code == 404


def test_update_event(client):
    create = client.post('/api/events', json={'name': 'My Event', 'event_type': 'custom'})
    event_id = create.get_json()['data']['id']
    resp = client.put(f'/api/events/{event_id}', json={'name': 'Updated Event', 'location': 'Delhi'})
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['name'] == 'Updated Event'
    assert data['location'] == 'Delhi'


def test_delete_event(client):
    create = client.post('/api/events', json={'name': 'To Delete', 'event_type': 'community'})
    event_id = create.get_json()['data']['id']
    resp = client.delete(f'/api/events/{event_id}')
    assert resp.status_code == 200
    # Confirm deleted
    resp2 = client.get(f'/api/events/{event_id}')
    assert resp2.status_code == 404


# ─── Budget ───────────────────────────────────────────────────────────────────

def test_get_budget_empty(client):
    create = client.post('/api/events', json={'name': 'Budget Test', 'event_type': 'birthday', 'budget': 100000})
    event_id = create.get_json()['data']['id']
    resp = client.get(f'/api/events/{event_id}/budget')
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['items'] == []
    assert data['summary']['total_budget'] == 100000


def test_budget_calculation(client):
    """Test that budget totals are calculated in Python, not by AI."""
    from services.budget_service import check_budget_overrun, calculate_budget_totals

    items = [
        {'amount': 50000, 'estimated_amount': 50000},
        {'amount': 30000, 'estimated_amount': 30000},
        {'amount': 20000, 'estimated_amount': 20000},
    ]
    totals = calculate_budget_totals(items)
    assert totals['total_allocated'] == 100000

    summary = check_budget_overrun(items, 100000)
    assert summary['remaining'] == 0
    assert summary['is_overrun'] is False


def test_budget_overrun_detection(client):
    from services.budget_service import check_budget_overrun
    items = [{'amount': 120000, 'estimated_amount': 120000}]
    summary = check_budget_overrun(items, 100000)
    assert summary['is_overrun'] is True
    assert summary['overrun_amount'] == 20000


# ─── Tasks ────────────────────────────────────────────────────────────────────

def test_create_task(client):
    create = client.post('/api/events', json={'name': 'Task Event', 'event_type': 'wedding'})
    event_id = create.get_json()['data']['id']
    resp = client.post(f'/api/events/{event_id}/tasks', json={
        'title': 'Book venue',
        'priority': 'high',
        'due_date': '2027-01-01',
    })
    assert resp.status_code == 201
    data = resp.get_json()['data']
    assert data['title'] == 'Book venue'
    assert data['status'] == 'pending'


def test_complete_task(client):
    create = client.post('/api/events', json={'name': 'Task Event', 'event_type': 'birthday'})
    event_id = create.get_json()['data']['id']
    task_resp = client.post(f'/api/events/{event_id}/tasks', json={'title': 'Buy cake'})
    task_id = task_resp.get_json()['data']['id']

    update = client.put(f'/api/tasks/{task_id}', json={'status': 'completed'})
    assert update.status_code == 200
    assert update.get_json()['data']['status'] == 'completed'


def test_delete_task(client):
    create = client.post('/api/events', json={'name': 'Task Event', 'event_type': 'community'})
    event_id = create.get_json()['data']['id']
    task_resp = client.post(f'/api/events/{event_id}/tasks', json={'title': 'Test task'})
    task_id = task_resp.get_json()['data']['id']

    resp = client.delete(f'/api/tasks/{task_id}')
    assert resp.status_code == 200

    # Confirm deleted
    resp2 = client.put(f'/api/tasks/{task_id}', json={'status': 'completed'})
    assert resp2.status_code == 404


# ─── AI Integration (Mocked) ─────────────────────────────────────────────────

MOCK_PLAN = {
    'overview': {
        'summary': 'A beautiful wedding plan.',
        'key_highlights': ['Elegant venue', 'Delicious catering'],
        'estimated_duration': '8 hours',
        'recommended_venue_type': 'Banquet hall',
    },
    'preparation_timeline': [
        {
            'phase': '3 Months Before',
            'weeks_before': 12,
            'tasks': [
                {'title': 'Book venue', 'description': 'Shortlist and book venues', 'priority': 'high', 'category': 'venue'},
            ],
        }
    ],
    'event_day_schedule': [
        {'time': '10:00 AM', 'activity': 'Guest arrival', 'duration_minutes': 60, 'notes': '', 'responsible': 'Host'},
    ],
    'vendor_checklist': [
        {'category': 'Catering', 'tasks': [{'title': 'Finalize menu', 'description': 'Select dishes', 'priority': 'high'}]},
    ],
    'ideas': {
        'themes': ['Royal Blue', 'Floral Garden'],
        'color_combinations': [{'name': 'Classic', 'colors': ['#003366', '#gold']}],
        'decoration_ideas': ['Flower arch'],
        'menu_suggestions': ['Biryani'],
        'entertainment': ['DJ'],
        'budget_saving_tips': ['Book early'],
    },
    'budget_breakdown': [
        {'category': 'Venue', 'description': 'Banquet hall', 'estimated_amount': 150000, 'percentage': 30.0, 'notes': '', 'priority': 'essential'},
        {'category': 'Catering', 'description': 'Food & drinks', 'estimated_amount': 200000, 'percentage': 40.0, 'notes': '', 'priority': 'essential'},
        {'category': 'Decoration', 'description': 'Flowers & lights', 'estimated_amount': 100000, 'percentage': 20.0, 'notes': '', 'priority': 'important'},
        {'category': 'Miscellaneous', 'description': 'Other expenses', 'estimated_amount': 50000, 'percentage': 10.0, 'notes': '', 'priority': 'optional'},
    ],
}


def test_generate_plan_mocked(client):
    """Test AI plan generation with a mocked Gemini response."""
    create = client.post('/api/events', json={
        'name': 'Rahul Birthday',
        'event_type': 'birthday',
        'budget': 50000,
        'guest_count': 50,
    })
    event_id = create.get_json()['data']['id']

    with patch('routes.events.ai_service.generate_event_plan', return_value=MOCK_PLAN):
        resp = client.post(f'/api/events/{event_id}/generate-plan')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'plan' in data['data']


def test_generate_plan_missing_api_key(client):
    """Test graceful error when API key is missing."""
    create = client.post('/api/events', json={'name': 'Test', 'event_type': 'custom'})
    event_id = create.get_json()['data']['id']

    with patch('routes.events.ai_service.generate_event_plan',
               side_effect=ValueError('GEMINI_API_KEY is not configured')):
        resp = client.post(f'/api/events/{event_id}/generate-plan')
        assert resp.status_code == 400
        assert 'GEMINI_API_KEY' in resp.get_json()['error']


def test_generate_plan_api_error(client):
    """Test graceful handling of AI API failure."""
    create = client.post('/api/events', json={'name': 'Test', 'event_type': 'custom'})
    event_id = create.get_json()['data']['id']

    with patch('routes.events.ai_service.generate_event_plan',
               side_effect=RuntimeError('Gemini API quota exceeded')):
        resp = client.post(f'/api/events/{event_id}/generate-plan')
        assert resp.status_code == 503


def test_generate_plan_invalid_json(client):
    """Test handling of invalid AI JSON response."""
    create = client.post('/api/events', json={'name': 'Test', 'event_type': 'custom'})
    event_id = create.get_json()['data']['id']

    with patch('routes.events.ai_service.generate_event_plan',
               side_effect=ValueError('AI returned invalid JSON response')):
        resp = client.post(f'/api/events/{event_id}/generate-plan')
        assert resp.status_code == 400


def test_chat_mocked(client):
    """Test AI chat with mocked response."""
    create = client.post('/api/events', json={'name': 'Party', 'event_type': 'birthday'})
    event_id = create.get_json()['data']['id']

    with patch('routes.events.ai_service.chat_with_assistant', return_value='Here are some great ideas!'):
        resp = client.post(f'/api/events/{event_id}/chat', json={'message': 'Give me theme ideas'})
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert 'message' in data
        assert data['message'] == 'Here are some great ideas!'


def test_chat_empty_message(client):
    create = client.post('/api/events', json={'name': 'Party', 'event_type': 'birthday'})
    event_id = create.get_json()['data']['id']
    resp = client.post(f'/api/events/{event_id}/chat', json={'message': ''})
    assert resp.status_code == 400
