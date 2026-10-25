# Vérifications — 25 octobre 2026, ~03:13 GMT

Les recettes utilisent seulement des données synthétiques. Aucun microphone physique ni email extérieur. Les fichiers de preuve et tests actuels priment sur cette synthèse. La recette intégrée Gemma+MLX a passé52contrôles avec inspection humaine de6rapports. La correction de reprise durable006 a ensuite passé6contrôles réels et une nouvelle recette intégrée52/52. Aucune qualité sémantique universelle déduite des seuls contrôles techniques.

| Commande / preuve | Résultat vérifié | Portée |
|---|---|---|
| `backend/.venv/bin/python scripts/memora-test.py` | **177 passed,3 skipped,1 warning,21,06s** | Bases et stockage jetables, worker désactivé, SMTP neutralisé. `logs/backend-tests.log`. Les3skips demandent TEST_REDIS_URL : intégrations Redis héritées, Redis désactivé pour Memora. Warning Pydantic URL/password Redis dans test de panne. |
| Ruff check et format check avec `--config backend/pyproject.toml` | PASS,40fichiers formatés | Domaine, tests Memora et scripts Python ; `logs/ruff-memora.log`, `format-memora.log`. |
| Frontend `npm run lint`, `npm run typecheck`, `npm run build:memora` | PASS après dernières sources | Refonte, import/reprise, permissions, hydratation, timeout et badge langue par portion. `logs/frontend-{lint,types,build}.log`. |
| Tests frontend ciblés | Langue6/6, i18n4/4, timeout2/2 ;7jalons UI et3proxy HTTP | `handoffs/frontend-requirements-audit.md`, `frontend-chat-deadline.md`. Pas un audit exhaustif Safari/accessibilité. |
| `npm --prefix frontend run api:check` | PASS final | SDK généré cohérent, `logs/api-check.log`. |
| Dépendances installées, pip check via runtime fourni | Aucune dépendance cassée | `logs/dependency-check.log` ; avertissement cache pip non accessible, cache désactivé sans bloquer le contrôle. |
| Téléchargeur, unittest8cas | PASS | Temp/mocks sans réseau ; provenance pin/SHA/taille, modèle existant non réécrit. Vérification réelle offline+réexécution sur modèle installé PASS, `logs/download-repeat-installed.json`. |
| Comparaison ASR réelle7cas×2moteurs | Résultats inspectés et critères techniques PASS | `handoffs/asr-final-validation.md`, détails ci-dessous. |
| Audio long synthétique15min | PASS couverture début/fin/langues,54,2905s |105segments, dernière fin899,84s, deux langues ; pic processus2,83GiB. `logs/benchmark-long.json/.log`. |

## Recette intégrée isolée

Runner : `backend/.venv/bin/python scripts/memora-verify-isolated.py --timeout 2400` avec `PLAYWRIGHT_CHROMIUM_EXECUTABLE` vers Chromium1248 installé. Création de comptes, bases, secrets, stockage, SMTP et copie frontend jetables ; arrêt uniquement de ses PIDs puis suppression temporaire. Modèles disque partagés en lecture et Ollama pour l’inférence : la latence peut dépendre des usages simultanés.

- Premier full base : **API24 + navigateur12 + auditUI7 PASS**,151,88s. Complément réel : **API33/33 PASS**,66,63s, paramètres/snapshots, guestedit puis403surancienlien, retranscriptionv4/idempotence/historique. Les anciens artefacts sont préservés sous `baseline-isolated-*`.
- **Final MLX+Qwen PASS** : API33/33 en72,9s, navigateur12 et audit7,6stages173,44s (173,67s avec nettoyage). Données temporaires supprimées ; main3PIDs+HTTP200 et ports tests fermés vérifiés. `logs/isolated-final-run.log`, `isolated-final-summary.json`, handoffs `isolated-final-*`.
- API : import/reprise/finalisation, Whisper/Ollama réels, rapport/chat/citations/manque, audio identique, corrections/historiques, droits/password/expiration/révocation, deux emails capturés, notification, archive/restauration, admin et retranscription.
- Navigateur : desktop/mobile, import→rapport, chat, correction/source périmée/régénération, invité/révocation/archive ; microphone factice Chromium, liveASR, pause, réseau coupé et sauvegarde reprise ; aucune exception JS lors du full final.
- Audit : reconnexion, focus clavier/Escape, FR/EN, thème, bornes admin sans mutation, mobile.
- Contrat UI supplémentaire : import interrompu sans finalisation partielle, reprise du même fichier, régénération invitée autorisée, retrait de vue sur révocation, suppression503 sans navigation et purge IndexedDB après succès ;7jalonsPASS sans exception.
- Proxy réel : chat normal200, délai1600ms avec configuration1000ms→504, REST1150ms→200 ; pas de troncature ni prétention d’annuler le calcul serveur.

