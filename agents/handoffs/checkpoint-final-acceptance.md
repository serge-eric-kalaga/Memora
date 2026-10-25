# Recette finale après checkpoints durables006

## Processus réellement tués et repris

Commande : `backend/.venv/bin/python scripts/memora-verify-worker-resume.py` → **6PASS en37,3s**, données et workers entièrement temporaires. ASR **MLX réelle**, rapport **Gemma4:e4b réel**, audio synthétique mixed-native.wav. Aucun résultat IA simulé. L'instrumentation attend aux frontières durables pour permettre des SIGKILL précis ; elle ne remplace pas le texte ASR ou le rapport.

Deux scénarios séquentiels : pipeline initial puis retranscribe. Pour chacun :

1. Après ASR réelle, le script vérifie en SQL `phase=report`, `source_version` publiée et transcription persistée, puis tue brutalement le seul groupe worker qu'il a créé.
2. Redémarrage sur la même base temporaire : rapport réellement produit, sans deuxième ASR ni version supplémentaire. Après commit de `phase=complete`, rapport et notification, le worker est de nouveau tué avant le passage du job à done.
3. Nouveau redémarrage : job done, réunion ready, même result_report_id, aucun rapport/version/notification supplémentaire.

**4SIGKILL réels**. Fin pipeline : version1,1transcription,1ASR,1appel rapport,1rapport,1notification. Fin retranscribe : version2,2transcriptions/ASR/rapports/notifications cumulés ; l'historique précédent est conservé. Les deux redémarrages après commit complet conservent les IDs de rapports. Compteurs d'appels instrumentés sans sortie simulée ; modèle local effectivement appelé après reprise.

Preuves : `agents/logs/worker-durable-real.log`, `worker-durable-real.json`, diagnostics `durable-checkpoint-*.log`. Script reproductible ajouté ; Ruff et py_compile réussis. Les workers créés sont arrêtés et leur répertoire temporaire supprimé. Aucun worker/service principal arrêté, aucune base principale modifiée par cette recette. Cette preuve vise les jobs exécutés avec006 ; elle n'invente pas un checkpoint pour des jobs historiquement interrompus avant cette migration.

## Parcours complets après006

Commande : runner complet `scripts/memora-verify-isolated.py --asr-engine mlx-whisper --timeout 2400`, Gemma4:e4b explicite et Chromium1248 existant, ports19081/14001/12026/19026, standalone du dernier build.

**52/52 contrôles PASS :33API +12navigateur +7auditUI**,6étapes en141,84s (**142,15s avec nettoyage**). API33 en55,11s. Inclut capture exclusivement synthétique, transcription live, pause/réseau offline/reprise, rapport/chat/citations, versions, partage, notifications/SMTP local, administration, édition invitée et retranscription idempotente réelle. Aucune inférence concurrente avec le probe de crash.

Preuves figées : `agents/logs/checkpoint-final-run.log`, `checkpoint-final-summary.json`, `checkpoint-final-api.log`, `checkpoint-final-browser.log`, `checkpoint-final-ui-audit.log`, diagnostics backend/frontend/mail sous ce préfixe. Les preuves Gemma précédentes `gemma-final-*` restent conservées.

## Inspection humaine et nettoyage

Nouvelle capture `agents/logs/checkpoint-final-browser-report-desktop.png` ouverte et relue : résumé « Le projet Mémora sera lancé lundi… », décision « Nous décidons de lancer… », Alice/vendredi/citation00:00 ; budget ouvert et discussion future/citation00:07. Aucune régression de modalité observée par rapport à l'inspection Gemma précédente ; la décision future ne devient pas un lancement déjà réalisé. La fidélité générale du modèle reste à relire sur chaque réunion.

Sondes avant/après (`checkpoint-final-main-before.json`, `checkpoint-final-main-after.json`) :3PID principaux backend/frontend/mail vivants, seuls les en-têtes HTTP consultés ; API8080, connexion UI3000 et inbox8025 répondent200. Les4ports de recette sont fermés après exécution, services créés arrêtés puis bases/mails/credentials temporaires supprimés. Tous artefacts conservés sont synthétiques.

Aucun code backend/frontend ni mémoire commune modifié par l'agent de recette ; seul le nouveau helper de vérification et ses preuves ont été ajoutés. Aucune donnée personnelle, aucun audio utilisateur, aucun nouveau modèle, fournisseur distant ou purge de cache. Modèles disque/Ollama/GPU partagés en lecture/inférence : pas d'isolation matérielle ou garantie de latence production. Pas de preuve microphone physique, Safari/iOS, veille réelle, charge production ou réunion naturelle2h.
