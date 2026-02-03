"""
Flask extensions initialization
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()

# Initialize Celery
celery_app = Celery(
    'neurolab',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_routes={
        'app.tasks.preprocessing.*': {'queue': 'preprocessing'},
        'app.tasks.training.*': {'queue': 'training'},
        'app.tasks.realtime.*': {'queue': 'realtime'},
    }
)