## Qualité ASR réellement observée

Ancien base insuffisant, conformément au retour utilisateur. Son audio n’a pas servi aux benchmarks et n’a pas été retranscrit automatiquement. Un succès TTS sur la phrase Python ne réfute pas son défaut initial.

Le premier MLX brut traduisait l’anglais et hallucinait sur bruit : non activé. Ajout SileroVAD et inférence par portion vocale ; nouvelle comparaison complète inspectée :

| Corpus synthétique | Base WER normalisé | MLX VAD WER normalisé |
|---|---:|---:|
| Python |0%|0%|
| Python+10s silence |0%|0%|
| Français complexe |17,5%|2,5%|
| Français/anglais |7,69%|3,85%|
| Anglais |0%|0%|
| Silence/bruit |Aucun texte|Aucun texte|

Normalisation numérique limitée explicite ; accents conservés. Français restant « M. »/« Monsieur », mixte « Mémora »/« Memora ». Français forcé testé aussi : Python0%, complexe2,5%. Pas de promesse de qualité universelle. Temps courts et méthode : `handoffs/asr-final-validation.md`, `logs/benchmark-mlx-final-auto.json`, `benchmark-mlx-final-forced-fr.json`.

Quinze minutes synthétiques :50cycles FR/EN et phrase finale,54,2905s/RTF0,0603,105segments, deux langues, début et phrase finale retrouvés près de899,84s ;1segment incertain. Les marqueurs ne prouvent pas chaque mot, ni une réunion naturelle2h. Le fichier900s est aussi intégralement validé par PyAV en0,02s à une tolérance d’un échantillon.

## Fiabilité IA, sécurité et cycle de vie

- Six corpus Ollama : fragments adjacents, première personne/locuteur, date d’une autre action non attribuée. Speaker/temps préservés, unités avant lots, citations remappées. `handoffs/speaker-context.md`, `report-quality.md`.
- Réel long texte :56segments/3lots, action du dernier passage retrouvée dans rapport51,082s et chat22,074s, citation s-final. `handoffs/long-context.md`.
- Contexte12016tokens/2048 avec truncate:false/shift:false :400explicite1,86s. Pas de troncature silencieuse. `logs/context-overflow-probe.json`.
- Modèle volontairement inexistant : échec explicite, transcription conservée, relance après restauration sans réimport. `logs/resilience.log`.
- UID permanent/JWT et suppression : fuite par réutilisationIDSQLite et résurrectionJWT reproduites puis corrigées. Migration additive0007/domaine004/005 et sauvegardes privées ; aucun compte utilisateur supprimé pour tests. `handoffs/account-incarnation.md`.
- Maintenance : panne mail/permission fichier ne tue plus worker, réessai aux ticks suivants, autre purge poursuit ;3tests dédiés. Fenêtre live silencieuse conserve l’aperçu,2tests dédiés.
- Permissions : reprise ASR requiert audio si source vide, refuse absent/expiré ; regen avec transcription reste autorisée sans audio, replay idempotent conservé.
- Inférences locales partagent un verrou par appel/lot, libéré après succès/exception ;2tests concurrents. Les autres applications/Ollama extérieur ne sont pas contrôlés.

## Limites non vérifiées

Pas de réunion naturelle2h, charge multiutilisateur, microphone/appareil physique, veille/verrouillage réel, Safari/iOS, accessibilité exhaustive, délivrabilité externe ou production. Pas de diarisation automatique. Portions très courtes, voix faible et alternance sans pause restent difficiles ; relecture des passages importants nécessaire.

Notes et handoffs pérennes versionnables. Logs/captures exclus de Git dans `agents/logs/`, fichiers privés/modèles/audio dans `.memora/`. Aucun secret ni contenu utilisateur dans les preuves.

## Choix final du modèle de rapport/chat

Le défaut modal Qwen a été reproduit sur la source exacte synthétique. Gemma4:e4b déjà installé conserve le futur dans6rapports courts/3chats et dans la recette intégrée : **52PASS,139,38s** (API33 en53,12s, navigateur12, audit7). Six rapports et la capture desktop relus ; source de lancement futur, Alice/vendredi et budget ouvert correctement repris. `handoffs/gemma-final-human-review.md`, preuves `logs/gemma-final-*`. Configuration active Gemma+MLX, aucun modèle Ollama téléchargé.

Long56segments/3lots avec Gemma : rapport41,241s/chat18,693s, fait final cité ; manque et injection testés. RAM libre minimale19% sur un contrôle court, récupérée ensuite ; pas benchmark de charge. Classification d’une discussion présente en action reste perfectible. `handoffs/gemma-full-validation.md`, `report-modality-comparison.md`.

