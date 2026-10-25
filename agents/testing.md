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

## V1.1 — capture, correction, validation et intervenants

- `python3 scripts/memora-test.py` :284PASS,3RedisSkip,1warningpréexistant,26,78s ; `v11-backend-final-tests.log`. Inclut15testsdiarisation et6workerdurabilité/versions/sourceimmutable.
- `backend/.venv/bin/python -m pytest scripts/tests/test_memora_*.py -q` :48PASS,3,82s ; `v11-preparation-final-tests.log`. Installateur testé avecpréparationpoidsoffline, politiqueisolation/configmodèles.
- Ruffcheck/format scopeMemora :69fichiersPASS ; `v11-ruff-final.log`.
- Frontend lint/types/buildPASS,16testsunit(7langue+3playback+6micro)PASS. SDK/OpenAPIexport+checkPASS. `v11-frontend-*-final.log` ; testsmicrocomposant :10contrôlesChromium avecAPIsmédias synthétiques(mockées),0exception ; `microphone-check-browser.log`, script `frontend/tests/memora-microphone-browser.mjs`.
- ModèleResemblyzer17,09MoSHApin préparé etcheck-onlyofflinePASS. `UV_CACHE_DIR=.memora/cache/uv .memora/tooling/bin/uv pip check --python backend/.venv/bin/python` :160packagescompatibles. Seulchangementversionexistante : setuptools84→80 compatiblepkg_resources ; dépendancesDarwinarm64, pasCUDAimposéLinux.
- Corpusdiarisation7cas+réserve4 ànouvellesvoix :seuilfigé0,30 avant réserve,18/18segmentsattribués ; DERréserve7,57%/8,10%propres,12,37%gainbruit. Segmentscouvrantdeuxgroupesabstiennent. FauxTTSsoussandboxv1vide rejeté, preuvesv2+finalréellesconservées. Protocole `handoffs/diarization-local-v1.md`, pasvoixhumaine/overlapnaturel2h.

Première recetteisolée V1.1 :API41PASS79,36s puis échecbrowser surlabelStatutambigu, formulaire pourtantvisible. Captureinspectée etancienslogs conservés `v11-attempt1-*`. Libellésaccessibles explicites corrigés, interface reconstruite. Relance finale en cours : `v11-isolated-final-run.log`, sourcesSHA dans `v11-isolated-source-provenance.json`. Aucun changementdecodeproductionpendantrelance ; auditmobileadditionnel chargéaprèsbrowser pourvérifiernouveauxformulaires.

Commande :

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Users/kalagasergeeric/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing' \
  backend/.venv/bin/python scripts/memora-verify-isolated.py --asr-engine mlx-whisper --french-asr-engine parakeet-mlx --timeout 2400
```

Base/stockage/captureSMTP/ports etcomptesjetables, vraiASR/Ollama/Resemblyzer. Chromiumfakedevice utilisel’audiosynthétique etsonvraiMediaRecorder, pasmicrophysique. Les noms/responsables ne sontpasidentifiésbiométriquement ; leséditshumainsrapport séparés ne remplacentpaslesphrasesprononcéesdanslechat. Migration007 additive etactivationmain restentàattesteraprèsrecette ; aucune donnéeprivée retraitée automatiquement.


### Clôture V1.1

Validation composée **41API+19navigateur+9auditUI=69contrôles PASS**, en exécutions isolées distinctes sur le même code de production figé. APIpreuve `v11-attempt2-isolated-api.log` (68,39s), browserpreuve `v11-attempt3-isolated-browser.log`, auditfinal `isolated-ui-audit.log` (lanceur21,88s). `v11-validation-summary.json` centralise les chiffres/empreintes. Ce n’est pas un unique run final69 ; backend etbuild inchangés entre phases. Les modes `--browser-only` et `--ui-audit-only` permettent une relance ciblée après problème de recette ; l’audit autonome prépare si nécessaire une fixture audio synthétique via le vrai pipeline, uniquement sur instance isolée.

Tentatives conservées :1labelStatutambigu (formulaire visible) corrigé par nom accessible explicite ;2sélecteurtexte interceptait optionmasquée Voixsynthétique, maintenant scopedstrong ;3auditPOST sansOrigin refusé403parCSRF, headerOrigin ajouté au test, protection serveur inchangée. Les41API avaient déjà passé deuxfois, les19browser passent avant relance audit seul. Les suites inchangées ne sont pas relancées pour masquer l’échec. Audit desktop/mobile final9PASS, deuxcapturessupplémentaires `isolated-audit-transcript-tools-mobile.png` et `isolated-audit-microphone-mobile.png` inspectées visuellement parROOT, pasdébordement.

Activation007 effective :0job/aucuneécritureaudio récente avant arrêt ; script migration local sauvegardeSQLite/validechemins+verrou ; intégritéOK et mêmes comptages+empreintes des transcriptions/rapports/partages/fragments. Nouvelles tables vides, aucun traitement de réunion original. Quatre servicesHTTP200, nouvelles routes présentes dans OpenAPI principal. Preuves privées `.memora/v11-activation.json` et `.memora/v11-migration.log`, jamais versionnées. Nettoyage processus/bases temporaires fait par chaque lanceur. Aucun micro physique, Safari/iOS, voixnaturelles ou déploiementproduction validé.


Complément codec microphone : `frontend/tests/memora-microphone-browser.mjs --real-codec` avec Chromium1248 et fichierWAVsynthétique, **2contrôles PASS** (`v11-microphone-real-codec.log`). VraiesAPIsMediaRecorder/AudioContext/getUserMediaChromium, entrée fournieparfake-device ; échantillonblob effectivement décodé et lu (currentTime avance), pistes stoppées, zéroPOST et zéroexception. DocumentHTTPS.test intercepté localement dansleprocessus, aucunserveurexterne ni microphysique. Le modedéfaut du mêmescript conserve les10contrôlesAPIsmédiasmockées distincts. Aucun changement de codeproduction après recette finale.


## Correctifs interface et langue — 25 octobre, après V1.1

- Routage français et adaptateur MLX :22 tests PASS (`scripts/memora-test.py test/test_memora_asr_routing.py test/test_memora_asr_mlx.py -q`). Préparation/configuration/install/politique isolée :17 PASS. Journaux `fr-language-route-tests.log` et `fr-language-preparation-tests.log`.
- Frontend helpers :22 PASS (langue, microphone, lecture, proxy et signal). `node --test frontend/tests/memora-{language,microphone-check,playback,proxy-timeout,recording-signal}.test.mjs`.
- Signal monté Chromium :8 contrôles PASS sur vrai WebAudio synthétique et MediaRecorder parent ; niveau/canvas, pause/reprise, silence, saturation, mute/ended, démontage préservant le flux. `node frontend/tests/memora-recording-signal-browser.mjs`. Aucun microphone physique. Helpers seuls pour AudioContext suspendu/API indisponible.
- Layout transcription/rapport : desktop1440×1000 et mobile390×844, clair/sombre, hauteur bornée/défilement interne, titre fixe, correction accessible, citation vers segment100 sans déplacement fenêtre, sources repliables et absence de débordement. Captures et preuve `transcript-layout-proof.json` dans logs locaux.
- Build final interface après refonte intervenants/lecture : lint, types et `npm run build:memora` PASS ; `final-ui-{lint,types,build}.log`. Validation complémentaire terminée :4vues avec CSS WorkspaceFrame réel, aucun débordement. Recette navigateur isolée19PASS +auditUI9PASS,environ108s avec vrais moteurs locaux et faux périphérique Chromium, source frontend avant la refonte des deux composants ; cette refonte vérifiée séparément en composants réels. Aucune revendication de recette intégrée unique sur le dernier build.
- Diagnostic FR réel :4 cas synthétiques×3 moteurs, aucune traduction reproduite. Comparaison conditionnée sur24profils déjà consommés+2négatifs ; TurboFR15,52% WER numérique, FullFR15,71%, Parakeetauto6,70%. Corpus limité, pas90% général. Voir handoffs/asr-language-drift-diagnostic.md et whisper-forced-fr-reserve-v3.md ; ne pas présenter Parakeet comme français forcé ni ces répétitions comme24 réunions indépendantes.
- Première tentative recette navigateur interrompue par assertion trop précoce sur le niveau après acquisition du faux périphérique. Attente bornée du vrai niveau ajoutée, assertion >0 conservée ; aucune logique applicative affaiblie.

Activation locale : seule clé moteur français changée après sauvegarde privée et garde0jobs/absence audio récent. Après redémarrage :4HTTP200, toutes empreintes de tables domaine inchangées, intégritéOK,0jobs. Pas migration ni retraitement imposé ; preuve privée .memora/ui-language-activation.json.


## Refonte actions/validation du rapport

`app.tsx`, `memora.module.css`, `report-review.tsx` et son module CSS : cartes actions/décisions, métadonnées groupées, badge de relecture et formulaire compact ; questions vides/limitations harmonisées. Aucun changement API/IA/données/permissions.

Lint/types/build PASS (`report-design-{lint,types,build}.log`). Frontend seul actualisé après garde0jobs/absence audio récent ; backend/Ollama inchangés et4HTTP200. Contrôle IAB sur réunion synthétique : rendu cartes réel, ouverture/fermeture formulaire sans enregistrement, capture `report-design-main-browser.png`.

Première recette UI : confirmation et historique réels PASS, puis sélecteur `getByLabel` exact d’un textarea non vide introuvable malgré formulaire ouvert ; reproduit en HTML minimal, remplacé par rôle textbox/nom accessible exact. Source applicative inchangée. Échec conservé (`report-design-first-failure.log`). Recette corrigée PASS :11contrôles UI,4stages/21,81s ;8captures cartes/formulaires desktop/mobile clair/sombre, aucun débordement/exceptionJS. Log distinct `report-design-ui-audit.log`.


## Onde historique et continuité de capture

- Backend complet :294PASS,3RedisSKIP,1warning préexistant,22,37s ; `python3 scripts/memora-test.py`, journal capture-continuity-backend.log.40tests domaine/awake ciblés PASS ; Ruff4fichiers PASS.
- Assertion macOS native réelle : PreventUserIdleSystemSleep vérifiée, aucune assertion de maintien écran ; release immédiat, aucun bail restant. Module fixe caffeinate-i-t120 ; détails handoffs/capture-awake-local.md.
- Waveform :9contrôles Chromium +4helpers PASS, pics réels décalés vers gauche mesurés par pixels, gel strict en pause et reprise conservant historique. Sans micro physique ; recording-signal-history-browser.log.
- Hook continuité monté :7contrôles PASS sur vrai WebAudio/MediaRecorder synthétique, vraies transitions hidden/visible de deux onglets d’un Chrome temporaire. Bytes progressent en arrière-plan, aucun pause/stop, flush en visibilité, pause maintenue, nettoyage, protection absente/refusée et acquisition tardive. WakeLock et service HTTP de bail simulés dans ce test isolé ; séparément le backend et l’assertion OS sont testés réellement ci-dessus. Script frontend/tests/memora-recording-continuity-browser.mjs ; recording-continuity-browser.log.
- Le premier harness Playwright gardait artificiellement chaque onglet visible (émulation de focus par défaut). Le test final utilise Chrome neuf +connectOverCDP(noDefaults:true), sans injection de document.hidden ni faux événement. Aucun défaut produit déduit de cette instrumentation initiale.
- Lint zéro erreur (avertissements tests), types/build, contrat OpenAPI et SDK généré/check PASS. Recette navigateur intégrée réelle finale :19jalons navigateur +11contrôles UI PASS, environ108s, log continuity-isolated-browser.log ; ports et services temporaires fermés. Aucun test de sommeil forcé, capot fermé, microphone physique ou Safari/iOS ; ces situations ne sont pas garanties.

Activation capture-continuité :4HTTP200 après garde0jobs/aucun audio récent ; intégritéOK et empreintes de toutes tables domaine inchangées. Preuve privée .memora/capture-continuity-activation.json. Aucun retraitement personnel.


## Textes utilisateur de l’enregistreur

Messages courts par état FR/EN et conseils repliés par défaut. Recette UI isolée12PASS/4stages20,97s (`recorder-copy-ui-audit.log`) : message prêt, conseils fermés par défaut puis ouverture/fermeture, aucun micro physique ni acquisition automatique ; autres vérifications langues/thème/mobile maintenues. Première tentative arrêtée faute de chemin Chromium explicite, relance avec l’exécutable existant réussie. Vérifications lint/types/build du texte dans recorder-copy-*.log ; aucun changement de capture ni backend. Unité EN MB corrigée après recette, vérifiée par compilation finale.

Textes enregistreur activés localement : lint/types/buildPASS, frontend seul redémarré après garde capture,4HTTP200 ; aucun changement backend ni microphone ouvert.


## Intervenants automatiques — nouvelles réunions

306backendPASS/3RedisSKIP/1warning21,15s, après adaptation d’une assertion ancienne affirmant à tort que les voix étaient toujours indisponibles.57tests ciblés couvrent checkpoint ASRv1, labels v2, échec/indisponibilité/mutation fournisseur, reprise sans doublon, correction concurrente et avertissement versionné.1test API complémentaire valide MEMORA_AUTO_DIARIZATION0/1 et conservation du snapshot antérieur (0,54s).2tests frontend prouvent absence de fauxnuméro pour inconnus et préservation des noms humains.

Ruff, lint/types/build et contrat OpenAPIcheck PASS. Vrai pipeline synthétique isolé : WhisperTurbo→Resemblyzer→Gemma,40,17s audio2voix/6prisesnonalternées,18,036s pipeline ; mêmes texte/IDs/temps v1/v2, labels1/2/2/1/1/2 et rapport uniquev2. Corpus connu, pas nouvelle réserve ni garantie naturelle. Handoff automatic-speakers-real.md ; reproduction scripts/memora-qa-auto-speakers.py après préparation réserve.

Recette finale réelle21browser+12UI PASS environ108s : nouveaux imports mixte/FR avec labels/provenanceSHA, v1ASR conservée, rapportv2, corrections/renommage/séparation manuelle, aucunJSerror. Logs auto-speakers-isolated-browser.log et handoffs/auto-speakers-browser.md. Main activé après gardes0jobs/0capture/aucun audio récent,4HTTP200 et empreintes de toutes tables domaine inchangées/intégritéOK. Aucun retraitement personnel.

## Capture persistante et chat conversationnel (25/10)

- `python3 scripts/memora-test.py` :315PASS,3RedisSKIP,1warning Pydantic préexistant,23,00s ; logpersistent-chat-backend.log.
- Ruffcheck backend ai/routes/testconversation et scripts/memora-qa-conversation.py PASS ; exportOpenAPI --check et npm run api:check PASS.
- `npm run lint`, `npm run typecheck`, `npm run build:memora` PASS ; cinqwarnings lint dans tests existants. Logs persistent-chat-{lint,types,build}.log.
- Chromium existant1248 explicite, `node tests/memora-persistent-capture-browser.mjs` :10contrôles PASS. MediaRecorder/codec/IndexedDB réels, API/auth/NextLink simulés ; navigation React, expiration et changement de compte, acquisition tardive après logout.
- Même Chromium, `node tests/memora-meeting-chat-browser.mjs` :7PASS après intégration finale ; réponsesAPI simulées, envoi/reprise/versions/droits/mobile. Logpersistent-chat-component.log.
- `scripts/memora-qa-conversation.py` :3tours réels Gemma sur transcription synthétique,10,475s total ; échéance vendredi sourcée et budget absent non inventé. Aucune donnée personnelle ni service payant. Logsconversation-real.{json,log}.
- Recette Next/API/IA réelle isolée : en cours, résultat et captures à ajouter après achèvement.

Tentatives intégrées conservées : première attente d’historique trop stricte (texte accessible inclut « Vous : »), assertion corrigée sans modifier produit ; deuxième navigation révèle modalcréation conservée dans l’étatNext au retour dashboard, recouvrant la barre. Produit corrigé : succèscréation ferme modal et libère busy avant router.push. Nouveau build et recette complète requis ; captures/logséchec conservés horsGit.

Dernier obstacle réel : tousparcours fonctionnels intégrésPASS, mais deux erreurs React418 détectées en finrun. Repro courte réunion brouillon sansIA : baselineproduction→418, dev→0, varianteproduction enfantsdirectsCaptureProvider→0, baselineproduction rétablie→418. Correction enlève wrapperDOM permanent et ajoute spacerconditionnel ; build finalPASS, recette complète relancée. Aucun avertissement masqué ni assertion zéroexception supprimée.

Clôture finale : `PLAYWRIGHT_CHROMIUM_EXECUTABLE=<Chromium1248 installé> python3 scripts/memora-verify-isolated.py --browser-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout 2400` :5stagesPASS,22browser+13auditUI,120,0s, zéroexceptionJS, demo_data_touched:false. 4capturesbarre et4chat desktop/mobile clair/sombre ; exemples inspectésROOT. Ports/services/stockages isolés nettoyés ; GPUlibre. Logfinal persistent-chat-isolated-browser.log, isolated-summary.json ; preuvesAB hydratation conservées. Harnesscapture10PASS relancé après suppressionwrapper.

Activationmain : guard0jobs/0capture/aucun audio récent, restart scriptsmemora en modeproduction local,4HTTP200 ; empreintes toutes tablesdomaine inchangées, quick_checkOK,0jobs. .memora/persistent-chat-activation.json0600. Aucun contenu personnel testé/modifié.

## Bandeaux et intervenants — correction25/10

`node --test tests/memora-speaker-label.test.mjs` :2PASS ; lint/types/buildPASS. Recette isolée `--ui-audit-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout600` avec Chromium1248 explicite :14UI PASS22,11s, zéroexceptionJS. Test supplémentaire injecte état analyzing +rapportpérimé dans réponseHTTP isolée et exige absence rappelpérimé ; pas preuve nouvelle logiqueworker, aucunworker changé. Préparationaudio/IA synthétique réelle. Logstatus-speaker-ui.log ; screenshotisolated-audit-single-analysis-status.png inspecté. Activation garde +4HTTP200 et empreintesdomaine inchangées, preuveprivée status-speaker-activation.json. Aucune donnée utilisateur retraitée.

## Chat réponses longues — correction25/10

`node --test tests/memora-chat-answer.test.mjs` :1PASS ; `node tests/memora-meeting-chat-browser.mjs` avec Chromium1248 :8PASS. Exemple15paragraphes,30sourcesdistinctes+doublon, sourcesfermées puis ouvertesliste≤240px etseekaudio, questiondansviewport, fontsansmonospace, renduHTMLnonexécuté, versions/permissions/abort/retry conservés. APIcomposant simulée. Logs chat-long-{unit,browser}.log ; captureschat-long-{mobile,desktop}.png.

Lint/types/buildfinalPASS et linttestsPASS. Recette `--ui-audit-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout600` :15UI PASS22,35s ;4capturesisolated-chat-long-{desktop,mobile}-{light,dark}.png, réponse longuefixtureHTTPisolée, donnéespersistéesinchangées. Préparationaudio/rapport réelle synthétique ; aucun testnouveau dequalitéIA. ExempledesktopdarkinspectéROOT ; zéroexceptionJS. Activation0jobs/0capture/aucun audio récent,4HTTP200 et empreintesdomaineinchangées ; .memora/chat-long-activation.json0600.

## Reprise séparation après échec25/10

`scripts/memora-qa-auto-speakers.py --cpu-only` sur réserve synthétique :PASS ; pas nouveau benchmarkseuils. Lint/types/buildPASS. Recette --ui-audit-only avecmoteursmlx etChromium1248 :16UI PASS21,91s,zéroexceptionJS. ScénarioHTTPisolé automaticfailed sourcecourante : messageclair,boutonouvre/focalisechampnombre,2accepté,actionactivée ;aucune nouvelle modificationbase par cecontrôle. PréparationASR/rapport réelle synthétique. Logspeaker-recovery-ui.log/captureisolated-speaker-failure-recovery-mobile.png.

Exception utilisateur pourcopie audio désignée : résultats etdiagnostics strictement .memora/accuracy-private/, pasdansceslogs/notes ; originalinchangé. Aucunrésultat qualitatifpersonnel généralisé.

## Dialogues intégrés25/10

Auditglobal frontend/src/public :aucunappel window.alert/confirm/prompt niéquivalentglobal restant. beforeunloadcapture conservé. Lint/types/buildfinalPASS (5warnings testspréexistants).

`memora-import-recovery.mjs` surfrontendjetable13000, toutesAPIinterceptéessynthétiques :7PASS, dont suppressionéchouée puisréussie/nettoyageIndexedDB via confirmationintégrée. Logdialog-import-recovery.log.

Recetteisolée --browser-only mlx/FRmlx :22browserréelsPASS (dialog-real-browser-passed.log), puisUIaudit détecteTabpouvantquitter HTMLdialog. Correctif Modal partagéboucleTab/ShiftTab explicite ; nouveau lint/types/buildPASS, puis --ui-audit-only :17UI PASS24,97s,zéroexceptionJS (dialog-final-ui.log).3confirmationsÉchap/Annuler→0requête,focusrestauré etTabcontenu,confirmation→1requêteinterceptée409 (sansmodifierDB). Quatrevues confirmation-{desktop,mobile}-{light,dark}.png ; mobile sombreinspectéROOT. Testsréels ettestscontratdistincts,pasunique39contrôlesmêmesource. Première tentativebrowserattendait dernierextraitAlice maintenanthidden ; sélecteurcorrigé ciblantAnswerBodyvisible,sansaffaiblirvérification.

Activationlocalegarde0jobs/0capture/aucun audio récent,4HTTP200, toutesempreintesdomaineinchangées,intégritéOK ;preuve .memora/dialog-activation.json. Microphonephysiqueetdonnéespersonnellesnonutilisés.

## Relanceanalyse→voix→rapport25/10

323backendPASS/3RedisSKIP/1warning25,93s, dont8nouveauxcas : séparationavantnouveaurapport/versionspréservées,correctionhumaineprotégée,idempotence/retryfailed,concurrenceparamètres,droitsguest/sansaudio/bornes,reportcrashrepris sansséparationdouble. Ruffcheck/formatPASS. OpenAPIexport etSDKrégénérés,checksPASS.

`scripts/memora-qa-analysis-speakers.py` : routeHTTPavecauthstub surbasejetable, vraisResemblyzerCPU/Gemma, audiocomposéderéférencesynthétique :21,699s,2groupes,rapportv2,sourcev1etancienrapportconservés. Loganalysis-speakers-real.log. Aucun audiopersonnel testé ici ; paspreuvequalitégénérale.

Recette --browser-only :22browserPASS surbuildavantultimesajustementsdisponibilitéaudio/aria-label/CSS, source backendprincipalevalidéepar323tests. UIauditinitialattendait labelcourtmaispetittexteaide faisaitpartiedunomaccessible ; corrigéaria-label+describedby. Buildfinallint/typesPASS. UIauditfinalavecfixtureHTTPfailed : borne9désactive puis2transmisdansbody/analyze (APIinterceptée409,sansmodifierDB), dansunrun de17contrôlesUItotal. Captures synthétiques etlogfinalanalysis-speakers-final-ui.log ; RésultatfinalaprèsCSS :17UI PASS24,39s/zéroexceptionJS. ImagechampmobileinspectéeROOT ; nomaccessible explicite etdétailsviaaria-describedby. Activationgarde+4HTTP200,empreintesdomaineinchangées/intégritéOK,preuveprivéeanalysis-speakers-activation.json.

## Harmonisation des couleurs25/10

`npm --prefix frontend run lint`, `typecheck`, `build:memora` : PASS (5 avertissements ESLint préexistants dans les tests). `git diff --check` et contrôle de secrets des fichiers modifiés : PASS. Aucun backend modifié ; la suite backend n’a pas été répétée pour ce changement CSS.

Recette isolée `memora-verify-isolated.py --ui-audit-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout 600`, Chromium1248 existant :19 groupes de contrôles UI PASS, 4 étapes runner PASS en28,86s, zéro exception JavaScript. Deux groupes ajoutés :6 routes publiques +4 routes connectées, chacune desktop1440/mobile390 × clair/sombre, soit40 vues de palette. Vérifications couleurs réellement calculées, contraste boutons activés≥4,5 et texte principal/fond≥7, texte secondaire/fond doux≥4,5, aucun débordement horizontal. Captures `isolated-palette-*` locales non versionnées ; connexion desktop sombre, inscription mobile clair/sombre, profil et administration desktop sombre inspectés visuellement. La recette existante couvre aussi réunion/rapport/transcription/chat/intervenants/confirmations/contrôle micro avec données synthétiques. Aucun microphone physique ni donnée personnelle utilisés. Pas de nouvelle mesure de qualité IA.

Défauts rencontrés : sélecteur de test main absent sur connexion remplacé par le vrai conteneur page-content ; filtre sélectionné distingué du bouton principal. Véritable défaut : transition background gardant l’ancienne couleur d’un bouton admin au changement de thème, contraste2,98. Retrait de cette transition des boutons ; recette finale valide couleurs et contrastes. Première attente d’animations bloquante remplacée par attente bornée des couleurs calculées, suivie des assertions. Logs `colors-final-{lint,types,build,ui}.log` et `isolated-ui-audit.log`, exclus de Git.

Activation locale après garde sans capture/tâche/audio récent :4HTTP200 ; empreintes toutes tables domaine inchangées, quick_checkOK, zéro tâche active. Preuve privée `.memora/colors-activation.json`0600. Services prêts sur http://127.0.0.1:3000 ; actualiser avant toute nouvelle capture. Aucun push ni déploiement public.

## Sur-segmentation — diagnostic synthétique en cours

Scripts temporaires `/tmp/memora-speaker-{regression,regression32,centers,channel-mono}.py`, exécutés séparément avec `backend/.venv/bin/python` : baseline16cas propres/réserve,5monologues/8conversations/3négatifs, comptes tous corrects. Variantes de canal acoustique/bruit/gain reproduisent2groupes pour1voix. Comparaison fenêtres1.6s/3.2s et seuils : aucune correction globale sûre prouvée ; 3.2s dégrade chevauchement DER6,10→8,17%, seuil.40 fusionne deux vraies voix, .42 fusionne3→2. Distances prototypes de faux groupes.229–.444 chevauchent vraiesvoix≥.298. Ne pas en déduire des taux sur parole naturelle. Preuves synthétiques locales speaker-overseg-{baseline,window32,centers,channel-mono}.json excluesGit. Aucun changement applicatif ni retraitement de réunion ; pas de nouvelle suite build/backend nécessaire. Diagnostic d’une nouvelle copie personnelle en attente autorisation explicite conformément à AGENTS.md.

## ECAPA et sur-segmentation — validation finale25/10

Dépendances SpeechBrain1.1.2/TorchAudio2.11.0 ajoutées avec uv lock/sync, Torch2.14.1 et anciennes versions conservés ; cinq nouveaux packages verrouillés. Poids officiels83,3Mo, Apache-2.0, révision0f99f2d0ebe89ac095bcc5903c4dd8f72b367286, SHA0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2. Architecturelocale statique comparée à EncoderClassifier officiel : allclose atol/rtol1e-5 PASS sur signal synthétique ; aucune configYAML exécutée en production. Préparation--from-file puis--check-only PASS, pas de second téléchargement des poids.

Évaluations exploratoires synthétiques :ECAPA1.6s seuil.55 choisi sur17cas calibration, réserve15cas consultée ensuite ; ECAPA3.2s améliore ces32cas, puis nouveauholdout12cas figé avant inférence, sans changement après résultats. Ces mesures ne constituent pas une garantie de précision sur parole naturelle. Résultats exploratoires locaux ecapa-synthetic-eval.json/ecapa-new-holdout.json. Comparaison initiale Resemblyzer : seuilplushaut fusionne vraiesvoix, fenêtresseules/filtrecanal insuffisants ; nepasreprendrecesparamètrescommevaleuruniverselle.

`memora-qa-speaker-consistency.py --engine ecapa-tdnn --include-holdout --output agents/logs/speaker-ecapa-integrated.json` :60inférences réellesCPU38,3528s,16baselinecomptesPASS,16variantesmonoautomatiquesPASS,16connus1PASS ;12holdout10comptescorrects/1abstention/1fauxcompte restant. Texte/IDs/timestamps préservés pourrésultatsacceptés. Nouveauholdout :monoFlo canal+gain+bruit reste2groupes auxdeuxéchelles ;3voixcanalindécidables→abstention. Huitconversationsbaseline gardent2/3groupes ; chevauchement DER6,41% vsanciennebaseline6,10%, gain/bruit12,68% vs11,80%. Cas courts1,2s difficiles, DERholdoutjusqu’à31,53%. Les abstentions ne sont jamais comptées comme bonnes attributions. Fixtureecapa-holdout-v1.json etgénérateurprepare-speaker-holdout.py versionnés ; --check-only12casPASS, refusécrasement incompatiblePASS.

`python3 scripts/memora-test.py` :333PASS/3RedisSKIP/3warnings23,81s ; après ultime garde manifeste nonobjet,24tests modulePASS1,17s.7nouveauxcasaupremierveto puis3casprovider/assets/source =10tests nouveaux parrapport323. `pytest scripts/tests/test_memora_env_generation.py -q` :5PASS. Ruffformat/check, lintfrontend (5warningspréexistants), sh-ninstall etgitdiffcheckPASS. Aucune modification de code de rendufrontend : pasnouveau build requis, construction optimisée précédente réutilisée ; testnavigateur attendprovenancedumoteur configuréexacte.

`MEMORA_DIARIZATION_ENGINE=ecapa-tdnn ... memora-verify-isolated.py --browser-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout600` :5étapesrunnerPASS126,93s ;22browser+19UI PASS, zéroexceptionJS. Auth, import/capture/live/navigation/pause/réseau/finalisation→ASR→ECAPA→Gemma→rapport, provenance etsourcev1 conservées, correction/renommage/séparation/versions, chat, partage/révocation etclavier/mobile/thèmes. Données/comptes/services jetables ; aucun microphone physique. Logs speaker-ecapa-browser.log,isolated-browser.log,isolated-ui-audit.log exclusGit. Pipeline synthétique séparé memora-qa-auto-speakers.py avantactivationECAPA :Resemblyzerv2 réelsource→voix→rapport18,648s, confirmantpréservationlegacy.

Copie personnelle explicitement autorisée : tous détails et résultats uniquement .memora/accuracy-private/, original audio SHA inchangé, aucune réunion réécrite. Activation ECAPA après garde0capture/0job/aucun audio récent :4HTTP200, toutes empreintes domaine inchangées/intégritéOK. Preuve privée .memora/ecapa-activation.json ; aucun push, email réel ou exposition publique.

## Exports transcription et rapport — 25/10

- `python3 scripts/memora-test.py` : **363PASS,3SKIP,3warnings,27,54s**, bases/stockage isolés ;30tests exports. Les3skips concernent Redis hérité. Log local `logs/exports-final-backend-tests.log`.
- `.venv/bin/python scripts/export_openapi.py --check` depuis backend, Ruff ciblé, `git diff --check`, `sh -n scripts/memora-install.sh` : PASS. Contrat OpenAPI/SDK régénéré, `npm --prefix frontend run api:check` PASS.
- Frontend `npm run lint`, `npm run typecheck`, `npm run build:memora` : PASS,5warnings lint préexistants. Logs locaux `exports-lint.log`, `exports-types.log`, `exports-build.log`.
- `python3 scripts/memora-verify-isolated.py --ui-audit-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout 600` avec Chromium1248 installé : **4étapesPASS,32,12s,20groupesUI,zéroexceptionJS** (`logs/exports-ui.log`, handoff isolated-ui-audit.md). Préparation synthétique ASR/ECAPA/Ollama réelle ;9téléchargements via interface/proxy/API, historique explicite, erreurs, invité protégé rapportseul/403/révocation404. Quatre vues dialogue desktop/mobile clair/sombre, focus/Échap/débordement vérifiés.
- Fixtures uniquement synthétiques `.memora/qa/exports/` : PDF transcription4pages/rapport6pages et DOCX transcription4pages/rapport7pages rendus, toutes les pages inspectées. Accents, FR/EN, durée>1h, mot très long, HTML littéral, Unicode hors police explicite et révisions humaines. Un titre DOCX bleu avec bordure a été corrigé et revérifié visuellement/XML. Captures et téléchargements locaux exclus de Git.
- Premier audit UI échoué sur un sélecteur Fermer ambigu, puis nom accessible version transcription ; helper et aria-label corrigés, audit final réussi. Test template `npm run test:generated-api` lancé sans URLs isolées : premier GET auth/config bloqué EPERM, aucune mutation ; **pas validé**, pas relancé sur les services principaux. L’intégration export réelle est couverte par la recette isolée ci-dessus.

Backend vérifie droits avant/après rendu, changement source409, ancien rapport même date ordonné parID, refus autre utilisateur/réunion, expiration/révocation/password, injection littérale, quota partagé par lien, taille avant chargement et concurrence. Les tests ne mesurent pas la qualité sémantique d’un nouveau modèle ; aucun audio personnel ni email externe utilisé.

Activation locale du build optimisé : garde0capture/0tâche/aucun audio récent ; redémarrage réel après restauration du suivi PID vérifié,4HTTP200 et empreintes de toutes les tables domaine inchangées/intégritéOK. Preuve privée `.memora/exports-activation.json`. Aucun changement de données ni enregistrement déclenché.

## Docker/PostgreSQL — livraison25/10

- `python3 scripts/memora-test.py` : **387PASS,9SKIP,3warnings,35,49s**, bases SQLite/stockage jetables, worker neutralisé (`logs/docker-backend-release-tests.log`). Skips :3Redis hérités +5PG +1import explicites ; ces6derniers ont été exécutés réellement séparément.
- `backend/.venv/bin/python scripts/memora-verify-postgres.py` : **6PASS1,49s**, deux DBs `memora_test_<aléatoire>` créées puis supprimées. Schémas/migrations, timestamps exacts, SQLparamétré/Unicode/quotas, rollback/cascade, concurrence/idempotence, uploadHTTP réel/fragments/fichier, importtoutescolonnes/révisionAlembic, séquences et refus cibleoccupée. `logs/postgres-live-release.log`.
- Docker images backend/frontend construites réellement avec les locks (`docker-build.log`, `docker-release-build.log`) ; Composeconfig/RuffPython/syntaxesshell/OpenAPIexportcheck/SDKcheckPASS. Frontendbuild Memoraoptimisé enimagePASS ; CI YAML13steps shellparse et12tests scriptsPASS. CI distante nonlancée.
- `scripts/memora-verify-docker.py` complet a passé les22contrôlesdu parcours navigateur approfondi, notamment provenance réelle ECAPA, capturemicrofactice, pause/navigation/réseau/reprise, FR/EN, versions, chat etdroits (`docker-browser.md`, `logs/docker-memora-e2e.mjs.log`). Son auditUI a ensuite révélé un bug du test lui-même : résumé de liste sanssegments au lieu détail. Correction fetchdétail et relanceciblée ci-dessous.
- `scripts/memora-verify-docker.py --ui-audit-only` final : **4étapesPASS**, 20groupesUIapprofondis, neufexportsréels/historique/erreurs/partageprotégé/révocation, états/confirmations, desktop/mobile clair/sombre, **zéroexceptionJS**, Mailpit reçoit réellementemailderapport etréunionspersistantesaprèsredémarrageAPI (`logs/docker-ui-acceptance-final.log`, `docker-ui-audit.md`). Les deuxrecettes utilisent conteneurs/volumes/comptes/stockages/ports jetables ; seuls poids/Ollama partagés. Aucun audio personnel.
- Bridge6testsPASS0,60s ; veille+bridge15testsPASS àl’étapeprécédente dont3frontièresIP/flag/XForwardedFor. Testsmodèlesmockésbornés dansunitaires ; modèlesréels dansrecetteDocker.

Bascule locale effective : garde0capture/0jobs, anciensPIDsdéjàabsents, verroustockage acquis ; `memora-import-postgres.py --apply` sauvegardeSQLitepuisimporte**26tables/535lignes** dansPG etcompareempreintesexactes, ycomprishashescomptes/UID/versions/liens. Preuves ethashes restent privés dans `.memora/docker/import-complete.json`, aucuncontenupersonnel dansnotes/logs. Toutesempreintesmédiasrevérifiéesinchangées aprèsdémarrage. Quatreconteneurssains, pontnatifauthentifié joignabledepuisAPI ;URLs README. Compte/sourceauthpasréécrits, aucunpush/production.

Les premiers essais Docker ont révélé : semicolons decommentairesSQL, ambiguïtéUPSERT, Rowdictdéballéenclés409upload, schémaauth "$user", refusdufichier-speakers. Corrigés+régressionsréelles. SaturationhôtearenduDockerreadonly ; nettoyageuniquementpackagesexpérimentaux/cachesNextdeMemora etredémarrageDesktopaprèsinventaire. Modèles/audio/volumesautresprojetspréservés. PasdevalidationSafari/iOS/veillematérielle niopérationsdeproduction.

Dernierscontrôles : lintfrontendPASS/5warningspréexistants ;quatreDockerhealthy,helperactif,`memora-postgres-check.py`PASS etavailabilityauthentifiéedepuisconteneurPASS. TroisanciennesDBsyntestrestantesretiréesuniquementdansleclusterMemoracréépourcejalon ;aucuneDBapplicativeniautreprojetmodifiéeparnettoyage.
