# Traçabilité Memora V1

Référence : PDF fonctionnel V1, 16 pages extraites et lues lors de l'audit initial. Le PDF décrit les exigences ; les autorisations viennent de la demande utilisateur. Mémoire de travail : `agents/`, conformément à sa correction.

État vérifié le 25 octobre 2026. **Implémenté** décrit le code ; **test isolé** peut utiliser des mocks ; **réel synthétique** implique les services locaux. Aucune ligne ne vaut recette métier générale ou validation production. Les références PDF ci-dessous reprennent la cartographie initiale, sans nouvelle extraction du PDF.

| Exigence / référence PDF | Code / module | Preuve disponible et état réel |
|---|---|---|
| Comptes et isolation propriétaire, administrateur sans lecture globale §2 | Template auth ; `backend/api/memora/routes.py:access` | Tests domaine isolation propriétaire/superuser ; authentification réelle dans recettes API et navigateur isolé. |
| Dashboard, titre/date/mode/état, recherche/archives §3 | `frontend/src/features/memora/app.tsx` | Implémenté ; navigateur isolé valide dashboard/archive. Recette isolée de l’interface refondue12étapes et audit7contrôles PASS. Recherche non revendiquée comme test navigateur final. |
| REC01 autorisation micro et information §4 | Capture frontend | Recette isolée avec microphone exclusivement synthétique. Aucun micro physique utilisateur activé ni validé. |
| REC02 sauvegarde progressive §4 | `routes.upload_chunk`, IndexedDB frontend | Tests ordre/intégrité/rejeu/octets orphelins ; recette isolée navigateur perte réseau sans faux accusé puis reprise. Derniers correctifs de reprise import testés (7jalons isolés, aucun finalize partiel). |
| REC03 transcription progressive §4 | `worker.process` kind live ; `ai.transcribe` | Ancienne capture synthétique → transcription live réelle. Direct = aperçu susceptible de différer du final ; qualité MLX mesurée sur7cas +15min ; recette live MLX+Gemma terminée,12jalons navigateur PASS. |
| REC04 pause/reprise §4 | MediaRecorder + état réunion | Recette isolée Chromium valide pause/durée/reprise sur instance unique ; audit MediaRecorder synthétique confirme neuf chunks sans perte lexicale sur exemple EN. Pas appareil physique/iOS. |
| REC05 finalisation unique §4 | `routes.finalize`, jobs SQLite | WAV réellement décodé, finalisation idempotente, un job actif et upload fermé après finalisation : tests domaine + recette API. |
| Interruption réseau, veille/verrouillage §4.2 AC02/22 | IndexedDB et reprise frontend | Réseau simulé testé dans navigateur isolé ; veille/verrouillage et appareils physiques **non vérifiés**. |
| Limites durée et taille §4.3 AC03 | Settings snapshot ; validation audio ; chunks | Tests bornes/admin/upload trop grand/corrompu/incomplet ; durée backend validée. Pas benchmark réunion de 2 h. |
| Import formats/progression/reprise IMP01–04 | PyAV et upload chunké | WAV réel + import navigateur et comparaison audio API ; essais PCM/Opus synthétiques. Tous formats proposés et reprise dernière interface non couverts exhaustivement. |
| Traitement fond, erreurs et relance §5 AC05/06 | `store.py`, `worker.py` | Checkpoints006 atomiques après ASR et rapport, tests crash/reprise sans doubleASR/doublereport et réconciliation métadonnées orphelines. Service modèle inexistant puis restauration réellement testés ; preuve réelle006 :4SIGKILL/6contrôles PASS, aucune doubleASR/doublereport/notification. Redémarrage complet machine non vérifié. |
| TR01–04 segments, horodatage, incertitude, intervenants §6 | ASR + transcriptions versionnées | ASR réel FR/EN/mixte testé avec base ; incertitudes heuristiques, aucune diarisation automatique. Noms non identifiés conservés puis correction manuelle. |
| Fidélité transcription FR/EN et alternance §6.2 AC09 | `ai.transcribe`, `asr_mlx.py` | **Base insuffisant, remplacé après preuves par MLX large-v3-turbo + SileroVAD**. SHA256 vérifié,7cas réels : FR complexe WER normalisé17,5→2,5%, Python/EN0%, mixte3,85% sans traduction, silence/bruit sans texte. Audio synthétique15min54,29s, début/fin/langues retrouvés. Limites voix faible/portion courte/alternance sans pause ; aucune garantie générale ou test naturel2h. Voir asr-final-validation.md. |
| Retranscrire l'audio existant, choisir auto/fr/en | `routes.retranscribe`, worker kind retranscribe | Tests paramétrés fr/en/auto et requêtes idempotentes ; recette API MLX réelle33contrôles inclut nouvelle transcriptionv4, historique et nouveau rapport. Source vide : droit audio requis et expiration vérifiée, replay idempotent et regen avec texte conservés. |
| Corrections et historique §6.3 AC10 | `correct`, table transcripts | Conflit409, repères audio immuables, anciennes versions conservées ; correction/régénération réellement parcourues dans API MLX33contrôles et navigateur isolé. |
| Régénération et prévention résultats/échecs tardifs | `analysis_requests`, active_job_id, `worker.fail_job` | Tests requêtes idempotentes, exclusion analyse/retranscription concurrentes, ancienne source/ancien job même version ne remplaçant pas état récent, échec courant relançable. |
| RAP01–06 résumé/sujets/décisions/actions/responsables/dates/questions §7 | `ai.Report`, `reading_units`, `report`, reports | Modèle local réellement testé ; cas normal/fragment adjacent/contre-exemple et locuteur/date distincte tous PASS (`report-quality.md`). Dates absentes restent non précisées. Gemma retenu après défaut modal Qwen reproduit :6rapports de recette relus, futur conservé. Classification discussion/action perfectible ; qualité globale/relecture humaine restent nécessaires. |
| Fidélité, manque et contradiction §7.2 | Prompts et contrôle provenance | Manque et injection synthétiques testés ; sources invalides rejetées. Pas garantie d'absence universelle d'hallucination. |
| CHAT01–04 sources, audio et isolation §8 | `ai.answer`, `routes.chat`, frontend citations | API réelle question/citations/manque ; test56segments/3lots conserve fait et citation du dernier segment dans rapport/chat ; tests révocation et correction pendant génération, contenu autorisé seulement. Citations parcourues dans la recette isolée. |
| Chat si transcription masquée §8.2 | Contexte limité au rapport visible | Tests rapport uniquement ; sources transcript supprimées. Identité acteur/session et historique versionnés. |
| Injection audio/documents §8.3 AC11 | SYSTEM + données JSON + contrôle IDs | Essai local injection et tests refus sources étrangères ; generation_schema contraint citations aux IDs autorisés, schéma de base non muté. |
| PAR01–05 lien ouvert/protégé/droits/invité §9 | Routes shares et frontend | Tests API sans compte, password incorrect, audio/chat/edit/manage ; accès réel invité et password dans recette API. Partage invité testé dans la recette isolée. |
| Permissions invité contemporaines | `share_access`, config courante | Test ancien lien edit après désactivation admin refuse correction/retranscription ; retranscription exige edit+audio. Pas de restriction nominative inventée par destinataire email. |
| Expiration et révocation §9 AC13–15 | Contrôle share sur chaque ressource | Tests expiration même owner connecté, révocation pendant chat ; recette réelle retrait audio et réunion. Ancienne page invitée observe révocation. Aucune révocation de copie téléchargée revendiquée. |
| Invitation multi-adresses, résumé et password §9 | `invite`, outbox Fernet | Tests validation/déduplication/mauvais password/corps chiffré/purge à suppression. Deux emails réels reçus en capture avec résumé et bouton ; ce parcours réel n'envoyait pas de password. |
| NOT01–03 notification et email §10 | `worker.queue_mail/send_mail` | Notification réelle et SMTP capture ; tests corps effacé après sent, pas renvoi sent, retry failed, isolation propriétaire. Aucune délivrabilité externe testée. |
| Configuration durée/conservation/édition §11 | Settings admin, snapshots | Bornes/admin/non-rétroactivité tests ; défauts = décisions techniques configurables, pas arbitrages explicites utilisateur. |
| Archive/restauration §11.2 AC18 | archived indépendant state | API réelle et navigateur isolé ; conserve contenu et liens. |
| Conservation/suppression §11 AC20/21 | retention audio, delete cascade/files/mail | Tests purge audio sans supprimer transcription, suppression cascades et mails liés, tombstoneUID de suppression de compte, erreur de fichier réessayée sans arrêter le worker. Pas preuve d'effacement de sauvegardes externes ou copies destinataires. |
| Sécurité serveur et isolation §13 | JWT template, access/limit, fichiers privés | Suite backend complète177passed/3skipped après006 ; tests domaine droits/quota password ; recette auth API réelle. Audit ne constitue pas certification sécurité production. |
| Responsive/clavier/accessibilité §13 AC22 | Frontend responsive/forms | Recette isolée Chromium1440×1000 et390×844 ; refonte finale testée (12étapes +7auditUI). Derniers correctifs d’import et hydratation testés (7jalons), types/lint/build PASS. Clavier/accessibilité exhaustive/Safari/iOS non validés. |
| D01–D12 paramètres ouverts p15–16 | `memory/decisions.md`, configuration | Valeurs initiales/hypothèses documentées ; validation métier générale non acquise. |

