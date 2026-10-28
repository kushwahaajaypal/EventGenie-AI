"""
EventGenie AI - Task-specific API Routes
"""
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from extensions import db
from models import Task

logger = logging.getLogger(__name__)
tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


def _json_error(message, status=400):
    return jsonify({'success': False, 'error': message}), status


def _json_ok(data=None, message=None, status=200):
    resp = {'success': True}
    if data is not None:
        resp['data'] = data
    if message:
        resp['message'] = message
    return jsonify(resp), status


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return _json_error('Task not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    if 'title' in body:
        title = (body['title'] or '').strip()
        if not title:
            return _json_error('Task title cannot be empty')
        task.title = title

    if 'description' in body:
        task.description = (body.get('description') or '').strip() or None

    if 'status' in body:
        valid_statuses = {'pending', 'in_progress', 'completed', 'cancelled'}
        status = (body['status'] or '').lower()
        if status not in valid_statuses:
            return _json_error(f"status must be one of: {', '.join(valid_statuses)}")
        task.status = status

    if 'priority' in body:
        valid_priorities = {'low', 'medium', 'high', 'urgent'}
        priority = (body['priority'] or '').lower()
        if priority in valid_priorities:
            task.priority = priority

    if 'category' in body:
        task.category = (body.get('category') or '').strip() or None

    if 'due_date' in body:
        due_date_str = body.get('due_date')
        if due_date_str:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                try:
                    task.due_date = datetime.strptime(due_date_str, fmt).date()
                    break
                except ValueError:
                    continue
        else:
            task.due_date = None

    task.updated_at = datetime.utcnow()
    db.session.commit()
    return _json_ok(task.to_dict(), 'Task updated')


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return _json_error('Task not found', 404)
    db.session.delete(task)
    db.session.commit()
    return _json_ok(message='Task deleted')
