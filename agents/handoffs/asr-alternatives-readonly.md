# Alternatives ASR — recherche en lecture seule, 25 octobre 2026

Aucun poids alternatif téléchargé, aucune dépendance installée, aucune configuration modifiée. Le téléchargement large-v3 comparatif déjà autorisé continue séparément. Aucun benchmark Qwen/Parakeet réalisé ; aucun gain de précision ou mémoire mesuré sur cette machine.

## Candidats vérifiés

Métadonnées HfApi officielles `model_info(files_metadata=True)` lues le 25/10 :

| Conversion | Révision | Poids | Licence |
| --- | --- | --- | --- |
| mlx-community/Qwen3-ASR-1.7B-8bit | a8379a2e2f9e313c9292cdf1af4055ab56d50d55 | model.safetensors 2463307541 octets | Apache-2.0 |
| mlx-community/parakeet-tdt-0.6b-v3 | ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15 | model.safetensors 2508288736 octets | CC-BY-4.0 |

SHA256 Qwen : `bf304b009cc7eca79283056f787b44c952d24ac22cec787b39732bba3c23c13c`.
SHA256 Parakeet : `05e01c7f396c298cf7d23f61da7b504adeab698f0aaeafd9c82d198625464592`.
Ces chiffres décrivent les poids, pas le pic mémoire d'inférence ni tous les fichiers nécessaires. Conserver attribution/licence amont et conversion ; CC-BY exige attribution et indication des modifications.

Sources : [Qwen officiel](https://huggingface.co/Qwen/Qwen3-ASR-1.7B), [conversion Qwen](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit), [NVIDIA officiel](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), [conversion Parakeet](https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3).

## Runtime, horodatages et longs audios

Lecture du code officiel mlx-audio main (branche mutable, à épingler avant utilisation) : [Qwen](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/models/qwen3_asr/qwen3_asr.py), [Parakeet](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/models/parakeet/parakeet.py), [loader](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/utils.py), [dépendances](https://github.com/Blaizzy/mlx-audio/blob/main/pyproject.toml), [exemples officiels](https://github.com/Blaizzy/mlx-audio/blob/main/docs/getting-started/quickstart-python.md).

- Qwen MLX découpe les longs audios aux faibles énergies (`chunk_duration` défaut1200s). Le résultat standard crée un segment pour chaque chunk avec son étendue audio, pas un alignement mot à mot. La langue auto est extraite par chunk. Budget `max_tokens` partagé entre chunks : un adaptateur Memora devra limiter les chunks, contrôler fin complète/budget et refuser toute troncature silencieuse. Ne pas recycler un temps calculé à partir du progrès tokens comme citation précise.
- Les timestamps mot à mot Qwen requièrent un **ForcedAligner séparé** (modèle supplémentaire 0.6B), présenté par Qwen et par les exemples MLX. Le modèle ASR seul n'apporte donc pas les citations fines requises. Les étendues VAD locales pourraient fournir des citations grossières explicitement annoncées, ou aligner après transcription avec un composant vérifié.
- Parakeet TDT dérive les tokens/start/duration de ses pas de décodage puis reconstruit les phrases. `generate` accepte un découpage explicite, défaut **sans découpage** : ne pas donner une réunion de2h d'un bloc. Overlap défaut2s quand chunking activé, fusion de tokens, offsets temporels corrigés. Streaming5s/overlap1s disponible. Les sorties streaming ont un champ `language="en"` codé en dur dans ce fichier : **ne pas le présenter comme détection anglaise** pour des paroles françaises. Pas de preuve de détection fine ni diarisation.
- Les deux cartes couvrent français et anglais. Leur qualité sur accents, noms propres, silence, FR/EN alterné et audio de réunion reste à mesurer ; aucun classement marketing utilisé comme preuve.

## Compatibilité 16Go et installation

Poids≈2.5Go chacun : candidats plausibles pour16Go **en inférence unique sérialisée** avec LLM déchargé, mais mémoire d'activation/pic/cache non mesurés. Pas de promesse de tenir avec plusieurs modèles simultanés. Parakeet utilise ici F32 ; comparer temps/mémoire réellement plutôt que déduire de0.6B vs1.7B quantifié.

mlx-audio MIT, pyproject actuel : `mlx==0.32.4` (déjà version présente), `transformers>=5.14.0`, huggingface_hub>=1.0, miniaudio, numpy, scipy, sentencepiece, sounddevice, tqdm ; extra STT ajoute zstandard. Une installation `pip install -U` dans le backend peut remplacer Transformers et dépendances partagées. Recommandation : environnement jetable benchmark séparé + versions/révision verrouillées avant intégration ; pas d'installation NeMo/CUDA pour Apple Silicon simplement parce que la carte NVIDIA les cite.

Le loader accepte un chemin local. Qwen post_load_hook charge tokenizer et feature extractor depuis ce chemin, avec `trust_remote_code=True` : inspecter `auto_map`/fichiers Python du snapshot avant tout chargement, fournir snapshot complet local et `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1`, prouver qu'aucun téléchargement secondaire n'est tenté. Parakeet a aussi besoin config/tokenizer complet local. Chargement local plausible d'après code, pas encore vérifié réseau coupé.

## Recommandation pour la décision suivante

Premier benchmark **Parakeet MLX** si large-v3 n'améliore pas assez : architecture distincte, horodatages natifs utiles aux citations et moins d'intégration d'alignement que Qwen. C'est un choix d'effort et de traçabilité, pas une affirmation de meilleure précision. Garder l'attribution CC-BY et ignorer le faux champ langue streaming.

Second candidat **Qwen3-ASR1.7B8bit** : architecture différente prometteuse à examiner, Apache2, mais coût d'alignement supplémentaire et contrôle strict du budget génération. Tester les mêmes corpus synthétiques français réaliste, anglais, mixte, bruit/silence, noms propres et long début/fin, avec WER/CER, références audio et pic mémoire. Décision d'installation/téléchargement alternatif réservée au parent.
