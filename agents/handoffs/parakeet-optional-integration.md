# Adaptateur Parakeet optionnel intégré, activation différée

Fichiers réservés à cet agent : backend/api/memora/asr_parakeet.py, backend/test/test_memora_asr_parakeet.py, pyproject/uv.lock, scripts/memora-install.sh, .env.memora.example, scripts/memora-verify-isolated.py. Aucun ai.py, testIAexistant, frontend ou backend.env modifié. Aucune inférence ou restart.

## Implémenté

Adaptateur paresseux, runtimePath vérifié+model_typeparakeet explicite (configNemo n'a pasmodel_typetoplevel). Pinsrepo/révision/poids/5assets. SHAcompletinitial puis cache par fingerprintstat dev/ino/size/mtime_ns/ctime_ns couvrant manifeste/poids/5assets, invalidationdèschangement ; pasdecachebypasssurassetmodifié, rejeuSHAavantcache. Symlinkassetexterne refusé. PyAV16kmono, chunk30s/overlap2benchmarkés, tailoffset, timestampsnativestousvalidés (start>=durationrefusé), pasderepairdetempssilencieux ; libérationcacheGPUfinally. Pasdedownload/autoremotePython : loaderreçoit Pathlocal vérifiéetmodeltypeconnu.

language='unknown' string compatibleCorrectionPydantic, confidenceNone. uncertainTrue conservateur signifie scorefournisseurabsent/noncalibré, paspreuvephrasefausse. Parakeet ne force pas fr/en ; factory peut sélectionner ce moteurpourrequêtefrsansprétendrelanguedétectée. LaUIunknown est traitéeparROOT, pascetagent.

## Dépendances et install

pyproject ajoute mlx-audio[stt]==0.6.1 limitéDarwinARM64. uv0.13.5 installé dans.memora/tooling. Lockrésolu : septajoutsseulement miniaudio1.71,mlx-audio0.6.1,safetensors0.8.0,sentencepiece0.2.2,sounddevice0.5.6,Transformers5.20.2,zstd0.25.0 ; aucuneversionexistantechangée selonuv. Dryrunfrozen ajouteces7+réinstalllocaleditablebackend-template, MLX/Metal0.32.4 inchangés. **Syncbackenddifféré pendant recetteGPUqa ; attendre signalROOT.** Logs parakeet-uv-lock.log/parakeet-uv-sync-dry-run.log.

Installer reconnaît primaryparakeet-mlx et optionMEMORA_FRENCH_ASR_ENGINE=parakeet-mlx, pathMEMORA_PARAKEET_MODEL_PATH distinct ; aucunevaleuractivepar défaut. Frenchunset gardecomportementexistant. PlateformeMacARM64vérifiéeavantdownload. Unseuldownloadsi primaryetFrenchparakeet, cheminsavec espaces correctementquotés. MEMORA_MLX_FR_MODEL_PATH fullWhisperoptionantérieure conservée. Exempleclécommentéeuniquement, pasd'activationmain.

Runnerisolé conserveclésFrench/parakeet/fullFR et CLIprimaryparakeet. Attentionoverride--asr-engineseulne désactivepasFrenchhérité ; pour benchmarkmoteurunique, passerexplicitementMEMORA_FRENCH_ASR_ENGINE='' ou prévoir CLIdepolitique. Runnerdéfautdoitreproduirepolitiquemainvalidée.

## Validation CPU sansGPU

16testsadapterPASS : hashes/cache6fichiers/invalidation5assets/mismatchlicence/corruption/manifeste/symlinkexterne/absentmodèlesansruntime, tailtempsnatifs/3argslangue, paramètreschunkfixes, failurecleanup, vraidécodeWAV/WebMOpus.bin et roundtripmodèlesSegment/Correctionréels extraitsASTsanschargerDB.

3testsinstaller shellisolésPASS, no realnpm/uv/migrate/network. RuffPASS, sh-nPASS. Logs parakeet-adapter-unit-tests.log/parakeet-installer-tests.log. QualitéASRpasévaluéeparcestests ; benchmarksindépendantsrestentpropriétéparent/api_tests.

## Factory à intégrer par ROOT après résultats

Aprèschoixengineexistant, si languagefr ETtail_secondsisNone, prendreMEMORA_FRENCH_ASR_ENGINE nonvide sinonengine. Brancheparakeet-mlx importparesseuxmoduleadaptateur et transcribe sousmême ai._lock ; nepasforcerlangue/score. English/auto/live restentconfigmoteurexistante. Moteurinconnu restererreurexplicite, pasfallbacksimulé. Ne pasactiverconfigurationmain ni réanalyseraudiopersonnel automatiquement.

## Ajout runner de politique explicite

`--french-asr-engine` choicesinherit/disabled/mlx-whisper/parakeet-mlx/faster-whisper, défautinherit. Disabled vide la clé, une valeur explicite remplace French seulement, liveinchangé. Exemple recette future `--asr-engine mlx-whisper --french-asr-engine parakeet-mlx` ; moteurunique `--french-asr-engine disabled`. Remplace la précaution de overrideparenv ci-dessus. 7testsconfigurationofflinePASS, logparakeet-isolated-policy-tests.log. La politiqueFRseule n'est pasdéclaréevalidéeparlesrunsParakeetglobaux.

## Synchronisation autorisée après QA terminée

ROOT a donné signal explicite : `uv sync --project backend --python3.12 --frozen` terminéexit0, septdépendancesajoutées+editablebackendreconstruit, versionsMLX/Metal/PyAV/NumPy/Hubexistantesconservées. uvpipcheck144packagesPASS, importpackageCPUmlx_audioPASS sansloadmodèle/inférence, versionsloguées. Aucunrestart/envmainmodifié. Logs parakeet-uv-sync.log/parakeet-backend-pip-check.log/parakeet-backend-import.log. Suiteconsolidée27testsCPU/offline relancéeaprès syncPASS (17adapter/3installer/7policy). FactoryroutageéditéeparROOT, pascetagent. Validationpipelineetpolitiquepropre toujoursresponsabilitérecetteROOT, pasdéduite desbenchsglobaux.
