"""Vérifier les contrats de publication sans contacter le broker applicatif."""

import asyncio
from unittest.mock import Mock
import pytest
from api.services.background import celery_app, enqueue, enqueue_async, task_status


def test_publish_failure_is_propagated():
    """Une panne du broker ne doit jamais être annoncée comme une tâche acceptée."""
    task = Mock()
    task.apply_async.side_effect = ConnectionError("broker down")
    with pytest.raises(ConnectionError):
        enqueue(task, "payload")


def test_async_publication_redacts_arguments():
    """Le producteur async retourne l’identifiant et masque les arguments affichés."""
    task = Mock()
    task.apply_async.return_value.id = "job-id"
    assert asyncio.run(enqueue_async(task, "private")) == "job-id"
    assert task.apply_async.call_args.kwargs["argsrepr"] == "<redacted>"


def test_failure_status_hides_exception(monkeypatch):
    """Ne pas exposer les exceptions privées via le statut public."""
    result = Mock(state="FAILURE")
    result.successful.return_value = False
    monkeypatch.setattr(celery_app, "AsyncResult", lambda _: result)
    assert task_status("id") == {"id": "id", "state": "FAILURE"}
