# Adaptateur MLX — implémentation et tests isolés

Fichier nouveau `backend/api/memora/asr_mlx.py`. Aucun changement de `ai.py`, des routes ou du worker par cette tâche.

Contrat : `transcribe(path, tail_seconds=None, language='auto')` → segments `id/start/end/text/speaker/language/uncertain`, avec métadonnées supplémentaires `language_scope` et `language_confidence=None`. Le locuteur reste explicitement non identifié.

Configuration : `MEMORA_MLX_MODEL_PATH`, par défaut chemin absolu racine `.memora/models/mlx-large-v3-turbo`. Exige config.json et poids locaux non vides (weights.safetensors ou weights.npz) AVANT import runtime ; aucune résolution automatique d'un dépôt distant autorisée. Le téléchargement reste une opération distincte de l'intégrateur.

Décodage : Faster Whisper `decode_audio` utilise PyAV pour produire ndarray float32 mono16k, transmis directement à MLX ; pas de sous-processus FFmpeg. Audio vide/silencieux retourne []. Échantillons non finis et options invalides rejetés. Mode queue audio optionnel conserve offset temporel absolu ; final doit traiter le fichier entier.

MLX 0.4.3 reçoit `task='transcribe'`, `verbose=None`, langue None/fr/en, fp16, température de repli0/0,2/0,4, contexte précédent désactivé, seuils natifs compression2,4/logprob-1/no-speech0,6. Pas de beam_size non pris en charge. Pas de timestamps mots, diarisation, modèle supplémentaire ni enrichissement de vocabulaire inventé.

Horodatages MLX bornés à la durée réelle et enrichis offset ; texte non vide avec horodatages invalides (même partiellement) fait échouer l'inférence au lieu de publier une transcription amputée silencieusement. Pas de suppression arbitraire d'un segment sur le seul score de silence : le moteur applique ses critères, l'adaptateur signale les scores faibles comme incertains.

Mémoire : sous verrou local, finally remet `ModelHolder.model` et `.model_path` à None, appelle gc.collect puis mx.clear_cache. Tous appels MLX du processus doivent passer ce verrou ; aucun gain mémoire GPU effectif mesuré dans cette tâche. Recharge par appel assumée pour rendre place aux modèles rapport/chat.

## Limites de langue et de qualité

Source installée inspectée `.venv/lib/python3.12/site-packages/mlx_whisper/transcribe.py` : auto détecte UNE langue dominante à partir des premières30s puis utilise cette langue pour l'inférence. Le champ language n'est donc pas une détection locale segment-par-segment. `language_scope='initial_window_detection'` l'explicite ; aucune probabilité de langue inventée (None). Forcé fr/en indique `language_scope='forced'`.

Bilingue/alternance et risque de traduction non demandée doivent être mesurés par benchmark réel. Aucune précision supérieure à base n'est revendiquée avant ce benchmark. Les scores avg_logprob/no_speech/compression servent d'heuristiques d'incertitude, pas de preuve d'exactitude. Désactivation contexte précédent limite boucles/répétitions mais peut réduire cohérence entre fenêtres ; ajustement à décider sur preuves.

## Validation réellement effectuée

`cd backend && .venv/bin/python -m pytest test/test_memora_asr_mlx.py -q` : **9 réussis, 0,23s**.

Tests MOCKS uniquement : transmission ndarray/langue/tâche sans traduction ; options ; modèle local manquant sans runtime/download ; silence ; timestamps absolus de queue ; scores manquants incertains ; libération après succès et erreur ; rejet horodatages invalides entiers/partiels.

Ruff format et check réussis sur les deux nouveaux fichiers. **Aucun modèle MLX ni audio personnel exécuté dans cette tâche.** Intégrateur responsable branchement et validation IA réelle après téléchargement officiel.

## Benchmark réel préparé, sans inférence anticipée

`scripts/memora-benchmark-mlx.py` est prêt. Avant import des moteurs ou inférence : présence config + weights.safetensors + memora-model.json, taille égale au manifeste, calcul SHA256 complet identique, dépôt officiel attendu et révision présents. Puis fonctionnement offline imposé aux bibliothèques. `--check-only` exécuté pendant téléchargement : refus explicite modèle incomplet, code2, aucune inférence. Ruff et py_compile réussis.

Commande après téléchargement vérifié :

`backend/.venv/bin/python scripts/memora-benchmark-mlx.py > agents/logs/benchmark-mlx.log 2>&1`

Par défaut compare moteurs séquentiels sur cinq fixtures SYNTHÉTIQUES : python-sentence.wav, french-realistic.aiff, mixed-native.wav, english.wav, silence3s créé localement. Baseline base cache local explicite, pas de résolution HF. Baseline libérée avant phase MLX. Résultats `agents/logs/benchmark-mlx.json` écrits après chaque cas : texte attendu/obtenu, segments/langue/scope/incertitude, durée audio, temps mural et RTF, WER/CER strict et variante numérique explicite. Silence référence vide : WER/CER mathématiquement indéfinis donc null, nombre insertions et hallucination booléenne renseignés.

Options : `--engine both|baseline|mlx`, `--language auto|fr|en`, `--cases python french-realistic mixed english silence`. Exemple ciblé : `backend/.venv/bin/python scripts/memora-benchmark-mlx.py --engine mlx --language fr --cases python french-realistic`.

Chronométrage volontairement conforme aux adaptateurs : temps mural inclut décodage et cleanup ; baseline premier cas inclut chargement puis reste chaude ; MLX recharge/décharge par cas non silencieux. RTF décrit ce fonctionnement réel, pas uniquement noyaux GPU chauds. Ne pas présenter ces mesures comme comparaison hardware isolée. Aucune supériorité ni qualité MLX revendiquée dans cette préparation ; l'intégrateur exécutera après disponibilité complète.

## Benchmark étendu anti-hallucination (préparé, aucune inférence)

Deux cas ajoutés, total sept cas par défaut :

- `python-tail` → `python-sentence-tail10s.wav`, 12,6433125s : préfixe Python original vérifié octet pour octet, puis exactement10s silence numérique. Texte attendu identique à la phrase de2,6433125s.
- `white-noise` → `benchmark-white-noise.wav`, 10s bruit blanc synthétique seul, RNG seed20261025, RMS effectif0,0014996 soit -56,48dBFS, peak0,006958. Dépasse le seuil d'amplitude0,001 de l'adaptateur : ne contourne donc pas le test par un simple retour « silence » avant moteur.

Fixtures mono PCM16bit16k créées avec numpy/wave, sans micro ni données personnelles. Génération reproductible dans `ensure_synthetic_negative_fixtures()`. Vérification WAV, préfixe et silence exact réussie ; Ruff et py_compile réussis. Garde manifeste/taille/SHA256 complet inchangé avant toute inférence.

Critères enregistrés dans JSON : bruit/silence doivent produire texte vide ET aucun segment non vide. Python avec silence doit conserver exactement le texte attendu après normalisation ET ne pas générer segment non vide commençant dans les10s ajoutées (tolérance150ms). Suffixe inattendu listé si le préfixe attendu correspond. WER/CER reste mesuré ; aucune correction automatique du résultat modèle pour le faire passer. Latence murale/RTF conservées, et différence de temps vs cas Python simple si présent dans le même run/moteur. Pas de seuil de latence promis sans mesure.

Commande ciblée après téléchargement vérifié : `backend/.venv/bin/python scripts/memora-benchmark-mlx.py --engine mlx --cases python python-tail white-noise silence > agents/logs/benchmark-mlx.log 2>&1`.
