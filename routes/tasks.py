"""
EventGenie AI - Task-specific API Routes
Modern SQLAlchemy 2.0 implementation with input sanitization and strict validation.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from flask import Blueprint, jsonify, request, Response

from extensions import db
from models import Task

logger = logging.getLogger(__name__)
tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

VALID_TASK_STATUSES = {'pending', 'in_progress', 'completed', 'cancelled'}
VALID_TASK_PRIORITIES = {'low', 'medium', 'high', 'urgent'}


def _sanitize_text(val: Optional[str], max_len: int = 1000) -> Optional[str]:
    """Sanitize input string by trimming, removing tags and control chars."""
    if val is None:
        return None
    cleaned = str(val).strip()
    if not cleaned:
        return None
    cleaned = re.sub(r'<[^>]*?>', '', cleaned)
    cleaned = ''.join(c for c in cleaned if c.isprintable() or c in '\n\r\t')
    return cleaned[:max_len]


def _json_error(message: str, status: int = 400) -> Tuple[Response, int]:
    """Return JSON error response."""
    return jsonify({'success': False, 'error': message}), status


def _json_ok(
    data: Any = None, message: Optional[str] = None, status: int = 200
) -> Tuple[Response, int]:
    """Return JSON success response."""
    resp: Dict[str, Any] = {'success': True}
    if data is not None:
        resp['data'] = data
    if message:
        resp['message'] = message
    return jsonify(resp), status


def _parse_task_due_date(due_date_str: Optional[str]):
    """Parse task due date across multiple accepted formats."""
    if not due_date_str:
        return None
    clean_str = str(due_date_str).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            continue
    return None


def _update_optional_task_fields(task: Task, body: Dict[str, Any]) -> None:
    """Update non-critical optional attributes on a Task."""
    if 'description' in body:
        task.description = _sanitize_text(body.get('description'), 2000)
    if 'priority' in body:
        priority = (body['priority'] or '').lower().strip()
        if priority in VALID_TASK_PRIORITIES:
            task.priority = priority
    if 'category' in body:
        task.category = _sanitize_text(body.get('category'), 100)
    if 'due_date' in body:
        task.due_date = _parse_task_due_date(body.get('due_date'))


def _apply_task_updates(task: Task, body: Dict[str, Any]) -> Optional[str]:
    """Apply validated field updates to a task. Returns error string if invalid."""
    if 'title' in body:
        title = _sanitize_text(body['title'], 300)
        if not title:
            return 'Task title cannot be empty'
        task.title = title

    if 'status' in body:
        status = (body['status'] or '').lower().strip()
        if status not in VALID_TASK_STATUSES:
            valid_list = ', '.join(sorted(VALID_TASK_STATUSES))
            return f"status must be one of: {valid_list}"
        task.status = status

    _update_optional_task_fields(task, body)
    return None


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
def update_task(task_id: int):
    """Update an existing task."""
    task = db.session.get(Task, task_id)
    if not task:
        return _json_error('Task not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    validation_err = _apply_task_updates(task, body)
    if validation_err:
        return _json_error(validation_err)

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return _json_ok(task.to_dict(), 'Task updated')


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
def delete_task(task_id: int):
    """Delete a task."""
    task = db.session.get(Task, task_id)
    if not task:
        return _json_error('Task not found', 404)
    db.session.delete(task)
    db.session.commit()
    return _json_ok(message='Task deleted')
