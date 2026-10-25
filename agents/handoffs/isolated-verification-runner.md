# Recette sur services entièrement jetables

Runner : `scripts/memora-verify-isolated.py`. Trois scripts paramétrés : runner, `memora-e2e-api.py`, `memora-mail-capture.py`. Les scripts navigateur acceptent désormais credentials/base/préfixe grâce à l'agent frontend.

Commande complète depuis racine :

```sh
backend/.venv/bin/python scripts/memora-verify-isolated.py --timeout 2400
```

Après un build standalone complet, le runner prépare migrations auth réelles et stockage domaine séparés dans TemporaryDirectory (hors dépôt), compte aléatoire synthétique et credentials0600, privilège admin limité à cette nouvelle base, capture SMTP séparée et copie temporaire du serveur standalone/statics/public. Seul node_modules est lié vers les dépendances existantes ; les caches runtime existants ne sont pas copiés. Le backend travaille dans ce répertoire temporaire pour isoler également logs/static/photos. Les clés d'auth sont nouvelles ; configuration de modèle seule lue depuis l'allowlist de backend.env/environnement. HF offline interdit le téléchargement automatique.

Ports par défaut : API18080, frontend13000, SMTP11025, inbox18025 sur127.0.0.1. Paramètres `--api-port`, `--ui-port`, `--smtp-port`, `--inbox-port`. Refuse les ports principaux3000/8080/1025/8025/11434, les doublons et les ports occupés. Ne tue jamais un service existant. Une restriction de binding du sandbox produit une erreur de permission explicite. Aucun contournement réseau : exécution via autorisation locale si l'environnement l'exige.

Le serveur frontend utilise BACKEND_URL vers la nouvelle API ; le smoke vérifie réellement login+session via le proxy et le compte jetable, au-delà d'une simple page HTML. SESSION_COOKIE_SECURE=false uniquement pour ce HTTP loopback isolé. Puis recette API, navigateur synthétique (fake microphone), audit UI en séquence. Chaque enfant a son groupe PID propre, une borne globale de travail et est arrêté dans finally avant suppression des bases, mails, credentials et copie frontend temporaires. Aucun arrêt Ollama ou service principal.

Variables de recettes : MEMORA_TEST_API_URL, MEMORA_UI_URL, MEMORA_TEST_CREDENTIALS, MEMORA_TEST_MAIL_DIR, MEMORA_TEST_ARTIFACT_PREFIX=isolated-. SMTP : MEMORA_MAIL_DIR/MEMORA_SMTP_PORT/MEMORA_INBOX_PORT. Les logs et captures ne concernent que des données synthétiques : `agents/logs/isolated-*`, handoffs `agents/handoffs/isolated-*`. Ils ne remplacent pas les anciennes preuves principales. Le résumé `isolated-summary.json` indique passed/failed, étapes réussies et smoke_only. Les bases et credentials ne sont jamais conservés dans ces logs.

## Preuves réellement obtenues

Smoke réel sur API19081/frontend14001/SMTP12026/inbox19026 : **migrations, synthetic-admin, isolated-authenticated-proxy réussis**,2,64s (2,89s avec nettoyage). Commande :

```sh
backend/.venv/bin/python scripts/memora-verify-isolated.py --smoke-only --timeout 120 --api-port 19081 --ui-port 14001 --smtp-port 12026 --inbox-port 19026
```

`isolated-summary.json` confirme passed et smoke_only=true. API démarrée puis arrêtée proprement dans isolated-backend.log. Ruff et py_compile réussis pour les trois scripts. Refus des ports principaux et timeout invalide contrôlés sans lancement de services. Première tentative avait cookie Secure sur HTTP : corrigé par option locale du runner et smoke entièrement repassé.

**La recette complète API24/navigateur12/audit7 n'a pas été exécutée dans cette étape.** L'intégrateur doit la lancer après validation du moteur MLX et dernier build. `--asr-engine faster-whisper|mlx-whisper` permet de choisir le moteur final ; les choix live/modèle restent issus de l'allowlist. Option PLAYWRIGHT_CHROMIUM_EXECUTABLE conservée pour Chromium existant.

## Limites d'isolation

Ollama11434 et fichiers des modèles existants sont partagés en lecture/inférence. Les requêtes n'emportent aucun historique de conversation ni donnée utilisateur mais consomment CPU/GPU/RAM et peuvent modifier le cache de modèle/latence du service commun. Aucun isolement matériel ou garantie de latence pendant l'utilisation simultanée de l'application principale. Pas de téléchargement modèle, nouvelle dépendance ou changement du modèle installé. Une réussite smoke ne prouve ni qualité ASR, ni analyse IA, ni parcours navigateur complet.

## Recette complète baseline exécutée

Après le smoke, exécution complète `--asr-engine faster-whisper --timeout 2400` avec Chromium1248 existant et les ports19081/14001/12026/19026 : **6étapes réussies en151,71s** (151,88s avec nettoyage), dont API **24/24 en51,58s**, navigateur **12/12** et audit UI **7/7**. Les constats « non exécuté » de la section smoke sont donc historiques, remplacés pour cette baseline par cette exécution complète ; le moteur MLX n'a pas été exécuté.

