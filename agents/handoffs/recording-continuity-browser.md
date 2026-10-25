# Continuité de capture — recette du 25 octobre 2026

## Preuves ciblées

`node frontend/tests/memora-recording-continuity-browser.mjs` : **7 contrôles PASS**, exit0. React et hook réels montés depuis un snapshot dont SHA256 avant/après est identique (`2738799e5b546c01c63fb486cc31426bef40e160bb28d671e050fed46a52bdf9`). Audio synthétique WebAudio vers vrai MediaRecorder : 41 196 octets, deux requestData flush, aucun pause/stop à cause de la visibilité. Vrais changements d’onglet hidden/visible à deux reprises ; pause explicite conservée. Wake Lock et heartbeat HTTP simulés : acquisition/libération/réacquisition, refus/absence, et acquisitions tardives après arrêt nettoyées. Zéro exception navigateur.

Le harness lance son propre Chrome avec profil vide jetable, puis connectOverCDP({noDefaults:true}), option publique Playwright qui évite son focus forcé. Il ne se connecte jamais au navigateur personnel. Tous les waits de visibilité utilisent polling100. Chrome, serveur et profil temporaire sont nettoyés. Logs : `agents/logs/recording-continuity-browser.log` et `.json`.

## Recette intégrée réelle

`PLAYWRIGHT_CHROMIUM_EXECUTABLE=<Chromium1248 headless-shell local> backend/.venv/bin/python scripts/memora-verify-isolated.py --browser-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout 2400` : **5 stages PASS, 19 jalons navigateur +11 contrôles UI, 108.28s nettoyage compris**. DB/comptes/stockage/SMTP synthétiques isolés ; Ollama local partagé. Import→ASR→rapport réel, chat/citations, historique/corrections/review, partage/révocation, microphone factice, capture/live/pause/réseau/reprise/finalisation, français, séparation locale et UI desktop/mobile/thèmes validés. L’indicateur en cours et le niveau positif réel, puis pause et niveau nul, sont vérifiés.

Logs : `agents/logs/continuity-isolated-browser.log`, `isolated-browser.log`, `isolated-ui-audit.log`, `isolated-summary.json` (passed ; demo_data_touched:false). Ports18080/13000/11025/18025 fermés après nettoyage. Lint des deux scripts ciblés PASS (`recording-continuity-test-lint.log`). Seuls les tests ont été modifiés par cet agent ; aucune source produit, donnée personnelle, configuration ou service principal modifié.

## Limites

Le test du hook simule Wake Lock et endpoint heartbeat ; la validation native du helper relève de ROOT. Aucun microphone physique, mise en veille physique, fermeture de machine, Safari/iOS ni garantie de capture illimitée en arrière-plan. Les changements réels d’onglet et progression des octets ont été observés sur Chrome, machine éveillée. Le corpus court synthétique ne qualifie pas la précision générale de l’IA. Logs/captures restent locaux exclus de Git ; ce handoff et les scripts de test sont pérennes. ROOT gère activation et commit.
