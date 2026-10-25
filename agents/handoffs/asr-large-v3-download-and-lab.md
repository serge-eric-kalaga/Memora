# Large-v3 comparatif et laboratoire séparé — 25/10/2026

## Téléchargement complet terminé

`scripts/memora-download-large-v3.py` réutilise le transfert reprenable de `memora-download-mlx.py`, dont seul le nom des poids est devenu paramétrable (défaut Turbo inchangé). Nouvelle destination fixe `.memora/models/mlx-large-v3`, aucune configuration main modifiée, aucun modèle existant supprimé/remplacé. Aucune inférence exécutée ici.

- Source officielle HF `mlx-community/whisper-large-v3-mlx`, révision `49e6aa286ad60c14352c404340ded53710378a11`.
- `weights.npz` : 3083520416 octets, SHA256 complet `05ff791ce3630fae47e7c51004e9666204d786246ec07cac6110af768099b40d` vérifié après368fragments et une seconde fois par `--check-only` offline.
- `config.json`269octets. README/provenance MIT enregistrés. Fragments temporaires supprimés après validation uniquement.
- Tests downloader 11PASS, Ruff PASS. Logs `large-v3-download.log`, `large-v3-integrity-check.log`, `large-v3-downloader-tests.log`.
- Commande reproductible : `backend/.venv/bin/python scripts/memora-download-large-v3.py [--check-only]`. Un install validé est uniquement relu/hashé, pas réécrit.

## Laboratoire Parakeet prêt, sans poids

Venv privé `.memora/asr-lab`, Python3.12.14, installation officielle PyPI wheels-only `mlx-audio[stt]==0.6.1`. Freeze complet `.memora/asr-lab/requirements.freeze.txt` privé/ignoré. Backend `uv.lock`, venv backend, main et Ollama inchangés. Aucun `.pth` ni partage de site-packages nécessaire.

Versions : mlx-audio0.6.1/MIT ; mlx0.32.4+mlx-metal0.32.4/MIT (mêmes versions backend) ; transformers5.20.2/Apache2 ; huggingface-hub2.3.0/Apache2 ; numpy2.5.4 ; scipy1.18.1 ; miniaudio1.71 ; sounddevice0.5.6 ; sentencepiece0.2.2 ; tokenizers0.23.3 ; zstandard0.25.0. Ni Torch ni NeMo installés. `pip check` : No broken requirements found.

Premier accès à l'index MLX a répondu aucune version ; vérification PyPI puis retry officiel réussi (pas contournement). Logs `asr-lab-install.log` et `asr-lab-install-retry.log`, `asr-lab-check.log`. Espace libre final13GiB, seuil5GiB respecté pendant assemblage double large-v3. Pas d'import MLX ou de chargement modèle/GPU pour ce contrôle : versions obtenues via importlib.metadata, sources lues statiquement.

## Hors ligne et hooks lus dans la version installée

`mlx_audio/utils.py:get_model_path` retourne le chemin local existant ; chemin local absent déclenche FileNotFoundError. Un identifiant Hub déclenche snapshot_download explicite : ne pas le passer lors du benchmark offline. Parakeet utilise vocabulaire de config et tokenizer package, pas de post_load_hook remote dans son fichier. Aucun poids Parakeet téléchargé et aucune inférence lancée.

Pour futur benchmark, obtenir snapshot complet épinglé/hash vérifié dans nouveau dossier, passer chemin absolu existant avec `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`, puis prouver absence de réseau. Découpage explicite requis (défautgenerate sans chunk), timestamps TDT natifs. `language='en'` streaming hardcodé à ignorer comme détection. Qwen post_load_hook porte `trust_remote_code=True` : audit supplémentaire avant éventuel essai. La compatibilité chargement/inférence offline reste NON TESTÉE tant que décision parent de télécharger les poids n'est pas donnée. Aucun poids alternatif autorisé par cette préparation.
