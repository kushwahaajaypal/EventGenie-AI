"""
EventGenie AI - Task-specific API Routes
Modern SQLAlchemy 2.0 implementation with input sanitization and strict validation.
"""
import re
import logging
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, Tuple

from flask import Blueprint, jsonify, request, Response

from extensions import db
from models import Task

logger = logging.getLogger(__name__)
tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


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
    return jsonify({'success': False, 'error': message}), status


def _json_ok(data: Any = None, message: Optional[str] = None, status: int = 200) -> Tuple[Response, int]:
    resp: Dict[str, Any] = {'success': True}
    if data is not None:
        resp['data'] = data
    if message:
        resp['message'] = message
    return jsonify(resp), status


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
def update_task(task_id: int):
    """Update an existing task."""
    task = db.session.get(Task, task_id)
    if not task:
        return _json_error('Task not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    if 'title' in body:
        title = _sanitize_text(body['title'], 300)
        if not title:
            return _json_error('Task title cannot be empty')
        task.title = title

    if 'description' in body:
        task.description = _sanitize_text(body.get('description'), 2000)

    if 'status' in body:
        valid_statuses = {'pending', 'in_progress', 'completed', 'cancelled'}
        status = (body['status'] or '').lower().strip()
        if status not in valid_statuses:
            return _json_error(f"status must be one of: {', '.join(sorted(valid_statuses))}")
        task.status = status

    if 'priority' in body:
        valid_priorities = {'low', 'medium', 'high', 'urgent'}
        priority = (body['priority'] or '').lower().strip()
        if priority in valid_priorities:
            task.priority = priority

    if 'category' in body:
        task.category = _sanitize_text(body.get('category'), 100)

    if 'due_date' in body:
        due_date_str = body.get('due_date')
        if due_date_str:
            clean_str = str(due_date_str).strip()
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                try:
                    task.due_date = datetime.strptime(clean_str, fmt).date()
                    break
                except ValueError:
                    continue
        else:
            task.due_date = None

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
