# Reprise V1.1 — confiance et correction

Travail autorisé « Goooo » sur quatre priorités : contrôle micro, éditeur synchronisé, validation humaine, séparation locale. ROOT a intégré UI/worker et les nouveaux parcours ; tous agents ont libéré leurs fichiers. Références : human-review-v11.md et diarization-local-v1.md. Main encore ancienne version, aucune migration007/restartmain réalisé à ce point.

Sources figées : diarization.pySHA08eed385c1266938136d4564361099f8ba5c36586c8bc6e0ef97bb4cd36983ae ; 2threads CPUdéfaut/restauration,15tests module. ROOTworker6tests, phasecomplete atomique etprovenance transcript_edits007. APIroutepermissions/report-onlyreview, métadonnéespréservées, revisions/conflits testés. Fullbackendfinal284PASS/3RedisSkip/1warning26,78s, scripts48PASS3,82s, Ruff69fichiersPASS. Frontend16testsPASS, lint/types/buildPASS ; OpenAPI/SDKexport/checkPASS.

Première recetteisolée : API41PASS79,36s, puis browserfail aprèsauth/import sur getByLabelStatutexact (form visible, label incluaitoptions). Logs/screenshot/summarypréservés v11-attempt1-*. Accessible names explicites ajoutés aux selects Statut et Étiquette actuelle ; rebuild/lint/types finis, sourcesUIgelées. Microcomposant isolé :10contrôlesChromiumAPIsmédia mocks +6testsunit, complémentcodecMediaRecorder réel àfaire dansrecette.

**Recette finale en cours** sessionexec36010 ; agents/logs/v11-isolated-final-run.log et isolated-{api,browser,ui-audit}.log/summary.json. Commande : PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Users/kalagasergeeric/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing' backend/.venv/bin/python scripts/memora-verify-isolated.py --asr-engine mlx-whisper --french-asr-engine parakeet-mlx --timeout2400. Ne pas modifier source chargée pendant recette. Si échec, inspecter premièrefrontière et préserver preuves, corriger/rebuild seulement nécessaire.

À finir : recettebrowser/audit et inspectioncaptures ; régénérer sourceprovenanceJSON aprèsfixaria ; docs/testing/requirements/state/plan finaux. Puis mainactivation : vérifier0jobs/aucuneécritureaudio récente, arrêterAPI/frontend via scripts sûrs, migration007 via memora-migrate.py qui sauvegardeSQLite/contrôlechemins+verrouworker, redémarrerbuildproductionloopback, contrôlerHTTP/quatreports/intégrité/comptages sansretraiteroriginalprivé. ModèleResemblyzerdéjàpréparé17MoSHApin, depmarkersDarwinarm64seulement/setuptools80compatible. Envmainpasmodifiée, modèlesASR/Gemmaconservés.

Commits locaux autorisés sanscoauteur, aucunpush/distant. Gitinitialbfa446a ; changementscourantsàcommitter APRÈSpreuves/docs. Supprimeraucunhistorique/sauvegardeGitcaruserdéjàfaitréinitialisationpropre ; nepasrecréerbackupGit. SauvegardesSQLitetechniquesprivées distinctes etnécessairesmigrationautorisée. Secrets/audios/modèles/bases/logs horsGit.

Limites : pasmicrophysique/Safari/iOS/voixnaturelles/overlap/identité. DERréserve2/3voix7,57/8,10%, gainbruit12,37%,18/18segmentsattribués, référencesTTSénergie/grille20ms pasprécisionuniverselle. AnciennesnotesV1pasencoreactualiséespartout : nouveaujalonencoursprimedessus.


## CLÔTURE — état actuel prime sur la reprise ci-dessus

69contrôles composésPASS :41API (attempt2),19browser(attempt3),9auditUI(finalautonome21,88s), codeproductionfigé. Les trois interruptions de recettes ont été diagnostiquées et préservées, voir testing.md. Microphone réel jamais sollicité ; MediaRecorder réel avecfakeinput testé, capturesmobile relues. Backend284PASS/3skip/1warning ;15module+6workerinclus ;48prépa ;16frontendunit ;Ruff69/lint/types/build/OpenAPI/SDKPASS.

Main migré007 et redémarrélocalement,0jobs, intégrité etcomptages/empreintessourcesidentiques, quatreHTTP200, nouvellesrouteschargées. Aucune référencepersonnelletraitée, aucunmodèleOllamachangé. Docs/state/requirements/testing actualisés. Prochaineaction : essaiutilisateur etcommitlocal (voirgitlogpourhashfinal), aucunpush/coauthor. Aucuneimplémentationobligatoire restante dans le jalon ; limites qualité/plateformes documentées.