Ajouts vérifiés : sécurité UID permanent/JWT lié au compte après delete/register ; migration prudente avec sauvegardes ; source en fin de trois lots conservée ; erreurs de maintenance isolées ; dépassement de contexte Ollama refusé explicitement. Recette Gemma+MLX : API33+navigateur12+audit7 PASS, avec inspection humaine de6rapports. Recette supplémentaire postcheckpoint006 terminée :52/52 PASS en141,84s.

Preuves et commandes : `testing.md`, `handoffs/api-tests.md`, `handoffs/e2e-api.md`, `handoffs/browser.md`, `handoffs/asr-capture-quality.md`, `handoffs/asr-mlx-adapter.md`, `handoffs/report-quality.md`. Logs locaux exclus Git ; ne remplacer un état en cours que par un résultat réellement terminé.

Contexte et ressources : dépassement Ollama400 explicite (pas troncature), chat proxy configurable10min et504explicite, verrou par appel/lot ASR/Ollama (tests concurrence), maintenance réessayée sans tuer worker. Ces dispositifs bornent le fonctionnement local sans promettre une capacité illimitée.

## Précision supplémentaire — livraison locale du25/10

Cette section actualise les états historiques ci-dessus ; les preuves antérieures ne sont pas effacées.

| Besoin / exigence liée | Code et méthode | Preuve et état réel |
|---|---|---|
| ASR française sans dégrader anglais/direct/alternance | ai.transcribe, asr_parakeet.py, asr_mlx.py ; factory FR finale uniquement | Activé localement après réserve indépendantev3 :148inférences, WERnumpropre6,07→4,05%, FR10,34→4,60%, anglais/mix inchangés. Bruit/noms encore difficiles ; accuracy-reserve-v3.md. |
| Raccords audio longs | Parakeet30s/chevauchement2s, timestamps natifs |95s/fourfenêtres :4,21%WERnum, pas bloc perdu/doublon détecté ; noms/responsables parfois erronés. Pas réunion naturelle2h. accuracy-long-fr.md. |
| Propositions/actions/échéances/injection fidèles | SYSTEM/REPORT_RULES, schémas, filtres | Réserve courte17/18affirmations,8/8faits ; deux chaînes ASR→rapport sixfaits, résumé parfois trop affirmatif. Pas100%. analysis-v3-reserve-results.md et asr-analysis-chain-real.md. |
| Corrections/annulations entre lots | ai.reconcile V12 : existence puis transitions typées, sourceIDs contraints/veto | Cinq plans réels ciblés satisfaits +un cas complet3lots94,688s. ÉchecsV4–V11 préservés, cas déjà connus ; doublon décision À vérifier persiste. analysis-reconciliation-v12-final.md. |
| Langue/confiance honnêtes et correction | unknownstring/backend, helperlanguage.tsFR/EN, badges |7testslabels, routing/adapter, importfrançais réel+correctionAPI/navigateur sans422 ; rapportpérimé/versionsconservés. Recette55PASS V11 ; fusionV12testée distinctement. |
| Reproductibilité/confidentialité/effets locaux | uv.lock, scriptsprépa, modèlespinned/SHA, servicesjetables | BackendV12242PASS/3skip/1warning ;48prépaPASS ; lint/types/buildPASS ;55recetteisoléePASS ;2panne/reprisePASS. Copiepersonnelle privée/autorisée/référenceparaphrase non scorable. |
| Activation sans retraitement imposé | envprivée sauvegardée, garde jobs/capture, restartlocal | Zérojobavant/après, mêmes nombres de ressources, intégritéSQLiteOK, quatreHTTP200. Aucun original privé retraité. Guide/MEMORA et state.md. |

