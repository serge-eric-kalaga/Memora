# Capture persistante pendant navigation interne

Extraction du Recorder existant dans CaptureRuntime (MediaRecorder/IndexedDB/import inchangés), monté sous CaptureProvider dans le layout racine. Le formulaire complet est un portail vers CaptureSlot sur la réunion ; quitter la page enlève le formulaire mais conserve le runtime. Barre compacte ailleurs, padding mobile pour ne pas recouvrir le contenu. Une seule session par onglet ; autre réunion bloquée tant que session en cours/interrompue. Aucune acquisition automatique du micro.

Callbacks provider stables pour ne pas déclencher cleanup timer ; retour réunion rebranche le portail. Acquisition getUserMedia concurrente verrouillée, résolution après démontage ferme les pistes. Prétest micro démonté à la navigation et indicateur réinitialisé. Déconnexion/changement utilisateur cache immédiatement l’ancienne session et démonte le runtime ; fermeture appelle stop/requestData et libère les pistes/lease. Les imports et transferts progressifs restent montés pendant navigation.

Vérifications obtenues : `cd frontend && ./node_modules/.bin/eslint src/features/memora/{app,capture-runtime,capture-session,audio-language}.tsx src/app/layout.tsx && ./node_modules/.bin/tsc --noEmit` PASS. Lecture du contrat Next layout persistant depuis docs installées et revue React hooks/accessibilité. Aucune validation navigateur revendiquée dans ce handoff : confiée à api_tests/ROOT pour recette isolée intégrée.

À vérifier navigateur : capture→dashboard/profil/autre réunion→pause/reprise barre→retour sans seconde acquisition ; finalisation hors page ; logout/expiration/changecompte ferme pistes ; prétest→navigation→retour ne bloque pas ; upload reste vivant ; mobile barre/composer non superposés.

Limites : navigation Next interne conservée, pas de continuité promise après hardreload/fermeture/veille manuelle ; fragments confirmés conservés dans IndexedDB. Un onglet distinct dispose de sa propre session, aucune exclusivité inter-onglets introduite. Aucun service principal démarré/modifié, aucune donnée personnelle traitée.

Empreintes des nouveaux modules à libération (app/layout intégrés ensuite par ROOT) :

```json
{
  "frontend/src/features/memora/capture-session.tsx": "4e1477b05f457ec502cf97e25ce9b90c0a79e5e59ef7944c40bd6c95b21db5bf",
  "frontend/src/features/memora/capture-runtime.tsx": "e31e0925c206e4ffb540cb2c23994a761f85ccaf305c9676df9571c991aac0cb",
  "frontend/src/features/memora/audio-language.tsx": "74d1544b9bbe3765a28bb874835020bd33a8ea72f3caee121141f0da789fcbcd",
  "frontend/src/features/memora/capture-session.module.css": "25f61808a55851fa1196d8924400b2e0bb4e3fb75cfd0840e8816e3fe9a95b6b"
}
```
