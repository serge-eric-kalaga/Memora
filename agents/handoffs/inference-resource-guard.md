# Sérialisation des inférences locales

ai.generate acquiert désormais le même verrou process-local que Faster Whisper ; la branche MLX ai.transcribe acquiert également ce verrou avant le verrou interne de l’adaptateur. Aucun verrou ajouté autour report/answer : libération entre chaque génération/lot. FWH conserve son verrou unique existant ; aucun chemin de génération dans son bloc ASR et aucun ordre inverse de verrous MLX trouvé.

Test concurrent instrumenté, deux threads : génération retenue par événement, second thread attend effectivement le verrou avant entrée dans ASR simulé ; après libération, ASR entre. Deux variantes succès/ConnectError vérifient que l’erreur libère le verrou et que le verrou final est libre. Aucun modèle chargé, aucun HTTP réel.

`python3 scripts/memora-test.py test/test_memora_ai.py test/test_memora_asr_mlx.py -q` :27PASS en0.28s sans avertissement. Ruff PASS. Limite : garde uniquement ce processus/application ; ne gouverne pas des clients externes Ollama ni benchmark direct de l’adaptateur (benchmarks séquentiels).