Les seuils universels90% (toutes voix, noms, bruit, analyse) ne sont pas acquis ; les métriques bornées et limites sont publiées, sans réduire le périmètre ni simuler les moteurs.


## V1.1 — amélioration de confiance autorisée

| Besoin | Implémentation | Validation à la livraison |
|---|---|---|
| Contrôle microphone avant capture | microphone-check.tsx/helpers/CSS, Recorder entrée sélectionnée et exclusion test/capture |6testsunit et10contrôlesChromium avecAPIsmédias synthétiques ; recetteMediaRecorder réelleChromiumfakedevice PASS. Aucun micro physique. |
| Éditeur synchronisé et corrections comparables | playback.ts/tools +app : passage actif, boucle, vitesse, raccourcis, diff avant/après |3testsfondamentauxPASS, lint/types/buildPASS ; recettebrowserPASS. |
| Validation humaine actions/décisions, historique et sources | routes.py capacitéreview, table007report_reviews ; report-review.tsx |Tests droits/versions/conflits/historique/effacementvaleurs/IAimmuable ; APIréellePASS, browserPASS. Rapport-seul+édition invité permis, sources masquées conservées. |
| Renommage global versionné | speakers/rename, transcript_edits, SpeakerTools |Source et timestamps conservés, anciennesversions ; unknownexigeconfirmation ; testsbackend etAPIréellePASS, browserPASS. |
| Séparation acoustique locale réelle | diarization.py Resemblyzer/Silero/AHC ; workerjobversionné etendpoint |Corpus synthétique7cas+réserve4 ; nouvellevoix18/18segments, DERbruit12,37% ;15testsmodule+6workerPASS ; jobAPIréelPASS. Paschevauchement/identité/2hnaturelles. |
| Limites ressources et effets externes | CPU2threads1..8/restauration, ai._lock, SHApoids/offline, idempotencephasecomplete |Pipcheck160PASS, poids17Mo vérifiés, pas serviceexterne ni retraitementprivé. Migration007 additive appliquée après recette/gardejobs, empreintes sources inchangées etHTTP200. |


