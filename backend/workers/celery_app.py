"""
Celery app configuration for background tasks
"""
from celery import Celery
from core.config import settings

# Create Celery app
celery_app = Celery(
    "salesops_pro",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'workers.call_processing',
        'workers.crm_sync',
        'workers.webhooks'
    ]
)

# Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True
)

# Task routes
celery_app.conf.task_routes = {
    'workers.call_processing.*': {'queue': 'processing'},
    'workers.crm_sync.*': {'queue': 'integrations'},
    'workers.webhooks.*': {'queue': 'notifications'},
}

if __name__ == '__main__':
    celery_app.start()
