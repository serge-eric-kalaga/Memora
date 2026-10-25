# Intégration Parakeet — proposition bornée, pas encore activée

Aucune modification de code principal, backend.env ou dépendance backend faite par cet audit. La décision dépend des benchmarks indépendants en cours. Sources locales inspectées : prototype, ai.py, routes.py Segment/Correction, worker.py, frontend app/api/language/i18n, installer/verify-isolated et inventaires des deux venv.

## 1. Dépendances et runtime

Lab validé par résolution/pipcheck (pas encore preuve inférence) : mlx-audio0.6.1/MIT, MLX/Metal0.32.4, PyAV16.1.0, NumPy2.5.4, SciPy1.18.1, Hub2.3.0, Tokenizers0.23.3. Ces sept derniers sont déjà aux mêmes versions dans backend. Nouveaux principaux : Transformers5.20.2/Apache2, miniaudio1.71, sounddevice0.5.6, sentencepiece0.2.2, zstandard0.25.0. Aucun Torch supplémentaire requis (backend dispose déjà Torch2.14.1 pour son VAD) ; aucun NeMo/CUDA.

Si benchmark concluant : backend/pyproject.toml dépendance exacte `mlx-audio[stt]==0.6.1` avec même marker DarwinARM64 que mlx-whisper, puis uv lock/sync frozen et diff revue. Variante extra optionnel `parakeet` évite d'alourdir tous les Mac mais exige que installer/runner sélectionnent explicitement l'extra ; garder une seule stratégie documentée. Ne jamais exécuter pip -U dans backend. Vérifier résolution/support LinuxDocker : markerDarwin ne doit pas installer MLX sousLinux ; moteur sélectionné incompatible doit rendre erreur explicite, sans fallback simulée.

## 2. Adaptateur et factory

Porter prototype vers backend/api/memora/asr_parakeet.py après validation : chargement paresseux/chemin local uniquement, mêmes verify SHA poids+assets qu'offline, PyAV16kmono, chunk30s/overlap2s, horodatagesnatifs+tailoffset, rejet tempsnonfinis/start>=duration/end<=start ; libération modèle/cachefinally. Factory backend/api/memora/ai.py:transcribe ajoute moteur `parakeet-mlx` sous **même verrou _lock** partagéASR/LLM. Pasdeprocess/servicepermanent additionnel.

Moteur ne force pas languefr/en dans l'implémentation inspectée. Ne pas étiqueter une langue choisie comme langue détectée. Langue sortie unknown/null, confidenceNone. Passageincertain doit distinguer absence de score fournisseur d'une suspicion d'erreur mesurée ; règle conservatrice explicite tantque pascalibration. Aucunmodèle métier/rapport ne doit déduire langue/speaker/confidence imaginée.

## 3. Configuration/installation

Nouvelle clé proposée `MEMORA_PARAKEET_MODEL_PATH` absolue vers modèle distinct. Env d'exemple/doc configurable, choix défautinchangé jusqu'à décision. Factory respecte MEMORA_ASR_ENGINE vs MEMORA_LIVE_ASR_ENGINE ; commencer finalseul si live nonmesuré, garderTurbo live si benchmarks lejustifient. Installer scripts/memora-install.sh caseparakeet-mlx appelle scripts/memora-download-parakeet.py --target; harmoniser résolutionenv/paths et guardscollisions avant écriture. scripts/memora-env.py ne doit jamais remplacer cléexistante ni activer nouvelleconfiguration silencieusement.

Pinner dépôt/révision/poids+assets, attribuer NVIDIA etMLXCommunity CC-BY4, préserverREADME/manifeste/ATTRIBUTION. Downloaderdéjàprêt, check-onlyoffline3GBHash devient coûteux parchaqueappel : envisagercachevérificationstat/fingerprint avec contrôleinitialcomplet et invalidationmodif, sans déclarerhashconstammentrecalculés’ilne l’estpas. Benchmarkconsidèrececoût ; nepasmasquer.

