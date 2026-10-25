# Carte du code

- `backend/api/__init__.py` : application template, montage routeur Memora ; CORS local explicite et logs chemins Memora masqués.
- `backend/api/services/{jwt,authorization}.py` : authentification et permissions template, réutilisées pour propriétaires.
- `backend/api/memora/routes.py` : domaine réunions, ressources, invités, versions, partages, quotas, configuration, notifications et outbox.
- `backend/api/memora/store.py` + `migrations/*.sql` : stockage SQLite transactionnel isolé, migrations idempotentes et historique.
- `backend/api/memora/worker.py` : file persistante single worker/verrou système, snapshots ASR, analyse versionnée, SMTP capture et rétention.
- `backend/api/memora/ai.py` : sélection ASR MLX/Faster Whisper, Ollama Gemma JSON local, sources validées et découpage/réduction bornés.
- `backend/api/utility/lifespan.py` : lancement et arrêt worker.
- `frontend/src/features/memora/{app.tsx,api.ts,storage.ts,memora.module.css}` : écrans domaine, contrats normalisés, audio IndexedDB, CSS responsive.
- `frontend/src/app/{reunions,partage,parametres}` et `page.tsx` : routes UI ; `mapi/[...path]/route.ts` : proxy serveur JWT/partages avec contrôle origine et tailles.
- `frontend/src/features/memora/i18n.ts` : traductions FR/EN ; voir import useMemoraText dans app.tsx.
- `scripts/memora-{install,start,stop,status,backend,frontend}.sh` : cycle local ; env.py génère secrets protégés, demo.py crée identité synthétique explicite.
- `scripts/memora-mail-capture.py` : SMTP sink local1025, inbox HTTP8025 sans relais externe.
- `backend/test/test_memora_{domain,ai}.py` : tests isolés, `scripts/memora-test.py` : toute suite sur données jetables.
- `scripts/memora-{qa-local,qa-improvements,e2e-api,resilience}.py` : intégrations IA et API réelles synthétiques.
- `frontend/tests/memora-e2e.mjs` : parcours navigateur réels avec microphone Chromium factice.

