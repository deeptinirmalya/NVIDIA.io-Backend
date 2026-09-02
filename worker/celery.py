from celery import Celery
from kombu import Queue
from core.config import settings

CLOUDAMQP_URL = settings.CELERY_WORKER_BROKER_URL

client = Celery("worker", broker=CLOUDAMQP_URL)


client.conf.update(
    task_queue_max_priority=10,
    task_default_priority=5,
    task_queues=[
        Queue(
            'priority_celery',
            queue_arguments={'x-max-priority': 10}
        ),
    ]
)