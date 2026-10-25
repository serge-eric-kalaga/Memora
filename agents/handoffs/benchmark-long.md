# Benchmark audio long synthétique préparé

Script `scripts/memora-benchmark-long.py`, génération par défaut **sans inférence**. `--minutes` défaut5, borne1–120 minutes pour la génération technique. Le fichier `.memora/qa/long.wav` est écrit progressivement sans allouer un waveform de deux heures en mémoire : cycles complets français/anglais, silence0,3s entre fixtures, intervalle résiduel silencieux, puis phrase finale Python intacte. Aucun mot de fixture n'est coupé pour atteindre la durée demandée. Métadonnées/hash/positions dans `.memora/qa/long-source.json`.

Vérifié : génération1min (60s, trois cycles FR/EN), phrase finale PCM identique à la fixture, début phrase finale57,3566875s, WAV mono PCM16bit16k. `git check-ignore` confirme WAV et sidecar exclus Git. Ruff et py_compile réussis. **Aucune inférence ni téléchargement exécuté.** Le fichier actuellement présent est la génération de60s de ce contrôle, pas une preuve IA de5min.

Génération uniquement :

`backend/.venv/bin/python scripts/memora-benchmark-long.py --minutes 5`

Inférence réelle explicite, seulement après disponibilité du modèle :

`backend/.venv/bin/python scripts/memora-benchmark-long.py --minutes 15 --infer > agents/logs/benchmark-long.log 2>&1`

Pour20min remplacer15 par20. Avant tout import/inférence MLX, le script importe par chemin `memora-benchmark-mlx.py` et réutilise **verify_model** (manifeste, taille, SHA256 complet, provenance), sans dupliquer ni affaiblir la vérification. Puis charge l'adaptateur local, en mode offline. Pas de commande de téléchargement.

Résultat local `agents/logs/benchmark-long.json` : génération réelle et hash, durée murale/RTF, nombre de segments, premier début, dernière fin, maxend, segments des premières/dernières30s, marqueur initial et phrase finale (partout/proche fin), fin temporelle atteinte, langues/incertitudes, **tous les segments transcrits**. Le texte complet reste dans les segments, sans doublonner une seconde copie dans le JSON.

Limites explicites : présence des marqueurs et timestamps est un diagnostic de couverture, pas la preuve que chaque mot répété est correct. Une exécution5min n'est pas validation2h. La borne120min du générateur n'est pas une promesse de capacité RAM/GPU pour l'inférence entière ; l'adaptateur actuel décode le fichier entier et la consommation augmente avec sa durée. Le test doit être choisi selon les ressources réellement disponibles. AutoMLX utilise une langue initiale dominante : inspecter alternance FR/EN et éventuelle traduction.
