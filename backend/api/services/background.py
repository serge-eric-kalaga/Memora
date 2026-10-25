"""Socle Celery : déclarer, publier et suivre une tâche depuis l’API."""

import asyncio
import os
from celery import Celery

celery_app = Celery(
    "template",
    broker=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@task-broker:5672//"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    # Ajouter ici les modules contenant les tâches de chaque projet.
    include=[],
)
celery_app.conf.update(
    task_default_queue="background",
    task_acks_late=True,  # Acquitter après traitement, pour permettre la reprise.
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"confirm_publish": True},
    task_soft_time_limit=270,
    task_time_limit=300,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=86400,
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)


class TransientTaskError(Exception):
    """Erreur temporaire que la tâche autorise explicitement à retenter."""


def background_task(*, name: str, max_retries: int = 5):
    """Déclarer une tâche idempotente avec reprises limitées et attente progressive."""
    return celery_app.task(
        name=name,
        autoretry_for=(TransientTaskError,),
        retry_backoff=2,
        retry_backoff_max=300,
        retry_jitter=True,
        max_retries=max_retries,
    )


def enqueue(task, *args, **kwargs) -> str:
    """Publier et retourner l’identifiant ; propager une panne de publication."""
    return task.apply_async(
        args=args, kwargs=kwargs, argsrepr="<redacted>", kwargsrepr="<redacted>"
    ).id


async def enqueue_async(task, *args, **kwargs) -> str:
    """Publier depuis une route async sans bloquer la boucle HTTP."""
    return await asyncio.to_thread(enqueue, task, *args, **kwargs)


def task_status(task_id: str) -> dict:
    """Lire l’état ; vérifier les droits métier avant de l’exposer dans une route.

    PENDING peut désigner une tâche inconnue, en attente ou un résultat expiré.
    Les exceptions privées ne sont pas retournées au client.
    """
    result = celery_app.AsyncResult(task_id)
    status = {"id": task_id, "state": result.state}
    if result.successful():
        status["result"] = result.result
    return status
