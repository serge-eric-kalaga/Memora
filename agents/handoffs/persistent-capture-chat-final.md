# Capture persistante et conversation — recette finale

25 octobre 2026. Sources produit intégrées et corrigées par ROOT/qa_local ; cet agent a modifié uniquement les tests et créé MeetingChat pendant son périmètre précédent. Aucun service principal, compte personnel ou audio privé utilisé.

## Résultat final

`PLAYWRIGHT_CHROMIUM_EXECUTABLE=<Chromium1248 headless-shell existant> backend/.venv/bin/python scripts/memora-verify-isolated.py --browser-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout 2400` : **22 jalons navigateur +13 contrôles UI PASS, 5 stages, 120.0s nettoyage compris, exit0**. Zéro exception JavaScript, y compris zéro React418. Summary passed, demo_data_touched:false ; Ollama partagé localement, autres services/DB/stockage/SMTP et données synthétiques isolés. Ports18080/13000/11025/18025 fermés après nettoyage.

Preuves : agents/logs/persistent-chat-isolated-browser.log ; isolated-browser.log ; isolated-ui-audit.log ; isolated-summary.json ; persistent-chat-test-lint.log (lint des trois scripts PASS).

## Contrôles ajoutés

- Chat principal avant audio dans l’ordre DOM, avant audio verticalement sur mobile, aucun rapport concurrent, aucun débordement. Question et vraie réponse locale restaurées après rechargement. Suggestions/composer/sources/version déjà couverts par harness React distinct (7 contrôles).
- Capture avec vrai MediaRecorder Chromium alimenté par WAV synthétique : après test microphone, instrumentation du vrai getUserMedia et des tracks.stop. Navigation Next réelle réunion→dashboard→menu profil→dashboard→autre réunion ; barre pause/reprise et retour à la réunion. Exactement un getUserMedia et zéro stop avant finalisation. Les fragments ET octets serveur augmentent réellement pendant ce parcours.
- Réseau coupé/rétabli et reprise de sauvegarde conservés. Finalisation depuis la barre sur le dashboard, arrêt des pistes observé, retour réunion et vrai rapport ASR/Ollama prêt. Français, séparation locale, corrections/historique et partage/révocation restent validés.
- UI audit : composer du chat et absence de rapport concurrent sur desktop/mobile, clair/sombre.

## Captures exactes

Sous agents/logs (locales, horsGit) :

- isolated-persistent-capture-desktop-light.png
- isolated-persistent-capture-desktop-dark.png
- isolated-persistent-capture-mobile-light.png
- isolated-persistent-capture-mobile-dark.png
- isolated-chat-primary-desktop-light.png
- isolated-chat-primary-desktop-dark.png
- isolated-chat-primary-mobile-light.png
- isolated-chat-primary-mobile-dark.png
- isolated-browser-chat-mobile.png (conversation avec source courante avant corrections)
- persistent-chat-history-restored-desktop.png (première tentative : vraie conversation après reload ; sélecteur corrigé ensuite)

Desktop chat clair et barre mobile sombre inspectés visuellement par cet agent ; ROOT a aussi inspecté chat mobile et les quatre barres. Disposition lisible sans débordement ; les anciennes citations sont explicitement désactivées dans les captures d’audit après corrections.

## Défauts trouvés et preuves A/B

1. Produit : modal Nouvelle réunion conservée par le cache de navigation du dashboard, masquant le menu du compte après retour pendant capture. ROOT ferme create/busy avant router.push. Test garde l’assertion absence de modal. Première preuve : persistent-capture-dashboard-modal-failure.log/.png.
2. Produit : deux React418 en fin recette. Reproduction courte sans audio/IA : hardloads dashboard/profil/paramètres OK ; création brouillon puis reload /reunions/id déclenche418. Développement webpack sur copie temporaire : zéro erreur. A/B production exact : wrapperdiv original→1 erreur au draftreload ; variante temporaire children directs/fragment +spacer conditionnel→0. ROOT applique cette correction ; recette finale complète→0, sans filtrage d’erreurs. Logs hydration-original-confirm-diagnostic.log, hydration-original-confirm-runner.log, hydration-fragment-diagnostic.log, hydration-fragment-runner.log, hydration-fragment-build.log. Copies temporaires et wrappers supprimés après preuve.
3. Tests : getByText exact sur question échouait car bulle contient le texte SR « Vous : » ; screenshot montrait pourtant historique correct. Corrigé attente partielle portée chat plus réponse. Autre test lisait chunk_count absent du détail ; corrigé chunks.length et somme bytes conformément au contrat. Échecs préservés : persistent-chat-first-browser-failure.log et persistent-capture-counter-test-failure.log. Aucun contrôle produit affaibli.

Script de régression court pérenne : frontend/tests/memora-hydration-diagnostic.mjs, utilise URL/credentials synthétiques fournis via environnement, sans audio/modèle. Assert zéro erreur par défaut ; MEMORA_EXPECT_HYDRATION_ERRORS permet une comparaison explicite de baseline. ROOT peut l’exécuter sur une future instance isolée. Les wrappers de services temporaires du diagnostic n’ont pas été ajoutés au projet.

## Limites et continuité

Pas de microphone physique, veille matérielle, capot fermé, Safari/iOS ni longue réunion naturelle. La preuve navigateur concerne la navigation dans le même onglet sur machine éveillée. Les mesures ne prouvent ni qualité universelle ASR/IA ni délivrabilité email production. Aucun envoi réel ou déploiement. Tests/handoff pérennes ; logs/captures locaux exclus Git. Sources tests gelées après livraison ; ROOT gère activation et commit.