Sources de vérité des résultats : testing.md + handoffs/*.md ; les logs volumineux sont locaux et ignorés.

## Ajouts précision/recette

- api/memora/asr_mlx.py : adaptateur local AppleSilicon, nettoyage GPU, langue dominante par portion vocale explicite. ai.transcribe sélectionne MEMORA_ASR_ENGINE/MEMORA_LIVE_ASR_ENGINE ; MLX+SileroVAD final/direct activé après benchmark supérieur.
- scripts/memora-download-mlx.py : téléchargement officiel fragmenté reprenable + SHA256 ; scripts/memora-benchmark-mlx.py : synthétiques FR/EN/mix/silence, métriques et refus modèle incomplet.
- routes.retranscribe + AnalyzeRequest : request_id persistant migration003, historique source ; rapportrevision distinct versiontranscript.
- scripts/memora-launch.py : processus détachés avec stdinfermé + contrôleport ; utilisé par start.sh.

## Identité, maintenance et recette isolée

- `backend/api/database/models.py`, `services/jwt.py`, `services/auth/login.py`, `migrations/versions/0007_account_uid.py` : identité permanente et JWT liés à la création du compte.
- Domaine migrations004/005 : owner_uid, emails liés, tombstones de suppression ; `store.delete_owner` et `views/auth/user.py` purgent le domaine avant suppression du compte.
- `scripts/memora-migrate.py` et `memora-bind-owners.py` : sauvegarde privée, migrations arrêtworker, rattachement prudent/dryrun.
- `worker.maintenance` : mail/rétention indépendants, échecs réessayés sans tuer le worker ; `test_memora_worker_maintenance.py` reproduit les pannes.
- `scripts/memora-verify-isolated.py` : API/UI/SMTP jetables puis recettes réelles ; logs et handoffs préfixés isolated-.
- `scripts/memora-qa-long-context.py` : preuve réelle fait/citation en fin de trois lots ; `memora-benchmark-long.py` : audio long synthétique, indépendant du test texte.
- `ai.reading_units/source_context` : conserve locuteur, temps et provenance avant lots ; `generate` refuse troncature/décalage de contexte Ollama.

- `frontend/src/features/memora/language.ts` : badges forced/initial/speech_region et aide FR/EN ; `frontend/src/app/mapi/[...path]/timeout.ts` : délai chat configurable, REST distinct.
- `scripts/memora-qa-modality.py` et probes Gemma : régression décision future/fait accompli, comparaison synthétique et mesure mémoire ; aucun contenu utilisateur.

- Domaine006 + `worker.process` : checkpoints atomiques source→report→complete, source_version distincte de version initiale, result_report_id ; tests `test_memora_worker_resume.py`. `store.init` réconcilie métadonnées processing sans tâche active ; `fail_job` relit checkpointSQL.

## Précision supplémentaire25/10

- `backend/api/memora/asr_parakeet.py` : adaptateurParakeetlocal, assetsSHA/cacheinvalidation, PyAV/nativeclock, languageunknownstring, confidenceabsente, finiteguard. `ai.transcribe` routeFRfinaloptionnelleMEMORA_FRENCH_ASR_ENGINE, autreslangues/directinchangés etverroucommun. Testsasr_parakeet/routing séparés.
- `scripts/memora-download-parakeet.py`, `memora-download-large-v3.py` : modèlesdistincts épinglés/attribution/check-only, jamaismodèlesOllamaremplacés. `memora-env.py` recommandenouvellesconfigDarwinARMFRParakeet, preserveexistingexact. Installerpréparelesmoteursconfigurés.
- `scripts/memora-benchmark-accuracy.py` : corpusv1/v2/v3figés, variantes/WERstrict+numeric/CER/probes/latence/mémoire ; production-factory vérifiedispatchréel. Défautadaptateurcourantversionné ; historiquesnécessitentsnapshotlogexplicite.
- `ai._report_plan_payload/_reconcile_report_statuses` : classificationcibléeactifs seulement, résumésdérivésnonclassifiés, littérauxtargets+vérificationchangementsummary-only, statutstypésparcatégorie, gardesIDs/ordre/quotes/context. Multi-lotsrésuméschronologiques, singlebatchinchangé. EnvalidationV10, nepasdéduireactivationducodeprésent.
- `scripts/memora-benchmark-analysis.py`, `memora-qa-cross-batch.py`, `memora-qa-reconciliation-plan.py` : vraisappelslocalsetrevues explicites ; scoresmanuelscomplets etéchecspréservés. `backend/test/fixtures/memora/analysis-long-cases.v1.json` :3caslongsinéditsfigés, IDsremappésopaquesavantmodèleparrunner.
- `frontend/src/features/memora/language.ts` : unknownFR/ENhonnête, aidefiabiliténonchiffrée ; recetteisoléeajoutefrimport/rapport/correctionAPI+browser. `memora-verify-isolated.py --french-asr-engine` explicitementtestable sanschangerMain.


## V1.1 — confiance

- frontend/src/features/memora/microphone-check.tsx et microphone-check.helpers.ts : test explicite/entrée/niveau/échantillon local, intégré à Recorder dans app.tsx.
- playback.ts/playback-tools.tsx : repères, boucle, vitesse/raccourcis ; app.tsx synchronise passage actif et diff de correction.
- report-review.tsx : couche humaine séparée de Report.data IA, formulaires/history ; routes.py capacités review et edit distinctes, tables report_reviews/transcript_edits via007.
- speaker-tools.tsx : renommage global et job volontairediarize, droits audio requis seulement pour séparation.
- diarization.py : ResemblyzerCPU/Silero/AHC, poidsSHAofflinemode, abstentionmultivoix ; worker.process_diarization commitsatomiques/version+1/phasecomplete. scripts/memora-prepare-diarization.py et benchmark/reserve synthétiques.
- Tests nouveaux : test_memora_human_review.py, test_memora_diarization.py, test_memora_worker_diarization.py ; frontend/tests/memora-microphone-*.mjs/memora-playback.test.mjs ; recettes API/navigateurétendues.

Capture persistante : app/layout.tsx→CaptureProvider (capture-session.tsx)→CaptureRuntime ; app.tsx→CaptureSlot ; capture-runtime.tsx possède médias/queue/IndexedDB/continuité, audio-language.tsx fournit le sélecteur. MeetingChat dans meeting-chat.tsx, styles dédiés ; API conversation routes.py→ai.answer(history), autorisation répétée après inférence.

meeting-chat.tsx→chat-answer.ts (nettoyage présentation/copie groupesuN) ; AnswerBody JSX échappé, sourcesdetails bornées et questionAnchorsticky. Tests memora-chat-answer.test.mjs et memora-meeting-chat-browser.mjs incluent réponseslongues/30sources ; memora-ui-audit.mjs inclut4vues longuesproduction.

components/ui/confirmation.tsx→useConfirmation promesse+dialogue action nommé, confirmation.module.css ; repose Modal partagé (modal.tsx/CSS), bouclefocus explicite. MeetingContent app.tsx l’utilise retranscription/suppression ; SpeakerTools pour séparation. TestsUIaudit3actions +E2E/importrecovery adaptés aux rôlesdialog/boutons au lieuévénementswindowdialog.
