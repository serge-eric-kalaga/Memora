# Installation MLX future : idempotence et vérification offline

**Futures exécutions seulement.** Le processus déjà lancé PID83493/session81420 n'a été ni arrêté ni relancé ; aucun fragment, poids ou config du téléchargement courant n'a été ouvert en écriture par cette tâche. Seuls le script et ses tests ont été édités ; les tests utilisent des dossiers temporaires et métadonnées simulées.

## CLI

- `python3 scripts/memora-download-mlx.py --check-only` : vérification offline, aucune création/écriture/résolution HF ; exit0 si modèle épinglé valide, exit2 sinon.
- `backend/.venv/bin/python scripts/memora-download-mlx.py` : vérifie d'abord installation portant un manifeste ; si valide, SHA256 complet puis sortie sans téléchargement ni réécriture. Sinon, reprise/téléchargement officiel épinglé (à lancer seulement après fin du processus courant, jamais en parallèle).
- Chemin par défaut absolu racine `.memora/models/mlx-large-v3-turbo`, override opérateur `MEMORA_MLX_MODEL_PATH`.

Le mode import et `--help` n'effectuent aucune connexion ni création de dossier. `--help` vérifié avec python3 sans lancer de modèle.

## Provenance et préservation

Dépôt `mlx-community/whisper-large-v3-turbo`, révision **a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb**, poids **1613977612 octets**, SHA256 **951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6**.

MetadataHF future interrogée explicitement à cette révision immuable ; révision/taille/SHA doivent correspondre avant création target ou écriture config/poids. Vérification locale du fichier entier réutilise par import-path `memora-benchmark-mlx.py::verify_model`, sans dupliquer la logique du hash local.

Un modèle validé reste strictement en lecture : config, poids, manifeste et éventuels restes.part ne sont pas réécrits/purgés. Le manifeste legacy actuellement produit par le processus en cours peut ne pas avoir de champ licence : accepté si provenance/hash/taille épinglés, sans migration ni réécriture. Un manifeste présent mais invalide provoque refus, pas remplacement silencieux.

Nouveaux manifestes seulement : licence MIT et source officielle upstreamWhisper enregistrées. La carte du checkpoint converti ne déclare pas elle-même une autre licence ; le code n'invente pas de champ licence provenant de l'APIHF. Provenance MIT upstream : https://github.com/openai/whisper/blob/main/LICENSE .

Reprise existante conservée : huit flux, fragments8MiB, cinq tentatives, octets des.tmp conservés ; ContentRange exact vérifié ; assemblage puis SHA global avant publication. ErreursHTTP ne journalisent pas les URLs signées/corps/headers, seulement classes et messages fixes.

## Tests réellement exécutés

`backend/.venv/bin/python -m unittest discover -s scripts/tests -p test_memora_download_mlx.py`

**8 tests PASS, 0,040s**, fichiers minuscules temporaires et FakeAPI uniquement :

- Installation valide, mode normal et check-only : aucun appel réseau/download ; bytes et mtimes inchangés pour config/poids/manifeste/.parts.
- Mode offline incomplet : refus sans créer target.
- Poids corrompus de même taille : rejet SHA complet, sans réparation/réseau.
- Mauvaise révision malgré hash correct : rejet.
- API simulée appelée avec revisionpin ; mauvaise taille/hash refusés.
- Métadonnées incompatibles refusées avant création target.
- CLI check-only exit0/2 testé avec chemin temporaire configuré.

Ruff format/check et py_compile réussis. `agents/logs/download-idempotence-tests.log` contient la sortie locale. **Aucun téléchargement réel, aucune vérification pleine du modèle courant, aucune inférence** exécuté dans cette tâche pour respecter le processus actif.