## Ajustements demandés après V1.1

| Besoin utilisateur | Code | Preuves/état |
|---|---|---|
| Transcription à hauteur bornée et barre de défilement | app.tsx, memora.module.css | Desktop/mobile clair/sombre : titre/correction fixes, citation au segment100 sans déplacer la fenêtre, zéro débordement. |
| Minutes seulement dans les éléments essentiels | Citations collapsed, reportNarrative dans app.tsx | Résumé/sujets : Sources repliées ; décisions/actions/questions : liens directs ; citations stockées inchangées. Recette layout synthétique PASS. |
| Français sélectionné transmis au décodeur final | memora-env.py, install.sh, configuration locale ; adaptateur MLX existant |22 tests routage/adaptateur,17 préparation PASS. Whisper Turbo fr/transcribe retenu ; dérive personnelle non reproduite, aucune garantie absolue. Handoffs diagnostic/comparaison. |
| Niveau et état de l’audio pendant capture | RecordingSignal + Recorder |22 helpers frontend dont signal PASS ;8 tests montés WebAudio/MediaRecorder synthétiques PASS. Recette intégrée19contrôles navigateur +9auditUI PASS ; micro physique non testé. |
| Refonte bloc intervenants et lecture | speaker-tools.tsx, playback-tools.tsx, transcript-tools.module.css | Lint/types/build PASS ;4 vues composant synthétique clair/sombre desktop/mobile, contrôles sans débordement. Validation4vues avec CSS WorkspaceFrame réel PASS, aucun débordement. |


## Présentation du rapport — ajustement utilisateur

Actions/décisions : cartes regroupant texte, sources et pied de validation ; responsable/échéance réunis en métadonnées, valeurs absentes explicites. Sections avec compteur, état vide sobre et limitations dans « Points à vérifier ». `app.tsx`, `memora.module.css`, `report-review.tsx` et module CSS dédié. Aucun changement IA/API/permissions ; validation et corrections restent séparées de l’original IA. Lint/types/build PASS, preuve IAB obtenue sur une réunion synthétique ; recette UI isolée élargie11contrôles PASS, confirmation/historique réels,8captures desktop/mobile clair/sombre sans débordement.


## Onde défilante et continuité de capture

| Besoin | Implémentation | État de validation |
|---|---|---|
| Historique audio qui défile, sans chiffres visibles | RecordingSignal :300pics réels, état simple, pause figée/reprise |9contrôles Chromium montés PASS dont déplacement de pics et gel pixels en pause ;4helpers PASS. |
| Changement d’onglet/arrière-plan | use-recording-continuity.ts : aucune pause/stop liée à visibilité, flush fragments, retour surveillé | 7contrôles hook Chromium à vrais onglets PASS ; vraie recette finale19browser+11UI PASS ; aucun micro physique. |
| Protection veille automatique locale | capture_awake.py, route propriétaire/loopback et heartbeat30s, caffeinate-i-t120, cleanup |40tests ciblés, suite complète294PASS/3skip/1warning ; assertion native réelle vérifiée puis libérée. |
| Vraie veille forcée/capot fermé | Limite OS/navigateur documentée, arrêt imprévu signalé et sauvegardes conservées | Impossible à garantir pendant suspension matérielle ; aucune promesse de continuité ni essai de sommeil réel de la machine. |