Preuves : `agents/logs/isolated-full-run.log`, `isolated-api.log`, `isolated-browser.log`, `isolated-ui-audit.log`, `isolated-summary.json` (status=passed,smoke_only=false), handoffs `isolated-e2e-api.md`, `isolated-browser.md`, `isolated-ui-audit.md`. Ces rapports ne contiennent que des données synthétiques. Bases, emails et credentials temporaires supprimés après arrêt des processus créés.

Sondes après exécution : les trois PID principaux backend/frontend/mail sont vivants ; health API8080, page connexion3000 et inbox8025 répondent200 ; les quatre ports de test sont fermés. Preuves comparables avant/après : `isolated-main-before.json` et `isolated-main-after.json`. Aucun service principal ni base utilisateur modifié par le runner ; la consommation de ressources du service Ollama partagé demeure la limite explicitée ci-dessus.

## Complément API réellement exécuté : administration, invités, retranscription

Extension du script API activée **seulement** si MEMORA_TEST_ISOLATED=1 et marqueur privé généré par le runner concordant avec API loopback hors ports principaux et credentials dans le répertoire temporaire. Un essai négatif a confirmé refus avant lecture de credentials/HTTP quand cible8080 et marqueur absent. Le mode normal de l'ancien script ne modifie pas les paramètres administratifs et n'exécute pas ce complément.

Runner `--api-only` permet de garder migrations, SMTP, API, compte et proxy standalone isolés puis exécuter uniquement les contrôles API. `--smoke-only` et `--api-only` sont exclusifs. La recette complète par défaut garde navigateur et audit UI après l'API.

Exécution réelle baseline faster-whisper :

```sh
backend/.venv/bin/python scripts/memora-verify-isolated.py --api-only --asr-engine faster-whisper --timeout 600 --api-port 19081 --ui-port 14001 --smtp-port 12026 --inbox-port 19026
```

**33/33 contrôles API réussis en66,63s**,4étapes runner réussies en69,05s (69,28s avec nettoyage). Les9 nouveaux contrôles couvrent rôle administrateur jetable, PUT valide des paramètres, snapshot d'une nouvelle réunion et absence de rétroactivité, correction invitée explicitement autorisée, désactivation admin retirant l'édition d'un ancien lien, requête de retranscription dédupliquée, ASR réelle + nouveau rapport avec historique conservé (transcriptionsv1/v2/v3/v4 et anciens rapports), rejeu terminé sans version supplémentaire, restauration exacte des paramètres initiaux dans finally.

Preuves actuelles : `agents/logs/isolated-extended-run.log`, `isolated-api.log`, `isolated-summary.json` (passed,api_only=true), `agents/handoffs/isolated-e2e-api.md`. Ruff et py_compile des deux scripts réussis. Aucun backend/IA/frontend modifié pour ce complément ; uniquement script API, runner et ce handoff.

Après nettoyage :3PID principaux vivants, API8080/UI3000/inbox8025 répondent200,4ports jetables fermés (`isolated-extended-main-after.json`). Les bases/mails/credentials sont supprimés. Ces33 contrôles n'utilisent pas MLX et ne remplacent pas la future recette finale après build/moteur retenu ; les12 contrôles navigateur et7 audit précédents restent les preuves de leur exécution antérieure complète.

## Validation finale MLX et dernière interface

Commande complète exécutée après le dernier build frontend et validation des poids MLX par l'intégrateur :

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Users/kalagasergeeric/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing' backend/.venv/bin/python scripts/memora-verify-isolated.py --asr-engine mlx-whisper --timeout 2400 --api-port 19081 --ui-port 14001 --smtp-port 12026 --inbox-port 19026
```

**SUCCÈS :33API +12navigateur +7auditUI =52contrôles PASS réellement comptés**,6étapes runner réussies en173,44s (durée incluant nettoyage dans isolated-final-summary.json), API72,9s. Mode complet, smoke_only=false,api_only=false. Capture exclusivement synthétique, transcription live, pause/réseau offline/reprise, finalisation et rapport réel validés. Édition invitée avec retrait de droit, paramètres/snapshots/restauration et retranscription idempotente avec historique sont inclus dans les33 API.

Preuves figées pour éviter confusion avec baseline : `agents/logs/isolated-final-run.log`, `isolated-final-api.log`, `isolated-final-browser.log`, `isolated-final-ui-audit.log`, `isolated-final-summary.json` ; diagnostics `isolated-final-backend.log`, `isolated-final-frontend.log`, `isolated-final-mail.log`. Handoffs : `isolated-final-e2e-api.md`, `isolated-final-browser.md`, `isolated-final-ui-audit.md`. Les preuves baseline préexistantes ont été copiées sous `baseline-isolated-*` avant lancement.

Après exécution : les3PID des services principaux sont toujours vivants ; seules les réponses HTTP (en-têtes) ont été contrôlées, health API8080/UI connexion3000/inbox8025 répondent200. Les4ports de recette sont fermés ; les services créés ont été arrêtés et les bases/mails/credentials temporaires nettoyés. Voir `isolated-final-main-before.json` et `isolated-final-main-after.json`. Aucun changement de code backend/frontend/harness nécessaire pendant cette validation finale ; aucune donnée utilisateur ou audio personnel utilisé.

Cette recette prouve les parcours synthétiques énumérés sur la configuration MLX et le bundle testés ; elle ne prouve pas microphone physique, Safari/iOS, charge production ou fidélité universelle. Les mesures de précision/15minutes et la vérification SHA des modèles sont des preuves distinctes maintenues par l'intégrateur.
