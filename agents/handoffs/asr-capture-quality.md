# Audit capture et précision ASR — données synthétiques uniquement

Aucun fichier audio personnel ni réunion utilisateur consulté. Aucun microphone activé. Aucun nouveau modèle téléchargé. Aucun fichier backend/frontend modifié par cette tâche.

## Résultats mesurés

Moteur de comparaison : Faster Whisper base déjà présent, CPU int8, 2 threads, beam5, multilingual=True, contexte précédent désactivé. Trois corpus voix macOS Thomas/Samantha. WER = distance de Levenshtein mots / nombre de mots attendus ; CER = distance caractères / nombre de caractères attendus. Normalisation NFC, minuscules, ponctuation remplacée par espaces, espaces fusionnés, accents conservés. Les chiffres vs mots comptent comme erreurs dans la mesure brute.

| Corpus synthétique | PCM original WER/CER | Opus32kb/s | Opus64kb/s | Opus128kb/s |
|---|---|---|---|---|
| FR court, 8,518s | 10,53% / 4,00% | 21,05% / 9,60% | 10,53% / 4,00% | 10,53% / 4,00% |
| EN court, 8,568s | 0% / 0% | 0% / 0% | 0% / 0% | 0% / 0% |
| FR chiffres/négations/lieux, 15,658s | 31,11% / 22,13% | 40% / 28,85% | 40% / 28,85% | 31,11% / 21,74% |

24 essais réels : quatre codecs/profils × trois corpus × VAD oui/non. VAD oui/non donne exactement les mêmes textes sur ces trois corpus. Aucune différence de durée après décodage Opus et retour mono16k (delta 0ms dans ces fichiers). Cela ne prouve pas que VAD soit sans risque sur voix naturelles faibles/bruitées.

Mesure complémentaire FR réaliste avec normalisation numérique EXPLICITE et limitée au corpus : « deux mille quatre cents »→2400 ; « vingt quatre mille »/«24 000»→24000 ; « douze »→12. PCM : WER17,5%, CER6,42% ; Opus128 : 17,5% / 5,96% ; Opus32/64 : 27,5% / 14,22%. Les noms propres et CFA ne sont pas normalisés : leurs erreurs demeurent mesurées. Ces résultats montrent des erreurs lexicales réelles du petit modèle même en source synthétique propre ; changer seulement le codec ne suffira pas.

## Phrase de référence Python

Fixture `backend/test/fixtures/memora/python-sentence.wav`, mono16k, et `.aiff` original Thomas145wpm. Attendu : « Aujourd'hui nous allons parler du langage python. ».

Base automatique : « Aujourd'hui nous allons parler du langage Python. », WER/CER0%, 0,895s.
Base langue forcée fr : même résultat, WER/CER0%, 0,414s. Audio2,643s.

Il s'agit d'une reproduction synthétique de la phrase fournie, pas d'une transcription ni d'un diagnostic de l'audio personnel de l'utilisateur.

## Parcours MediaRecorder réel sans microphone

`scripts/memora-qa-capture-browser.cjs` : Chromium existant, Web Audio décode `english.wav` puis alimente `createMediaStreamDestination()` ; aucun `getUserMedia`. MediaRecorder identique au choix courant de l'app, timeslice1s pour le test. Une seule instance, pause/reprise après suspension de la source synthétique pour conserver le texte attendu.

Résultat : MIME `audio/webm;codecs=opus`, bitrate EFFECTIF128000, neuf chunks, transitions recording→paused→recording. Source8,568s ; fichier décodé8,520s (-48ms). Base transcription WER/CER0% : aucune perte lexicale observée. Ce test ne couvre ni microphone physique ni Safari/mobile.

Première tentative du harness avait une erreur d'export base64 (spread dépassant pile JS) après l'enregistrement ; corrigée via FileReader. L'ancien processus de test a été arrêté, le second navigateur fermé. Aucun téléchargement navigateur supplémentaire.

## Inspection structurelle et recommandations

- `frontend/src/features/memora/app.tsx` capture actuelle inspectée : `audio:true`, préférence Opus WebM puis MP4, bitrate non fixé, `media.start(10000)`, pause/reprise sur la même instance. Le protocole serveur conserve les octets de chunks dans l'ordre (idempotence/digest testés dans recette API antérieure). Pas de reconstruction de plusieurs fichiers WebM indépendants dans ce parcours.
- `validate_audio` décode les frames avec leurs taux réels ; `decode_audio` Faster Whisper utilise PyAV, downmix mono et rééchantillonnage16k. Pas d'hypothèse erronée « flux48k déjà16k » observée. Full-file final évite les anciennes coupes extérieures30s. Le direct est un aperçu sur queue120s et peut différer du final ; ne pas les présenter comme transcription définitive identique.
- Fixer explicitement `audioBitsPerSecond:128000` préserve une qualité mesurée meilleure que32/64 sur ce corpus. La valeur demandée peut différer de la valeur effective : relever `recorder.audioBitsPerSecond` et `track.getSettings()` pour diagnostic non sensible (sampleRate/channelCount/traitements), sans log audio, deviceId ni labels de périphériques. [MDN audioBitsPerSecond](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/audioBitsPerSecond).
- Préférer contraintes souples `channelCount:{ideal:1}`, `sampleRate:{ideal:48000}` puis contrôler paramètres effectifs. Ne pas imposer `exact` qui ferait échouer certains appareils. Le rééchantillonnage16k reste la responsabilité du moteur, pas du navigateur.
- Pour fidélité voix propre/casque : proposer echoCancellation:false, noiseSuppression:false, autoGainControl:false. Pour pièce bruitée/retour haut-parleur, ces traitements peuvent aider ou retirer des voix utiles ; garder un profil configurable et comparer avec l'audio source. Aucune prétention à un réglage universel optimal sans mesure acoustique. Echo cancellation peut retirer audio système/participants distants selon navigateur : [MDN echoCancellation](https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/echoCancellation). AGC n'est pas universellement supporté et les contraintes simples sont tentatives : [MDN autoGainControl](https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/autoGainControl).
- `pause()` conserve le Blob courant pour reprise, comportement compatible avec la même instance observée : [MDN pause](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/pause).

## Reproduction et preuves locales

`backend/.venv/bin/python scripts/memora-qa-capture.py` (24 essais codec/VAD, modèle base local uniquement).

`backend/.venv/bin/python scripts/memora-qa-python-sentence.py` (auto/fr et transcription capture navigateur synthétique, un seul modèle chargé).

`MEMORA_QA_BROWSER="<chemin Chromium déjà installé>" node scripts/memora-qa-capture-browser.cjs` (pas de micro).

Résultats : `agents/logs/capture-qa.json`, `capture-browser.json`, `python-sentence-qa.json`. Logs/fichiers de codec `.memora/capture-qa` restent locaux et exclus Git. Fixtures et scripts sont pérennes. Les modèles plus précis MLX sont gérés par intégrateur, pas évalués dans cette tâche.