## Reprise durable006

Crash après publication ASR reproduit rouge puis corrigé : source publiée/checkpoint report atomiques, rapport/checkpoint complete atomiques. Reprise pipeline et retranscription sans deuxièmeASR ni doublereport ; idempotence source/version et protection résultat tardif conservées. Startup réconcilie seulement les métadonnées d’un traitement sans tâche active vers failed/relançable ; aucune inférence automatique. Échec relit checkpoint durable même si dict ancien.44tests ciblés PASS. `handoffs/worker-durable-checkpoints.md`.

Migration principale006 appliquée après0jobsactifs, arrêtworker, sauvegardeSQLite privée et contrôle de rattachement :14réunions existantes,0orphelin/ambigu. IntégritéSQLite ok ;21transcriptions/20rapports/16partages inchangés par comparaison privée avant/après, seul état processing orphelin devenu relançable. MainAPI/UI/capture/Ollama HTTP200. Aucun contenu utilisateur retranscrit ou régénéré. Preuve réelle terminée : `backend/.venv/bin/python scripts/memora-verify-worker-resume.py`,6contrôles PASS en37,3s,4SIGKILL sur les seuls processus temporaires. Pipeline puis retranscription : après ASR et après commit rapport/avant done, redémarrage conserve même rapport, une seule ASR/LLM par version et aucune notification dupliquée. Instrumentation suspend seulement aux frontières, modèles MLX/Gemma réels. Données temporaires supprimées. `logs/worker-durable-real.json/.log`. Dernière recette post006 terminée : **52/52 PASS** (API33 en55,11s, navigateur12, audit7),6étapes141,84s. Capture desktop relue : futur conservé, décision littérale, Alice/vendredi et budget ouvert sourcés. Preuves `logs/checkpoint-final-*` et `handoffs/checkpoint-final-acceptance.md`.

Clôture post006 : processus temporaires arrêtés, bases/mails/credentials jetables supprimés, ports19081/14001/12026/19026 fermés ;3PID principaux vivants et HTTP200. `handoffs/checkpoint-final-acceptance.md`, `logs/checkpoint-final-main-after.json`. Dernier contrôle ROOT : API/UI/capture/Ollama200.

## Correctif session expirée ~05:55 GMT

`node frontend/tests/memora-session-recovery-integration.mjs` :7contrôles PASS en environnement temporaire (réel proxy Next, backend HTTP synthétique). Les trois messages exacts de jeton/session expirée retournent200null et cookie effacé ; refus403 ordinaire et panne503 restent des erreurs sans logout. Chromium avec anciencookie retrouve Se connecter et efface son cookie, sans message indisponible. Build/lint/types PASS ; frontend seul redémarré. Aucun changement backend, réunion ou traitement. `logs/frontend-session-recovery-tests.log`, `session-fix-{build,lint,types}.log`.

## Recherche précision supplémentaire — intermédiaire09:09GMT

Le jalon est encore EN COURS ; aucun nouveau moteur/config n'est activé sur main. Corpus et résultats détaillés : handoffs/accuracy-benchmark-v1.md, accuracy-reserve-v2.md et accuracy-work-current.md. Références synthétiques figées ; la référence personnelle reformulée est impropre à tout scoreWER personnel.

- Comparaisons développement :8configurations×62cas=496inférences ASR réelles ; holdoutv1Turbo/routeFrenchlarge3=100 ; réservev2Turbo/Parakeet=148. Aucun silence/bruit seul transcrit dans ces comparaisons. Parakeetv2propre17/241erreurs=7.05%contreTurbo28/241=11.62%, FR7.23%vs24.10%, EN3.49%vs1.16%, mix11.11%vs9.72%. Ne pas convertir en90%universel ; routeFRParakeet/EN-auto-liveTurbo est une nouvelle hypothèse issueV2, validationv3 en cours.
- Analyse V3courte : tuning33/36itemsconformes,15/15faits,3/3chats ; petite réserve17/18items,8/8faits,1/1chat. Revue manuelle explicite, limitescatégories/collectifpersistantes ; handoffs/analysis-v3-reserve-results.md.
- Longs V4 : chat rectificationfinalePASS, rapportFAIL(action/budgetannulésrestentactifs), contrôleindépendantPASS ;321.064s réel. Échec conservé, correctionstatutsen cours, pas de succès déclaré.
- Backend complet aprèspremièrefusion :189PASS/3RedisSkip/1Pydanticwarning20.29s ; avantajoutfactory/adapter/planstatutsfinal.7testsroutefactoryPASS0.65s ;33préparationbench/downloaders/prototypePASS0.32s ;27adapter/installateur/policyCPU aprèssyncPASS4.26s. Ces tests mocks/offline ne remplacent pas les inférences réelles.
- Frontend nouveau badge langueunknown honnête :7testsPASS ; lint/types/buildPASS. Recette intégrée postroute reste à faire. uvfrozen ajoute7packages seulement, aucuneupgradeexistante, pipcheck144PASS ; MLX/Metal/PyAV/NumPy/Hubversions conservées.


