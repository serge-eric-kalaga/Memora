# Tests domaine API Memora

Fichier possédé : `backend/test/test_memora_domain.py`.
Commande : `backend/.venv/bin/python -m pytest backend/test/test_memora_domain.py -q`.
Dernier résultat : **29 passed** (2026-10-25, 2.18 s ; défauts corrigés par intégrateur et revalidés).
Lint : `backend/.venv/bin/ruff check backend/test/test_memora_domain.py` réussi.
Formatage : `backend/.venv/bin/ruff format backend/test/test_memora_domain.py` réussi.

Périmètre : TestClient du router Memora seul, store SQLite et audio dans tmp_path par test. Identité synthétique via dépendance et stub validation JWT/lookup User ; le vrai contrôle de propriétaire et tous contrôles de partage restent exécutés. Pas une preuve de validation cryptographique JWT du template. SMTP neutralisé par conftest existant, aucune IA externe ou locale appelée. Validation WAV réelle via PyAV.

Scénarios : isolation propriétaire (y compris superuser), ordre/intégrité/idempotence chunks et récupération append orphelin, limites upload, finalisation valide/invalide/incomplète et unicité job, fermeture upload finalisé, mot de passe incorrect, expiration/révocation, restriction audio/transcription/chat/modification, corrections concurrentes et historique, rapport ancien non écrasant après correction, races révocation/correction pendant chat, droits invités configurables, bornes admin/rétention non rétroactive, archive/suppression/cascade, queue mail idempotente et retry échec SMTP, jobs running rétablis queued.

Défauts constatés puis corrigés et tests repassés :
- `worker.queue_mail` : INSERT 8 placeholders pour 7 colonnes mail (OperationalError).
- `routes.open_share` : mutation scope.headers après cache Request.headers ; lien expiré renvoie encore 200 lorsque session propriétaire présente (ou échec 401 pour invité sans token explicite). Endpoint doit appliquer token du chemin explicitement.

Régressions supplémentaires validées : 20 mots de passe incorrects consomment bien le quota ; vieux job v1 ignoré après correction v2 ; helper fail_job ignore ancien échec et résultat déjà prêt, mais expose un échec courant relançable ; génération rapport conserve historique et notification/mail uniques sur relance API, invisibles pour autre utilisateur.

Extension email : invitation multi-adresses validée/dédupliquée, mauvais password refusé, corps Fernet sans password clair en DB, déchiffrement du MIME avant SMTP simulé, corps effacé après sent, retry sent sans renvoi, nettoyage mail à suppression réunion, invitation interdite sans manage ou avec token autre réunion/révoqué. Ruff check/format réussis. Audit ciblé droits contemporains : chat révocation et correction durant IA déjà couverts ; aucun autre défaut reproductible identifié dans cette passe.

Extension retranscription : fr/en/auto transmis au worker, snapshots audio synthétiques, conservation versions transcript+rapport, request_id stable avant/après done, validation langue/identifiant/audio expiré ou absent, edit+audio obligatoires, politique admin courante même sur ancien lien, exclusion traitements concurrents. active_job_id empêche ancien échec même source de modifier tâche plus récente. generation_schema restreint toutes citations aux IDs autorisés sans modifier schéma de base. Tests ASR/rapport utilisent mocks ; aucune preuve de qualité MLX/Whisper/Ollama dans ces tests.
