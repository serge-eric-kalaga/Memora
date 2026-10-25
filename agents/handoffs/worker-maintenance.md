# Worker : isolation des échecs de maintenance

## Défaut reproduit avant correction

Deux tests SQLite isolés ont échoué sur le code initial : `PermissionError` lors de retention.unlink et `sqlite3.OperationalError` lors du SELECT de la file mail remontaient hors de `loop()`. Le premier job avait terminé, le second restait non traité : un thread de production se serait arrêté. Preuve locale `agents/logs/worker-maintenance-before.log` : **2 failed, 0,26s**. Données entièrement synthétiques, aucun modèle ou SMTP réel.

## Correctif borné

`backend/api/memora/worker.py` : `maintenance()` isole séparément send_mail et retention ; une erreur de l'une laisse l'autre s'exécuter et le worker poursuit les jobs au tick suivant. Aucun changement de claim/process/fail_job ou des versions/états de résultats.

Retention isole aussi l'OSError de suppression par fichier : si unlink échoue, audio_expired resteFalse et le fichier sera retenté plus tard ; les autres réunions expirées peuvent être purgées dans le même passage. Aucun flag de purge mensonger.

Journalisation : opération connue et classe d'exception uniquement, sans str(exception), traceback, chemin, adresse, corps de mail ou source. Pas de secret ajouté aux logs. Réessai au tick futur (cadence existante1s), sans nouveau thread/infrastructure.

## Résultats vérifiés

`cd backend && .venv/bin/python -m pytest test/test_memora_worker_maintenance.py -q` : **3 passed, 0,45s**.

- Refus permission du premier unlink, réussi au tick suivant : deux jobs terminentdone, réunionsready ; fichier finalement purgé et flag cohérent.
- SELECTmail échoue une fois : mail restequeued, autre maintenance s'exécute ; au tick suivant il est capturé par SMTP simulé une seule fois, étatsent et corps effacé. Deux jobs done, aucune tâche running abandonnée dans ce scénario.
- Un fichier constamment impossible à supprimer ne bloque ni les jobs ni la purge d'un autre fichier expiré ; flag du fichier refusé resteFalse.
- Marqueur synthétique de message d'erreur absent des logs ; tous les records exc_info=None.

Régression ciblée domaine :

`cd backend && .venv/bin/python -m pytest test/test_memora_worker_maintenance.py test/test_memora_domain.py -k 'maintenance or retention or mail or worker or job' -q`

**10 passed, 22 deselected, 0,80s**. Journal `agents/logs/worker-maintenance-after.log`. Ruff format/check réussis sur worker et nouveau fichier de tests.

## Portée

Tests de maintenance et persistance isolés, pas preuve de délivrabilité SMTP externe ni d'inférence IA. La panne testée de file mail survient avant SMTP ; aucune garantie de livraison exactement une fois en cas de panne après acceptation SMTP n'est revendiquée. L'enveloppe des jobs et les erreurs globales du stockage hors maintenance n'ont pas été modifiées. Backend à relancer par intégrateur pour charger ce correctif.
