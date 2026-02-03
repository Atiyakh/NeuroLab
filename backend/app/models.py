"""
Database models for NeuroLab
"""
import uuid
from datetime import datetime
from sqlalchemy import JSON, String
from .extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Subject(db.Model):
    """Subject/participant information."""
    __tablename__ = 'subjects'
    
    id = db.Column(String(36), primary_key=True, default=generate_uuid)
    label = db.Column(db.String(255), nullable=False, unique=True)
    dob = db.Column(db.Date, nullable=True)
    notes = db.Column(JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = db.relationship('Session', backref='subject', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'label': self.label,
            'dob': self.dob.isoformat() if self.dob else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'session_count': self.sessions.count()
        }


class Session(db.Model):
    """Recording session information."""
    __tablename__ = 'sessions'
    
    id = db.Column(String(36), primary_key=True, default=generate_uuid)
    subject_id = db.Column(String(36), db.ForeignKey('subjects.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    protocol = db.Column(JSON, default={})
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # relationships
    recordings = db.relationship('Recording', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'subject_id': str(self.subject_id),
            'date': self.date.isoformat(),
            'protocol': self.protocol,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'recording_count': self.recordings.count()
        }


class Recording(db.Model):
    __tablename__ = 'recordings'
    
    id = db.Column(String(36), primary_key=True, default=generate_uuid)
    session_id = db.Column(String(36), db.ForeignKey('sessions.id'), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    sfreq = db.Column(db.Integer, nullable=True)
    channels = db.Column(db.Integer, nullable=True)
    duration_sec = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), default='uploaded')  # uploaded, processing, processed, failed, needs_review
    s3_path = db.Column(db.String(1000), nullable=True)
    processed_path = db.Column(db.String(1000), nullable=True)
    features_path = db.Column(db.String(1000), nullable=True)
    meta = db.Column(JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    processing_jobs = db.relationship('ProcessingJob', backref='recording', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'session_id': str(self.session_id),
            'filename': self.filename,
            'sfreq': self.sfreq,
            'channels': self.channels,
            'duration_sec': self.duration_sec,
            'status': self.status,
            's3_path': self.s3_path,
            'processed_path': self.processed_path,
            'features_path': self.features_path,
            'meta': self.meta,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class ProcessingJob(db.Model):
    """Processing job tracking."""
    __tablename__ = 'processing_jobs'
    
    id = db.Column(String(36), primary_key=True, default=generate_uuid)
    recording_id = db.Column(String(36), db.ForeignKey('recordings.id'), nullable=False)
    step = db.Column(db.String(100), nullable=False)  # preprocessing, feature_extraction, training
    params = db.Column(JSON, default={})
    status = db.Column(db.String(50), default='pending')  # pending, running, completed, failed
    progress = db.Column(db.Float, default=0.0)
    log = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    celery_task_id = db.Column(db.String(255), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'recording_id': str(self.recording_id),
            'step': self.step,
            'params': self.params,
            'status': self.status,
            'progress': self.progress,
            'log': self.log,
            'error': self.error,
            'celery_task_id': self.celery_task_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'created_at': self.created_at.isoformat()
        }


class MLModel(db.Model):
    """Machine learning model metadata and versioning."""
    __tablename__ = 'models'
    
    id = db.Column(String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(50), default='1.0.0')
    model_type = db.Column(db.String(100), nullable=False)  # logistic, random_forest, etc.
    pipeline = db.Column(JSON, default={})  # Pipeline configuration
    hyperparams = db.Column(JSON, default={})
    metrics = db.Column(JSON, default={})
    feature_names = db.Column(JSON, default=[])
    scaler_params = db.Column(JSON, default={})
    cv_results = db.Column(JSON, default={})
    dataset_info = db.Column(JSON, default={})  # Split info, recording IDs used
    stage = db.Column(db.String(50), default='development')  # development, candidate, production
    s3_path = db.Column(db.String(1000), nullable=True)
    git_commit = db.Column(db.String(100), nullable=True)
    random_seed = db.Column(db.Integer, default=42)
    created_by = db.Column(String(36), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'version': self.version,
            'model_type': self.model_type,
            'pipeline': self.pipeline,
            'hyperparams': self.hyperparams,
            'metrics': self.metrics,
            'feature_names': self.feature_names,
            'stage': self.stage,
            's3_path': self.s3_path,
            'git_commit': self.git_commit,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class User(db.Model):
    """User authentication and authorization."""
    __tablename__ = 'users'
    
    id = db.Column(String(36), primary_key=True, default=generate_uuid)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='researcher')  # admin, researcher, viewer
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class AuditLog(db.Model):
    """Audit trail for important actions."""
    __tablename__ = 'audit_logs'
    
    id = db.Column(String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(String(36), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(100), nullable=False)
    resource_id = db.Column(String(36), nullable=True)
    details = db.Column(JSON, default={})
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id) if self.user_id else None,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': str(self.resource_id) if self.resource_id else None,
            'details': self.details,
            'created_at': self.created_at.isoformat()
        }
