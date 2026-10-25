# MLX : régions de parole et négatifs synthétiques

Adaptateur uniquement : Silero VAD déjà livré avec Faster Whisper, min_silence300ms, padding200ms, durée maximale de région infinie (pas coupe arbitraire de mots). Rejet sans modèle si VAD aucune parole. Chaque région est transcrite indépendamment task=transcribe, language=None en auto ; modèle conservé entre régions, libéré en finally. Offsets/timestamps relatifs rétablis dans audio source complet et IDs uniques. Un résultat texte sans timestamps exploitables dans une région fait échouer tout le résultat, pas omission partielle silencieuse.

`language_scope=speech_region_detection` en auto, forced sinon ; confiance null. Signifie langue dominante détectée séparément par région de parole, pas détection par mot. Une alternance sans pause dans la même région reste une limite. Silero peut manquer une parole faible : ces corpus ne prouvent aucune garantie générale ni la qualité de l’audio utilisateur (jamais lu).

Modèle officiel SHA complet vérifié par le script avant chaque benchmark réel. Aucun téléchargement supplémentaire.

Preuves `agents/logs/benchmark-mlx-vad.json` et `benchmark-mlx-vad-negative.json` (+logs correspondants) :
- Mixte11,7957s : attendu FR+EN, obtenu FR+EN sans traduction ; seul Memora→Mémora. WER3,85%, CER0,62%, 2,3608s, RTF0,2001. Régions FR0–6,84s puis EN7,48–11,72s. Ancienne inférence fichier entier traduisait EN en FR (~46%WER selon benchmark-auto préservé ROOT).
- Bruit blanc10s RMS≈−56dBFS : texte vide, 0segment, 0mot ajouté ;0,0316s. Ancien moteur sans VAD inventait Thank you.
- Python : WER/CER0%,0,7683s ; anglais WER/CER0%,0,8534s.
- FR complexe : WERstrict20%, CER20,95%, WERnormalisé chiffres2,5% (M. vs Monsieur),1,0098s ; même qualité avant VAD, base17,5%normalisé.
- Python+10s silence : WER/CER0%, aucun texte ajouté,1,4001s, RTF0,1107.
- Silence3s : texte vide/0segment,0,013s.

Normalisations détaillées dans les JSON : strict conserve accents et transforme ponctuation/majuscules ; normalisation des chiffres seulement pour les équivalences explicites du corpus. Les taux portent sur synthèse vocale, pas des réunions naturelles.

Tests mocks : indépendance langues de deux régions, offsets exacts/IDs et maintien modèle entre régions, VAD vide ne charge pas modèle, nettoyage/erreurs/horo existants. `python3 scripts/memora-test.py test/test_memora_asr_mlx.py test/test_memora_ai.py -q` :29PASS en0.34s. Ruff PASS. Pas activation/configuration/service modifié par cet agent. Le champ language_limit et timing_policy du script benchmark sont anciens textes génériques : les segments JSON et ce handoff décrivent précisément la nouvelle portée VAD, ROOT doit actualiser ces descriptions avant documentation finale.
