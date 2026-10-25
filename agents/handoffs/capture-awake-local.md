# Capture : bail temporaire contre veille inactive macOS

Code livré : `backend/api/memora/capture_awake.py`, route dans routes.py, cleanup dans api/utility/lifespan.py, tests `backend/test/test_memora_capture_awake.py`. Aucune migration, modificationréglagesOS ou capturemicro. ModuleSHA c34470c3604d08fa7c5ba48caea766d7549299c03508ce5943062e0845154102.

## Contrat

`POST /api/memora/meetings/{id}/capture-awake`, corps `{ "active": true/false }`, réponse `{ "supported": true/false, "active": true/false }`.

Dépendance current_user obligatoire, compteincarnation ownerUID et propriétaire id vérifiés côté backend, compte supprimé refusé. Headerpartage explicitement403, autrecompte404. Active exige réunionmode recording, étatrecording oupaused, sinon409. Release accepte tout état de la même réunionowned. Requêteactive nonloopback → supportedfalse/activefalse (pas affirmation de protéger un navigateur distant). Plateforme autrequemacOS, Docker ou binaireabsent :false gracieux. Aucune commande ni paramètreprocess contrôlé par client.

Commande fixe : `/usr/bin/caffeinate -i -t 120`, stdout/stderr/stdinDEVNULL, closesfds. Aucun `-d`, aucune modificationpmset. Un bailenmémoire maximum par ownerUID ; nouveauheartbeat/meeting remplace proprement ancienprocess, autreowner indépendant. Releaseancienmeeting ne peut pas interrompre nouveau bailowner. Nettoyageexpiration/poll aux requêtes, atexit et lifespanfinally ; délaiOS120s demeure si crash/SIGKILL du backend. Aucune nouvelleinfrastructure ou tâchepermanente. Si arrêtprocessraced/échoue, timeoutnatif reste borné.

FrontendROOT doit renouveler environ30s tant enregistrement OU pause voulue, et libérer à finalisation/annulation/démontage si possible. Sansheartbeat (ongletfermé/crash), assertionexpire. Aucun succès n'est promis si lesheartbeatssont suspendus plus120s : utiliser informationsavertissementsappropriées.

## Tests

`python3 scripts/memora-test.py test/test_memora_capture_awake.py test/test_memora_domain.py -q` : **40PASS2,27s** (8nouveaux+32domaine). Ruff4fichiers conformes. Logs `agents/logs/capture-awake-tests-final.log`. Processmocks uniquement dans testsisolés : commande fixeTTL/flags, renouvellement/ownership/max1bail, oldrelease, expiry/shutdown, échecspawn/nonprischarge, killaprèsattente, permissions/états/nonlocal. IdentitésJWT simulées par fixtures existantes ; ces tests ne remplacent pas la validationauth réelle du template.

**Smoke natif réel distinct** : moduleisoléimporté sansconfigprincipale, bail synthétiquecréé, `/usr/bin/pmset -g assertions` lu enmémoire en filtrant exclusivement le process créé. AssertionPreventUserIdleSystemSleep vérifiée, absencePreventUserIdleDisplaySleep vérifiée ; releaseall immédiatement, aucun bail/process détenu ensuite. Aucune sortieglobale de pmset niPID/app privée enregistrés dans logs. Aucun vrai passage enveille déclenché.

## Limites explicites

Protection contre veille **inactive du Mac hébergeant backend local seulement**, pas garantie de captureweb enarrièreplan. Ne bloque ni veillemanuelle, ni fermeturecapot, ni extinction/redémarrage, ni manquebatterie ; écranpeut dormir. Ne garantit pas que navigateur/OSgardemicro/MediaRecorder pendantverrouillage ou suspensionsd'onglet. La repriseaprèsréveil et sauvegardeprogressive relèvent d'autres mécanismes, à tester séparément. Pas qualification Safari/iOS ni laptopcapotfermé, aucun contournement de restrictionsmacOS.

Aucun bail natif laissé actif par le sous-agent. Pas de redémarrageapplication effectué ; intégrationfrontend/recettenavigateur par ROOT.
