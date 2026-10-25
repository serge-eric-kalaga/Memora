# Parakeet comparatif prêt — 25 octobre 2026

Aucune activation main, aucune inférence/GPU exécutée par cet agent. Décision de benchmark et créneau GPU réservés au parent.

- `.memora/models/parakeet-v3` : HF officiel mlx-community/parakeet-tdt-0.6b-v3, révision ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15, model.safetensors2508288736octets/SHA25605e01c7f396c298cf7d23f61da7b504adeab698f0aaeafd9c82d198625464592.
- 300fragments, hash poids complet validé puis seconde lecture offline `backend/.venv/bin/python scripts/memora-download-parakeet.py --check-only`. Config, README, tokenizer.model, tokenizer.vocab, vocab.txt tous épinglés SHA256+taille dans wrapper/manifeste. Origine petits assets contrôlée contre SHA officiel LFS ou Gitblob du snapshot. Aucun Python distant téléchargé.
- Licence CC-BY-4.0 correcte, ATTRIBUTION.md NVIDIA/amont+MLX Community/conversion/liens/licence/absence modifications poids. Provenance MIT de Whisper reste inchangée ; transfert générique désormais paramètre licence/assets. README modèle conservé avec sa déclaration licence.
- `scripts/memora-download-parakeet.py` : cible séparée, --target optionnel, garde manifesteautrerepo/Turbo/poidsexistantsansmanifeste, reprise et checkoffline. Logs parakeet-download.log, parakeet-integrity-check.log.
- Runtime `.memora/asr-lab` Python3.12.14, mlx-audio0.6.1, MLX/Metal0.32.4, PyAV16.1.0 (ajout officielPyPI), Transformers5.20.2 ; requirements.freeze.txt privé réactualisé. pipcheckPASS, aucun Torch/NeMo. Aucun backend lock/config/package modifié.
- Prototype **hors production** `scripts/memora-parakeet-experimental.py`: import module sansMLX/GPU, exige HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ; vérifie touspoids/assetsavantload. PyAVdecode bytes WebMOpus.bin etWAV→16kmonofloat32, tailoffset ; chunk30s/overlap2s ; phrases/timestampsnatifs validés ; aucunlangageanglaisfictif (`language:null`,confidence:null,uncertain:true). Argumentfr/encompat mais nonforçable par ce moteur. Nettoyagemodèle/cachefinally. Aucune preuve qualité/latence/inférence encore.
- 29testsCPU/offlinePASS couvrant downloadersTurbo/full/Parakeet, licenceCCBYrefusMIT, assets/corruption/guards, nativeoffsets/tempsinvalides/clamp, WAVetWebMOpussuffixebin. RuffPASS. TestlabCPUimport+WAVsansaucunmodulemlxPASS (`parakeet-lab-cpu.log`). Logs parakeet-preparation-tests.log et parakeet-decoder-tests.log.
- Espacefinal9.8GiB, seuil5GiB respecté même assemblage double. Fragments supprimés seulement aprèshashvalidé. Turbo/full3/autresmodèles/Ollama conservés.

Prochaine action : parent réserve GPU puis agentapi_tests lance son harness adaptateur sur corpus synthétiques indépendants. Ne pas interpréter une reformulation humaine comme transcription motàmot ; aucun audio personnel utilisé dans ce travail.
