# Séparation locale des voix — module et preuves livrés

Périmètre de ce sous-agent : nouveau `backend/api/memora/diarization.py`, tests dédiés, scripts/fixtures et dépendances réservées. Aucun changement ai.py/worker/routes/store/frontend, aucune donnée privée, aucun microphone ni inférence GPU. Les résultats ci-dessous sont de vraies inférences CPU sur pistes TTS synthétiques connues.

## Choix documenté

[Pyannote community-1 officiel](https://huggingface.co/pyannote/speaker-diarization-community-1) fournit diarisation et tours exclusifs ; licenceCC-BY4.0, accès exige acceptation des conditions et tokenHuggingFace. Aucun accès gated contourné ni consentement accepté à la place de l'utilisateur. Pas de servicepyannote distant/payant utilisé.

Alternative choisie : [Resemblyzer officiel](https://github.com/resemble-ai/Resemblyzer), encodeur vocal neuronal256dimensions, [Apache-2.0](https://github.com/resemble-ai/Resemblyzer/blob/master/LICENSE). Le [packagePyPI0.1.4](https://pypi.org/project/Resemblyzer/0.1.4/) contient le modèle. L'auteur précise une meilleure prise en charge de l'anglais ; résultats français synthétiques mesurés ici sans prétendre équivalence sur voix réelles. Ce n'est pas une alternance heuristique : embeddings appris, distancescosinus et clusteringagglomératif réel, puis réattribution des fenêtres aux centroïdes.

Poids :17,090,379octets, SHA256 **39373b86598fa3da9fcddee6142382efe09777e8d37dc9c0561f41f0070f134e**. Provenancepackage officiel verrouillé. Préparation copie le modèle déjà installé vers `.memora/models/resemblyzer-0.1.4`, vérifie SHAépinglé, crée manifest ; aucun téléchargement pendant préparation/inférence. Réexécution valide ne réécrit rien.

## Dépendances et préparation

- Resemblyzer0.1.4 et setuptools>=80.9,<81 conditionnés Darwinarm64, comme torch déjà présent. Lock horsCUDA ; autresOS non validés, disponibilitéfalse si moteur absent.
- **Seul existant changé** : setuptools84.2.1→80.10.2. Motif vérifié : webrtcvad2.0.10 importepkg_resources, absent ensetuptools84 ; sanscompat importéchoue. Avertissement de dépréciation connu, pas erreur. Nouveaux librosa/scikit-learn/soundfile/etc verrouillés, pas upgrade torch/scipy/ASR.
- Installationuv validée, compilationwebrtcvad réussie. Lockfinal168packages, aucune dépendanceCUDA téléchargée surMac. Inspection initiale11GiBdisquelibre et76%RAMlibre ; aucun poids>1Go.

Commandes depuis racine :

```sh
backend/.venv/bin/python scripts/memora-prepare-diarization.py
backend/.venv/bin/python scripts/memora-prepare-diarization.py --check-only
```

Variable opérateur : `MEMORA_DIARIZATION_MODEL_DIR`, défaut `.memora/models/resemblyzer-0.1.4`. `availability()` et `available()` ne chargent aucun modèle et n'accèdent pas au réseau. Contrôle intégrité complet avant chaque vrai traitement. Les poids/manifests/audios générés restent `.memora/` horsGit ; corpusdephrases, scripts, tests et cehandoff pérennes.

## Contrat pour intégration ROOT

```python
result = diarization.diarize(audio_path, segments, num_speakers=None, max_speakers=8)
# result: {segments, turns, metadata}
```

Chaque segment retourné est une copie conservant exactement id/start/end/text (et champsASR existants), avec `speaker` (« Intervenant1 »), `speaker_id` (« SPEAKER_00 »), `speaker_confidence=None`, `speaker_uncertain`, `speaker_candidates` (fractions temporelles, pas probabilités), `speaker_provenance` (engine/version/modelSHA). Aucun nom, genre ou identité n'est déduit. Labels stables par ordre de première occurrence dans CE fichier, pas identifiants personnels interréunions.

Un segmentASR contenant deux groupes vocaux reste « Intervenant non identifié », même majorité90/10. Pas de découpage inventé du texte ni d'attribution majoritaire présentée sûre. Couverture insuffisante/tourincertain →abstention. `uncertain`ASR n'est pas écrasé ; incertitudevoix séparée.

metadata : moteur resemblyzer-silero-ahc-v1, CPU, comptegroupes, poidsSHA, fenêtre1,6s/hop0,4s, warnings, overlap_supportedFalse, confidence_calibratedFalse. Voix proches/bruit/portionscourtes peuvent fusionner/fragmenter. Séparation de paroles simultanées NON prise en charge ; aucune confiance% calibrée.

VADSilero existant, timestamps originaux préservés (aucune compression des silences). Clusteringcosinus seuil0,30 sélectionné sur cas de mise au point ;600ancres max pour borner la partie quadratique, puis attribution de toutes fenêtres. Deuxheures maximum technique,32groupes plafondparamètre ; aucune validationperformance2h ni garantie sur voixrares non représentées parmi ancres. Verrou local ; **worker doit prendre le verrou lourd commun ai._lock** pour sérialiser avecASR/LLM sur16Go (ROOTinformé).

## Preuves réelles et métriques

Fixtureinitiale v1 INVALIDE : say sandbox avait produit AIFFvide malgréretour0. Découverte parinspectionwaveform ; résultatsv1 ne prouvent aucune qualité. Le générateur refuse désormais TTSvide/silencieuse ; générationmacOS autorisée horssandbox, uniquementfichierssynthétiques/pas micro. Preuves invalides conservées explicitement.

DER : grille20ms, permutation optimale des labels, aucun collar et overlap inclus. Référenceactivité issue pistesTTS isolées connues, RMS>-45dBFS, **pas référence annotée humaine ni VADmodèle**. Donc métrique reproductible spécifique, pas DERbenchmarkacadémique comparable sans réserve. DER non défini quand référence sans parole ; vérification0faussevoix séparée.

Final `agents/logs/diarization-benchmark-final.json/log` :

| Cas | Duréeaudio | Groupesattendus/prédits | DER | Affectationssegment |
|---|---:|---:|---:|---:|
|2voixFR, retoursnonalternés|32,6s|2/2|2,17%|6/6|
|gain+bruitglobal20dB|32,6s|2/2|11,80%|5/6+1abstention|
|FR/EN|28,9s|2/2|3,80%|5/5|
|2voix avec1,4soverlap|20,8s|2/2|6,10%|2/4+2abstentions|
|3voix|33,4s|3/3|3,72%|6/6|
|silence et bruitfaible seuls|4s chacun|0/0|non défini|aucune voix|

Premier appel1,467s puis0,329–0,503s pour casparlés ; CPUOMP/MKL2threads dans benchmark. Pas garantie latence encharge/2h. Sansoverlapclean,0confusionvocale surgrille ; bruit0,32s confusion, overlap0,02s etmissinévitable de voix simultanée. La baissegain rend la voix faible plus difficile que le SNRglobal affiché.

Réserve figée AVANT inférence : `backend/test/fixtures/memora/diarization-reserve-v1.json`, voix Daniel/Karen/Eddy inédites et nouvellesphrases, résultats `diarization-reserve-v1.json/log`. Aucun retuning après :

-2voixretours :2groupes,DER7,57% ;gain/bruit :2groupes,12,37% ;3voix :3groupes,8,10%. **18/18segments synthétiques correctement appariés**,0confusion vocale ; erreursDER principalement faussesalarmesVAD selon référenceénergie.
-bruitblancfortRMS0,03 seul :0voix.
-coût1,589spremier puis0,580/0,605/0,036sCPU.

`diarization-spanning-real.json` : alignementcontre vrais tours neuronaux2voix, segmentunique couvrant2voix →abstention, identifiant/texte/times inchangés. Pas nouvelle inférence ni mock sur ces tours.

## Reproduction et tests

```sh
# Génération TTS synthétique, jamaismicro ; surmacOS accessiblehorssandboxsi nécessaire
backend/.venv/bin/python scripts/memora-benchmark-diarization.py --prepare-only
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 backend/.venv/bin/python scripts/memora-benchmark-diarization.py --run --output agents/logs/diarization-new.json
backend/.venv/bin/python scripts/memora-prepare-diarization-reserve.py
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 backend/.venv/bin/python scripts/memora-benchmark-diarization.py --run --references .memora/qa/diarization-reserve/references.json --output agents/logs/diarization-new-reserve.json
python3 scripts/memora-test.py test/test_memora_diarization.py -q
```

Testsdédiés **10PASS0,27s**, Ruff5fichiers conformes : intégritépoids, indisponibilité sûre, stabilitétimeline/silences, vrais algorithmesclustering vecteurs nonalternés, comptageexplicite, abstention50/50et90/10, copiesimmuables, silence sanschargementmodèle, bornes. Testsunit ne prouvent pas qualité neuronale ; preuves réelles séparées ci-dessus.

## Limites de livraison

Pas diarisationpyannote/overlap, pas reconnaissanceidentité, pas modèleentraîné ici ni garantie voixnaturelles. Retourdevoix validé surTTS, pas conversationhumaine/roomreverb2h. Auto comptage et attribution estimés, correctionmanuelle toujours nécessaire. ROOT/APIagent intègrent jobvolontaire versionné avecdroitsaudio/transcript/edit, nouvellesversions/historiques/résultatspérimés ; ces parcoursbackend/browser ne sont PAS prouvés par ce sous-agent. Aucune activationmain réalisée ici.