## Résultats finaux précision —25/10, après activation locale

Cette section remplace les états « en cours » des notes intermédiaires, sans invalider les preuves historiques. Source AI finale V12 SHA df3afc645752ec5bebedf45eb195431a4bccb20adc85833743c35a206cb5585c.

| Commande / preuve | Résultat constaté | Portée / limite |
|---|---|---|
| `python3 scripts/memora-test.py` |242PASS,3skipRedis,1warning existant,21,77s ; accuracy-backend-v12-tests.log | Backend complet V12, DB/stockage jetables ; mocks dans tests isolés seulement. |
| `backend/.venv/bin/python -m pytest scripts/tests/test_memora_*.py -q` |48PASS,4,11s ; accuracy-preparation-final-tests.log | Téléchargeurs/SHA, génération config conservant existant, préparation/install/policy/évaluation. |
| `backend/.venv/bin/ruff check backend/api/memora backend/test/test_memora*.py scripts/memora-*.py scripts/tests/test_memora*.py` et `ruff format --check` même sélection | PASS,62fichiers formatés | Pas tout le code du template hors périmètre. |
| Frontend `node --test tests/memora-language.test.mjs`, `npm run lint`, `npm run typecheck`, `npm run build:memora` |7tests et commandes PASS ; accuracy-frontend-*.log | Badgeunknown explicite FR/EN et build livré. |
| `scripts/memora-verify-isolated.py --asr-engine mlx-whisper --french-asr-engine parakeet-mlx --timeout 2400` avec PLAYWRIGHT_CHROMIUM_EXECUTABLE réel |55PASS=35API+13browser+7audit ;177,13s total, isolated-summary.json | Migrations/auth/audio→ASR→rapport→chat/citations/manque/corrections/versions/partages/email/archive/admin ; pause/réseau/reprise/capture synthétiques, desktop/mobile. Runtime V11 figé au démarrage, fusionV12 testée séparément. Nettoyage terminé, aucun compte démo touché. |
| `scripts/memora-resilience.py` |2PASS, accuracy-resilience-final.log | Vrai modèle404 puis restauration Gemma, source conservée/rapport réel sans réimport, services/base isolés. |
| Réserve ASRv3 : scripts/memora-benchmark-accuracy.py et commandes exactes dans accuracy-reserve-v3.md |148inférences ; WERnumpropre6,07→4,05%, FR10,34→4,60% ; EN/mix inchangés |12sources inédites figées avant inférence, sixconditions+deuxnégatifs. Variantes d’une source non indépendantes, noms/bruit régressions publiées. WERstrict/CER séparés. |
| Long95s / deuxchaînesASR→rapport |4,21%WERnum/fourfenêtres ; sixfaitscentraux conservés | Noms erronés et résumé trop affirmatif persistent ; handoffs/accuracy-long-fr.md, asr-analysis-chain-real.md. |
| Cinq plans réels V12 puis un cas complet trois lots |5critèresciblés satisfaits125,088s puis94,688s full | Maps conservés de V10, pas cinqfullV12 ; cas connus après diagnostic. Responsables/délais/annulations corrects ; doublon décision À vérifier dans un cas. Handoff analysis-reconciliation-v12-final.md. |
| Contrôles activation main |0jobs/aucunecapture récente, backup privé0600, intégritéOK, nombres ressources identiques,4HTTP200 | Aucun original retraité ; configFRParakeet active, TurboEN/auto/direct inchangé. Preuve privée .memora/accuracy-activation.json. |

Première recette : API35PASS puis navigateur impossible à lancer sur ancien cheminChromium1234. Échec conservé accuracy-attempt1-*. Relance avec Chromium1248 effectivement installé réussie. Aucune dissimulation d’échec ni mock remplaçant l’inférence livrée.

Recherche/expériences rejetées et échecs longs sont conservés ; ne pas réutiliser un score de tuning comme preuve indépendante. La copie personnelle autorisée reste inchangée et privée ; référence reformulée, donc aucun score personnel valide. Pas90% universel ni validation voix naturelle2h/microphysique/Safari/iOS/production. Les notes d’analyse de réserve courte17/18affirmations et8/8faits concernent une petite réserve synthétique, pas une exactitude générale de la chaîne.
