# Contexte long LLM — validation réelle synthétique

Commande : `backend/.venv/bin/python scripts/memora-qa-long-context.py`, après fin et arrêt de toute la recette isolée, sans inférence MLX.

Résultat : **PASS rapport et chat**,56segments synthétiques traités en3lots. L'action du dossier Zéphyr et son échéance vendredi figurent uniquement dans le dernier segment ; le rapport conserve Alice, vendredi et la source finale ; le chat retrouve ce fait avec citation s-final. Les métadonnées de locuteur des sources sont prises en compte par le code actuel.

Latence mesurée : rapport51,082s ; chat22,074s. Preuves : `agents/logs/long-context.log` et `agents/logs/long-context.json`. Script terminé avec exit0. Aucune modification de ai.py ni d'autres sources applicatives pendant cette exécution.

Portée : source textuelle longue, segmentation multi-lots et conservation d'un fait/citation tardifs sur modèle local réel. Ce n'est pas une transcription d'un audio long, une mesure15min/2h, une preuve de diarisation ou une garantie générale d'exhaustivité/fidélité. Données exclusivement synthétiques ; service Ollama existant partagé, sans conversation ou donnée utilisateur.
