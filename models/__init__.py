"""
EventGenie AI - Database Models
Optimized with database indexes for high performance and strict type integrity.
"""
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, List
from extensions import db


class Event(db.Model):
    """Event model representing an event created by the user."""
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(100), nullable=False, index=True)  # wedding, birthday, college, community, custom
    location = db.Column(db.String(300))
    event_date = db.Column(db.Date, index=True)
    guest_count = db.Column(db.Integer)
    budget = db.Column(db.Float)
    theme = db.Column(db.String(200))
    preferences = db.Column(db.Text)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='planning', index=True)  # planning, confirmed, completed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships with cascading deletes
    plans = db.relationship('EventPlan', backref='event', lazy=True, cascade='all, delete-orphan')
    budget_items = db.relationship('BudgetItem', backref='event', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='event', lazy=True, cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='event', lazy=True, cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to a JSON-compatible dictionary."""
        total_tasks = len(self.tasks)
        completed_tasks = sum(1 for t in self.tasks if t.status == 'completed')
        total_budget_allocated = sum(b.amount for b in self.budget_items)

        return {
            'id': self.id,
            'name': self.name,
            'event_type': self.event_type,
            'location': self.location,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'guest_count': self.guest_count,
            'budget': self.budget,
            'theme': self.theme,
            'preferences': self.preferences,
            'description': self.description,
            'status': self.status,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'task_progress': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1),
            'total_budget_allocated': round(total_budget_allocated, 2),
            'budget_remaining': round((self.budget or 0) - total_budget_allocated, 2),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f'<Event {self.id}: {self.name}>'


class EventPlan(db.Model):
    """Stores structured AI-generated plan sections."""
    __tablename__ = 'event_plans'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    plan_type = db.Column(db.String(100), nullable=False, index=True)  # overview, timeline, vendor_checklist, ideas, day_schedule
    title = db.Column(db.String(300))
    content = db.Column(db.Text, nullable=False)  # JSON string
    version = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize plan section to dict with parsed JSON content."""
        import json
        try:
            content_data = json.loads(self.content)
        except (json.JSONDecodeError, TypeError):
            content_data = self.content
        return {
            'id': self.id,
            'event_id': self.event_id,
            'plan_type': self.plan_type,
            'title': self.title,
            'content': content_data,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f'<EventPlan {self.id}: {self.plan_type} for Event {self.event_id}>'


class BudgetItem(db.Model):
    """Budget breakdown item for an event."""
    __tablename__ = 'budget_items'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    category = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    estimated_amount = db.Column(db.Float, nullable=False, default=0)
    amount = db.Column(db.Float, nullable=False, default=0)  # actual/edited amount
    percentage = db.Column(db.Float)  # % of total budget
    notes = db.Column(db.Text)
    is_confirmed = db.Column(db.Boolean, default=False)  # estimated vs. quoted
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize budget item to dictionary."""
        return {
            'id': self.id,
            'event_id': self.event_id,
            'category': self.category,
            'description': self.description,
            'estimated_amount': self.estimated_amount,
            'amount': self.amount,
            'percentage': self.percentage,
            'notes': self.notes,
            'is_confirmed': self.is_confirmed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f'<BudgetItem {self.id}: {self.category} ₹{self.amount}>'


class Task(db.Model):
    """Actionable event planning task with deadlines and priorities."""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), index=True)  # preparation, vendor, decoration, logistics, etc.
    priority = db.Column(db.String(20), default='medium', index=True)  # low, medium, high, urgent
    status = db.Column(db.String(30), default='pending', index=True)  # pending, in_progress, completed, cancelled
    due_date = db.Column(db.Date, index=True)
    relative_deadline = db.Column(db.String(200))  # e.g. "3 weeks before event"
    is_overdue = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary with computed overdue status."""
        today = date.today()
        is_overdue = bool(
            self.due_date and
            self.due_date < today and
            self.status not in ('completed', 'cancelled')
        )
        return {
            'id': self.id,
            'event_id': self.event_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'relative_deadline': self.relative_deadline,
            'is_overdue': is_overdue,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f'<Task {self.id}: {self.title}>'


class ChatMessage(db.Model):
    """Stores conversation turns between user and AI planner assistant."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user, assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize chat message to dictionary."""
        return {
            'id': self.id,
            'event_id': self.event_id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f'<ChatMessage {self.id}: {self.role}>'
