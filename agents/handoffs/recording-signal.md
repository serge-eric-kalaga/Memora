# Signal pendant l’enregistrement

Composant client nommé `RecordingSignal` dans `frontend/src/features/memora/recording-signal.tsx`.
Contrat : `{ stream: MediaStream | null, state: string, language: 'fr' | 'en' }` ; recevoir le flux EXISTANT du recorder, aucune acquisition microphone. States actifs `recording`/`paused`, autres inactifs.

Canvas waveform échantillons réels, dessin plafonné20Hz et publication React4Hz ; RMS/dBFS, peak, niveau relatif -60..0dBFS. Seuil silence RMS<.003 pendant4s et saturation peak>=.98 : heuristiques techniques sans garantie parole/ASR/sauvegarde. Pause/mute/ended/unsupported/suspended explicites, reprise AudioContext par bouton. Flux analysé sans connexion destination (pas de retour haut-parleur). Cleanup ferme uniquement contexte/nœuds/RAF propres, jamais tracks parent. Détection mute/ended/enabled/context par polling pendant RAF ; onglet masqué peut différer affichage jusqu’au retour.

Validation : quatre tests CPU helper `cd frontend && node --test tests/memora-recording-signal.test.mjs` PASS ; ESLint ciblé PASS ; `./node_modules/.bin/tsc --noEmit` PASS. Pas de navigateur monté, microphone physique ou capture réelle testés dans ce jalon. Root assure intégration app puis recette. Aucun app.tsx/fichier commun/service/main data modifié.

## Preuve navigateur composant monté

`frontend/tests/memora-recording-signal-browser.mjs` bundle le composant actuel avec Webpack local puis Chromium1248. Origine réservée memora.test intégralement interceptée en mémoire ; aucune API applicative ni microphone. Source réelle AudioContext Oscillator→Gain→MediaStreamDestination ; vrai MediaRecorder parent. Huit vérifications PASS : niveau>0 et canvas4588pixels, pause sans arrêter recorder, reprise, saturation gain1.2, silence4s, piste désactivée, démontage conservant tracklive/recorderrecording/contextparentrunning, puis second montage/piste explicitement terminée détectée. ZéroexceptionJS vérifiée avant second montage. Log `agents/logs/recording-signal-browser.log`. Exécution a requis permission Chromium hors sandbox ; aucune inférenceGPU. Suspended/unsupported couverts helpers uniquement, pas simulation navigateur ; pas preuve microphone matériel ni intégration app complète.