## 4. Écart UI/API concret avant intégration

frontend/src/features/memora/app.tsx:1192 masque badge si `seg.language` null, donc aucune fausse anglaise. Mais frontend/api.ts Segment.language?:string ne décrit pas null. **backend/api/memora/routes.py:581 Segment.language:str** refuse null ; UI correctionPUT renvoie segmentsbruts (app.tsx:1159). Une sourceParakeetnull serait consultable mais correction422.

Choix simple : normaliser adaptateurproduction vers language:"unknown" ; frontend language.ts traduit badge "Langue non déterminée"/"Language not determined" avec aide "Le moteur ne fournit pas de détection de langue". Ne pas montrer littéralanglaisunknown à interfaceFR. Autrechoix cohérent : schema/API nullable+typeTSnullable et indicationglobale ; couvrir correctionroundtrip. Ne pas appliquer unilatéralement nullable backend sans tests.

Uncertaintrue partout affiche "Passage incertain" sur chaquephrase (app.tsx1193). C'est avertissementconservateur mais neprouvepascesphrasesfausses. Si absenceconfiance seulement, préférer aideglobale "Fiabilité non chiffrée" et nepas prétendre une détectiond'incertitudefine. L'existant avertissementASRglobal reste utile. Correction schema actuelexclut language_scope/confidence, donc prévoir conservationmétadonnéesdétectioninchangées si l'UIlesutilise aprèscorrection.

Capture/createparamlangue restefr/en/auto : siParakeetignoreforçage, une aidecapacitédoit le dire pource moteur ; garderconventionAPI sans faussepromesse. Paramètremodèle centralisébackend, pasSDKtechnique dansUX.

## 5. Validation avant activation

- TestsadaptateurCPU/mocks : offline/noautodownload, mauvaiseprovenance/assetcorrompu, decodeWAV/WebMOpus.bin/importautresformatsautorisés, timestampclamp/offset/tail, chunkmergepasdedoublons, langunknown/corrections, lock/libérationexception. Déjà29préparationPASS, paspreuveIA.
- Bench réel sous créneauGPUROOT, corpusindépendantFR/EN/mixte/silence/bruit/voixaccents/longsourcefinale, nativecitations/audio cohérentes, mémoire/latence parcas. Pasdereformulationhumainecomme vérité motàmot. Ne pas faire passerbenchmarksourcewords pourtest2h.
- scripts/memora-verify-isolated.py : ajouter choixCLIparakeet-mlx, MODEL_KEYS clépath, éventuellement liveengineCLI, subprocessbackendvenvavecdepsrésolues ; DB/SMTP/storage/comptesjetables et portsnonmain. Aucunenvsecretcopié. TestsAPIcorriger/langunknown/report/chat/retention/audio/injection, navigateurenregistrementWebM+finalimport+versions/partages ; zérocompteuser.
- Build/types/lint/testsbackend/SDKconsistants aprèschoixschema. Activationconfiguration séparéeaprèspreuves, annoncerredémarrageMaincourt0jobsactifs, nepasretranscrire automatiquement réunionspersonnelles, conserverversions existantes.

## Risques précis

Gainqualité nonétabli pourParakeetavantbench ; auto25langues negarantitpascode-switching ; nompropresponctuation/chunkmerge ; pasdiarisation ; tempsnatifsalignementmodèleàcontrôler, pasvéritéhumaine ; languehardcodéeenstreamingnepasexposer ; RAMpartagée16GB/picactivation ; dépendancesTransformersnouvelleprofondeur ; effetquotidiendesupdates évitéparpin/lock ; loaderHubautodownload évitéparcheminPathvérifié+offline ; licenceattributionàconserver ; DockerLinuxnonMLX ; correctionnullactuelle422 ; confianceabsenten'estpasuneerreurdétectée.
