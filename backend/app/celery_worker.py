# Celery worker initialization
from celery import Celery
import os

# Create Celery app
celery = Celery(
    'neurolab',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=[
        'app.tasks.preprocessing',
        'app.tasks.features',
        'app.tasks.training',
        'app.tasks.realtime'
    ]
)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # Soft limit 50 min
    worker_prefetch_multiplier=1,  # One task at a time for heavy processing
    task_routes={
        'app.tasks.preprocessing.*': {'queue': 'preprocessing'},
        'app.tasks.features.*': {'queue': 'preprocessing'},
        'app.tasks.training.*': {'queue': 'training'},
        'app.tasks.realtime.*': {'queue': 'realtime'},
    },
    beat_schedule={
        'check-auto-retrain': {
            'task': 'app.tasks.training.check_auto_retrain',
            'schedule': 3600.0,  # Every hour
        },
    }
)


def init_celery(app):
    """Initialize Celery with Flask app context"""
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery
