# Memora — état de reprise

Mis à jour 2026-10-25 12:20 UTC, Africa/Ouagadougou. Livraison locale V1 et jalon supplémentaire de précision intégrés. Commits locaux autorisés par l’utilisateur après livraison ; aucun push, achat, déploiement public ou email réel. Lire AGENTS.md → agents/README.md → ce fichier, puis uniquement les preuves utiles. Les notes/fichiers actuels priment sur les anciens points de reprise.

## Onde défilante et continuité de capture — livrées localement

Onde historique300pics réels défilant droite→gauche, sans chiffres techniques visibles ; pause figée et reprise conservée. RecordingSignal ne possède pas les pistes. Continuity hook : changement de visibilité sans pause/stop, flush fragment, wake lock écran facultatif et heartbeat30s. Arrêt inattendu marqué interrupted, fragments conservés.

Protection native macOS locale : propriétaire connecté/UID +capture en cours/pause/loopback, caffeinate-i-t120,1bail/compte, release/TTL/shutdown. Empêche la veille automatique inactive du système sans modifier réglagesOS ni empêcher verrouillage/veille manuelle/capot. Pas de garantie de capture pendant vraie suspension matérielle. Backend nonmacOS/Docker/distant : protection native indisponible, fallback écran visible seulement.

Preuves :294backendPASS/3RedisSKIP/1warning préexistant22,37s ;40tests domaine/awake ciblés, RuffPASS ; assertion OS réelle présente puis libérée ;9contrôles onde et4helpersPASS ;7tests hook monté sur vrai WebAudio/MediaRecorder/onglets hidden-visible (41196octets,2flushes), WakeLock et HTTP de bail simulés dans ce test. Recette réelle isolée finale19browser+11auditUI PASS environ108s, services jetables nettoyés. Lint/types/build/OpenAPI/SDKcheckPASS. Handoffs capture-awake-local.md et recording-continuity-browser.md ; logs privés horsGit.

Activation main : garde0jobs/absence audio récent, services redémarrés sur loopback,4HTTP200 ; toutes empreintes domaine inchangées, intégritéOK,0jobs. Preuve privée .memora/capture-continuity-activation.json. Aucun audio personnel retraité ni microphone utilisateur ouvert. Prochaine action utilisateur : actualiser AVANT un nouvel enregistrement puis essai volontaire. Veille physique/capot fermé/microphone physique/Safari-iOS/longue capture naturelle restent non vérifiés ; la protection empêche la veille automatique mais ne promet pas d’enregistrer une machine réellement endormie. Commit local sans coauteur et aucun push.

## Présentation du rapport — livrée localement

Demande Actions à suivre/validation humaine : cartes actions/décisions regroupant texte, sources, responsable/échéance et pied de validation ; badge discret, formulaire responsive, compteurs de sections, état vide et bloc Points à vérifier. `report-review.tsx` et CSS dédié gardent API, permissions, original IA et historique séparé inchangés.

Lint/types/build PASS. Recette UI isolée élargie :11contrôles PASS,21,81s ; confirmation et historique réels,8captures cartes/formulaire desktop/mobile clair/sombre, aucun débordement/exceptionJS. Première tentative stoppée par sélecteur getByLabel exact textarea non vide, reproduit minimalement et remplacé par rôle/nom accessible exact sans changement produit. Échec conservé dans logs.

Frontend seul actualisé après garde0jobs/absence audio récent ; backend/Ollama inchangés,4HTTP200. Rendu réel et ouverture/fermeture formulaire vérifiés dans IAB sur réunion synthétique sans modifier données. Capture locale report-design-main-browser.png. Prochaine action utilisateur : consulter le rapport ouvert ; commit local sans coauteur, aucun push. Limites plateforme identiques aux précédentes.

## Correctifs après V1.1 — livrés localement

Transcription bornée avec défilement interne et titre/correction fixes ; résumé/sujets avec Sources repliées, citations directes pour décisions/actions/questions ; forme d’onde/niveau/crête et états audio pendant capture ; outils intervenants/lecture refondus en surfaces neutres et disposition compacte responsive. Aucun nouveau getUserMedia dans le visualiseur ; il ne stoppe pas les pistes du Recorder.

Français final maintenant **Whisper Turbo conditionné language=fr/task=transcribe**, après diagnostic de Parakeet incapable de contraindre la langue. Le symptôme personnel de traduction n’a pas été reproduit sur4cas synthétiques×3moteurs. Comparaison24profils déjà consommés : Turbo15,52% WER numérique, Full15,71%, Parakeet6,70% non contraint. Compromis explicite, pas90% général ; modèles conservés, aucun retraitement personnel automatique. Handoffs asr-language-drift-diagnostic.md et whisper-forced-fr-reserve-v3.md.

Vérifications :22tests routage/adaptateur backend +17préparation PASS ;22helpers frontend PASS ;8contrôles Chromium WebAudio/MediaRecorder synthétiques PASS ;19recette navigateur avec capture/live/pause/reprise/français réel et9auditUI PASS (environ108s, services isolés). Lint/types/build/Ruff PASS. Première tentative browser arrêtée par assertion trop précoce de niveau, corrigée par attente bornée sans affaiblir >0. Layout transcription/rapport validé4vues ; outils refondus validés4vues avec CSS WorkspaceFrame réel. Microphone physique, Safari/iOS non testés. Logs locaux exclus Git.

Activation main : zérojob actif/aucuneécritureaudio récente, config privée sauvegardée puis seule cléFrenchengine changée. Services Memora redémarrés, Ollama intact ;4HTTP200. Empreintes de toutes tables domaine inchangées, intégritéSQLiteOK,0jobs. Preuve privée .memora/ui-language-activation.json. Services prêts sur http://127.0.0.1:3000 ; actualiser la page. Ne pas retraiter les réunions existantes sans action utilisateur. Prochaine action utilisateur : actualiser la page puis essai volontaire. Livraison versionnée localement sans coauteur, aucun push.

## V1.1 — confiance et correction livrées localement

Autorisé par « Goooo » : contrôle microphone explicite/entrée/niveau/échantillon local, éditeur audio/transcription synchronisé (boucle/vitesse/raccourcis/diff), relecture humaine séparée des décisions/actions avec historique et droits invités, renommage global, séparation locale volontaire des voix. Implémentation et tests intégrés ; voir handoffs/trust-v11-current.md (clôture), human-review-v11.md et diarization-local-v1.md.

Séparation : Resemblyzer0.1.4 CPU,17MoSHApin/offline, Silero/AHC ; 2threads défaut configurables1..8/restaurés. Aucun nom réel déduit, segments multivoix non attribués, chevauchements non séparés. Réserve synthétique nouvellesvoix :18/18segments attribués, DER7,57%/8,10%propres,12,37%gainbruit ; pas garantie voixnaturelles/2h. ASR/Gemma inchangés.

Preuves finales V1.1 :284backendPASS/3RedisSkip/1warning26,78s ;48prépaPASS ;16frontendunitPASS ;10contrôlesmicroChromiumAPIsmédias synthétiques +2codecChromiumréel/fakeinput (blob lu, pistes stoppées, zéroPOST) ; lint/types/build/SDK/OpenAPI etRuff69fichiersPASS. Intégration en phases isolées distinctes :41API,19browser,9auditUI PASS (69contrôles composés, pas un unique run final69). Vrais moteurs locaux et vraiMediaRecorderChromiumfakedevice ; contrôles desktop/mobile, zéroexceptionJS. Deux sélecteurs de test etun OriginCSRF manquant ont interrompu des tentatives, preuves conservées ; aucune protection backend affaiblie. testing.md détaille chronologie/commandes/logs.

Activation main terminée après0jobs/aucuneécritureaudio récente, sauvegardesSQLiteprivées et migrationdomaine007 additive (Alembic0007 inchangée). Comptages et empreintes des transcriptions/rapports/partages/fragments inchangés, intégritéOK ; nouvelles tables initialementvides ; servicesrepartisHTTP200 et nouvellesroutesprésentes. Aucun retraitement personnel, modèleASR/Ollama ou distant modifié. Preuve privée .memora/v11-activation.json. Les limitations historiques ci-dessous concernent la baselineV1 et sont actualisées ici pour la séparation volontaire.

## État actif vérifié

UI http://127.0.0.1:3000 ; API8080 ; SMTP1025/capture8025 ; Ollama11434, tous locaux. Après activation, les quatre services HTTP200. Production désigne ici le build Next optimisé, pas un déploiement ni une qualification production.

Configuration actuelle : MEMORA_FRENCH_ASR_ENGINE=mlx-whisper. Français final Whisper large-v3-turbo conditionné fr/transcribe ; direct/anglais/auto-bilingue Whisper large-v3-turbo. ParakeetTDT0.6Bv3 reste installé comme option non contrainte ; analyse/chat Gemma4:e4b existant. Aucun modèle Ollama remplacé/supprimé/téléchargé. Modèles épinglés/SHA/licences dans docs/MEMORA.md et téléchargeurs versionnés. Dépendances uv verrouillées, sept ajouts sans upgrade des dépendances existantes.

Activation : zéro job actif, aucune capture/import récente ; configuration sauvegardée0600, redémarrage local. Intégrité SQLite OK et mêmes nombres de réunions/transcriptions/rapports/partages/fragments avant-après. Aucune réunion personnelle retranscrite/régénérée automatiquement. Preuve privée .memora/accuracy-activation.json, sans contenu de réunions dans les notes.

## Preuves de précision historiques et limites

ASR réserve indépendante v3 :148 inférences réelles,12 sources inédites avant inférence, six conditions+deux négatifs. WER numérique propre global6,07→4,05%, français10,34→4,60%, anglais4,55% et mixte2,78% inchangés. Bruit10 reste10,93%, échos10,93% ; noms propres imparfaits, pas90% universel. Référence privée utilisateur reformulée/partielle : copie locale testée qualitativement, aucun WER personnel valide. Audio/copie/résultats privés restent hors notes/logs. Voir handoffs/accuracy-reserve-v3.md et accuracy-long-fr.md (95s,4,21% WERnum, quatre fenêtres, noms encore erronés).

Deux chaînes ASR→rapport réelles : six faits centraux conservés ; une qualification « décidé » trop forte reste dans un résumé. Analyse courte réserve :17/18 affirmations conformes,8/8 attendues ; petit corpus synthétique, pas garantie universelle. handoffs/asr-analysis-chain-real.md et analysis-v3-reserve-results.md.

Fusion longue V12 finale SHA df3afc645752ec5bebedf45eb195431a4bccb20adc85833743c35a206cb5585c : existence initiale des actions puis transitions typées vérifiées par IDs source contraints ; résumés chronologiques conservés. Suppression non prouvée refusée et original marqué À vérifier. Cinq plans réels ciblés satisfaits (maps conservés, pas cinq analyses complètes), puis un cas complet trois lots validé94,688s. Cas connus après diagnostic, pas réserve aveugle. Doublon décision À vérifier persistant dans un cas ; classification LLM encore faillible. Échecs V4–V11 conservés. handoffs/analysis-reconciliation-v12-final.md.

Rejetés après essais : vocabulaire global (noms/langues régressés), remplacement global par Whisper large-v3 (bilingue/bruit régressés), variantes température/best_of sans gain, Qwen spécialisé pour classification longue. Pas de réécriture LLM silencieuse de l’ASR.

## Vérifications finales

- Backend V12 :242PASS,3Redis ignorés,1avertissement existant,21,77s ; Ruff check/format62fichiers PASS.
- Scripts préparation/config/téléchargement :48PASS ; frontend7libellés PASS, lint/types/build PASS.
- Recette isolée complète réelle :55PASS (35API+13navigateur+7audit),177,13s, nettoyage terminé. Source V11 chargée au démarrage ; V12 change uniquement fusion multi-lots, validée distinctement ci-dessus. Première tentative échouée avant navigateur à cause d’un chemin Chromium absent, conservée.
- Panne modèle réelle404 puis restauration :2PASS, source conservée/rapport unique sans réimport.
- V1 antérieure : durabilité4SIGKILL/6contrôles PASS, contrôles droits/versions/révocation ; sources historiques dans handoffs/checkpoint-final-acceptance.md et worker-durable-checkpoints.md.

Non vérifiés : microphone physique, Safari/iOS, veille/verrouillage réel, réunion naturelle2h, charge multiutilisateur, accessibilité exhaustive, délivrabilité externe et production. La séparation locale volontaire est disponible, sans identité déduite ni traitement des paroles simultanées ; correction manuelle toujours nécessaire. Contexte très volumineux peut échouer explicitement sans troncature silencieuse. testing.md contient commandes et preuves ; ne pas relancer tous benchmarks sans nouvelle anomalie/modification.

## Architecture, usage et continuité

Template FastAPI/Next réutilisé, comptes SQLite SQLAlchemy et domaine SQLite transactionnel/versionné, worker durable/checkpoints006/verrou POSIX ; migration domaine007/Alembic0007 actuelle. Capture/import progressifs IndexedDB, live/final, rapport/chat sourcés, audio, corrections/historiques, partages ouverts/password/droits invités/expiration/révocation, notifications/captureSMTP, archive/suppression/rétention/admin. Sécurité backend chaque ressource, UID permanent et contrôle de versions/résultats tardifs. UI FR/EN responsive inspirée des captures Read.ai. Connexion403 session périmée corrigée et vérifiée antérieurement ; panne503 reste distincte.

Démarrer : MEMORA_MODE=production ./scripts/memora-start.sh ; arrêter : ./scripts/memora-stop.sh ; état : ./scripts/memora-status.sh. Ne touchent pas Ollama. Compte démo déjà communiqué, identifiants uniquement .memora/demo.json0600. Configuration .memora/backend.env privée. Notes/handoffs/traçabilité versionnables ; .memora/ et agents/logs/ exclus Git (modèles, audios, bases, secrets, emails, captures/logs).

Prochaine action utilisateur : actualiser l’application ; nouvelle réunion→Vérifier le microphone, ou Transcription→Corriger/Gérer les intervenants. Rapport→Valider cet élément. Le traitement Séparer les intervenants localement est volontaire et conserve les anciennes versions ; relire puis régénérer le rapport. Pour l’ASR seule : Français→Retranscrire l’audio, historique conservé. Relire noms/montants/engagements, corriger et régénérer. Aucun besoin de reproduire la recherche avant cet essai. Guide docs/MEMORA.md ; traçabilité agents/requirements.md. Handoff de travail historique accuracy-work-current.md est clos par cet état et le handoff final V12.

## Versionnement local autorisé

Le dépôt initial provenait de la copie du template. Sur instruction explicite de l’utilisateur, l’ancien historique sauvegardé et le dossier .git ont été supprimés, puis le dépôt a été initialisé à neuf avec git init. Branche main avec un premier commit propre, puis commits fonctionnels locaux autorisés ; aucun distant, aucune mention de coauteur ni push. Aucune sauvegarde Git conservée. Guide docs/MEMORA.md explicitement inclus malgré une règle globale docs/. Secrets, modèles, bases, audios et logs restent exclus. Référence du commit disponible par git log.
