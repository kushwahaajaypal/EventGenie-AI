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


# ─── Security & Sanitization Tests ───────────────────────────────────────────

def test_security_headers_present(client):
    """Verify all critical OWASP security headers are present in responses."""
    resp = client.get('/api/health')
    assert resp.status_code == 200
    headers = resp.headers
    assert 'Content-Security-Policy' in headers
    assert headers.get('X-Content-Type-Options') == 'nosniff'
    assert headers.get('X-Frame-Options') == 'DENY'
    assert headers.get('X-XSS-Protection') == '1; mode=block'
    assert headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    assert 'Permissions-Policy' in headers


def test_input_sanitization_xss(client):
    """Verify HTML/script tags are stripped from user inputs to prevent stored XSS."""
    payload = {
        'name': '<script>alert("XSS")</script>Safe Wedding',
        'event_type': 'wedding',
        'location': '<b>Mumbai</b> Palace',
        'theme': '<img src=x onerror=alert(1)>Royal',
        'preferences': '<a href="javascript:alert(1)">No non-veg</a>',
    }
    resp = client.post('/api/events', json=payload)
    assert resp.status_code == 201
    data = resp.get_json()['data']
    assert '<script>' not in data['name']
    assert 'Safe Wedding' in data['name']
    assert '<b>' not in data['location']
    assert '<img' not in data['theme']
    assert '<a ' not in data['preferences']


def test_export_event_plan(client):
    """Verify the /export endpoint returns complete structured JSON."""
    create = client.post('/api/events', json={'name': 'Exportable Gala', 'event_type': 'community', 'budget': 100000})
    event_id = create.get_json()['data']['id']

    # Add a task
    client.post(f'/api/events/{event_id}/tasks', json={'title': 'Setup stage'})

    resp = client.get(f'/api/events/{event_id}/export')
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert 'event' in data
    assert 'plans' in data
    assert 'budget' in data
    assert 'tasks' in data
    assert len(data['tasks']) == 1
    assert data['tasks'][0]['title'] == 'Setup stage'
    assert 'exported_at' in data


def test_delete_single_budget_item(client):
    """Verify deleting a specific budget line item."""
    create = client.post('/api/events', json={'name': 'Budget Event', 'event_type': 'birthday', 'budget': 50000})
    event_id = create.get_json()['data']['id']

    # Add item
    update = client.put(f'/api/events/{event_id}/budget', json={'items': [{'category': 'Cake', 'amount': 3000}]})
    assert update.status_code == 200
    item_id = update.get_json()['data']['items'][0]['id']

    # Delete item
    del_resp = client.delete(f'/api/events/{event_id}/budget/{item_id}')
    assert del_resp.status_code == 200
    assert len(del_resp.get_json()['data']['items']) == 0


def test_budget_service_contingency_and_percentages():
    """Unit test contingency and percentage recalculations."""
    from services.budget_service import apply_contingency, recalculate_percentages

    contingency = apply_contingency([], 100000, 10.0)
    assert contingency == 10000.0

    items = [
        {'amount': 25000},
        {'amount': 75000},
    ]
    recalculated = recalculate_percentages(items, 100000)
    assert recalculated[0]['percentage'] == 25.0
    assert recalculated[1]['percentage'] == 75.0


def test_task_overdue_computation(client):
    """Verify task is_overdue computation for past due dates."""
    create = client.post('/api/events', json={'name': 'Overdue Event', 'event_type': 'custom'})
    event_id = create.get_json()['data']['id']

    task_resp = client.post(f'/api/events/{event_id}/tasks', json={
        'title': 'Past task',
        'due_date': '2020-01-01',
    })
    assert task_resp.status_code == 201
    assert task_resp.get_json()['data']['is_overdue'] is True


def test_cascade_delete_event(client):
    """Verify deleting an event deletes associated tasks and budget items."""
    create = client.post('/api/events', json={'name': 'Cascade Event', 'event_type': 'college', 'budget': 20000})
    event_id = create.get_json()['data']['id']

    # Add task & budget
    client.post(f'/api/events/{event_id}/tasks', json={'title': 'Poster design'})
    client.put(f'/api/events/{event_id}/budget', json={'items': [{'category': 'Print', 'amount': 2000}]})

    # Delete event
    del_resp = client.delete(f'/api/events/{event_id}')
    assert del_resp.status_code == 200

    # Ensure getting event 404s
    assert client.get(f'/api/events/{event_id}').status_code == 404
    assert client.get(f'/api/events/{event_id}/tasks').status_code == 404
    assert client.get(f'/api/events/{event_id}/budget').status_code == 404

