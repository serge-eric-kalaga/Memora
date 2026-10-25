# Validation finale Gemma + MLX et inspection humaine

Recette complète isolée terminée avec exit0 : **33API +12navigateur +7auditUI =52PASS**,6étapes en139,38s (API53,12s). Modèle explicite `gemma4:e4b`, ASR final/live `mlx-whisper`, Chromium1248 existant, dernier bundle standalone. Aucun mock IA dans cette recette, aucun audio personnel ni modification des données principales.

## Modalité et provenance réellement relues

Source ASR synthétique : s1 « Bonjour. Nous décidons de lancer le projet Mémora lundi. Alice préparera la démonstration vendredi. » ; s2 « The budget remains an open question. We will discuss it next week. ».

Capture desktop courante ouverte et inspectée : `agents/logs/gemma-final-browser-report-desktop.png`. Résumé affiché : « Le projet Mémora sera lancé lundi, et Alice préparera la démonstration vendredi. Le budget reste une question ouverte et sera discuté la semaine prochaine. » La décision affichée conserve « Nous décidons de lancer… ». Ce résultat conserve le futur et ne présente pas le lancement comme déjà réalisé, contrairement au défaut précédemment observé avec Qwen.

Action démonstration : Alice, vendredi, source s1 à00:00, cohérente avec les mots prononcés. Discussion budget : responsable Non précisé, next week/la semaine prochaine, source s2 à00:07 (s2+s3 dans la capture où le moteur segmente la phrase). La question budgétaire reste ouverte ; aucune personne responsable ajoutée sans preuve. Les locuteurs restent non identifiés dans les citations, ce qui ne confond pas une personne chargée d'une action avec la voix qui parle.

Export en lecture seule de la seule base temporaire du runner, identifié par son marqueur/API19081, AVANT cleanup : `agents/logs/gemma-final-source-inspection.json`. Les6 rapports conservés (APIv1/v2/v4, UIv1/v2, capturev1) ont été relus avec leurs transcriptions correspondantes : les résumés conservent tous « sera lancé », les décisions restent des décisions de lancement, l'action Alice/vendredi est plausible et sourcée. Aucun autre défaut sémantique observé dans ces exemples. Cette inspection ciblée ne garantit pas la fidélité universelle du modèle.

## Preuves et isolation

Logs figés : `gemma-final-run.log`, `gemma-final-api.log`, `gemma-final-browser.log`, `gemma-final-ui-audit.log`, `gemma-final-summary.json`, diagnostics backend/frontend/mail sous même préfixe. Handoffs `gemma-final-e2e-api.md`, `gemma-final-browser.md`, `gemma-final-ui-audit.md`. Anciennes preuves Qwen préfixées `qwen-final-*` conservées avant exécution.

Avant/après :3PID principaux backend/frontend/mail vivants ; seuls les statuts HTTP ont été contrôlés, API8080/UI3000/inbox8025 répondent200. Les4ports de test19081/14001/12026/19026 sont fermés après la recette ; bases, mails et credentials temporaires ont été supprimés. Preuves `gemma-final-main-before.json` et `gemma-final-main-after.json`. Le JSON de rapports/transcriptions et les captures conservés sont exclusivement synthétiques.

Aucun code backend/frontend/harness corrigé pendant cette validation, aucun modèle installé/supprimé ou cache purgé. Ollama/GPU partagés ont servi à l'inférence locale ; la charge matérielle reste partagée. La recette ne couvre pas microphone physique, Safari/iOS, production ou fidélité générale sur réunions naturelles.
