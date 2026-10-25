# Comparaison locale unique Gemma/Qwen — rapport synthétique

**Une seule génération Gemma** effectuée. Script `scripts/memora-qa-gemma-report.py`, corpus identique au contre-exemple de `memora-qa-speaker-context.py` : Alice dit qu'elle préparera la démonstration sans date ; Bob annonce sa réunion marketing vendredi. Sources exclusivement synthétiques, aucun audio lu, aucun téléchargement.

Override `ai.MODEL='gemma4:e4b'` limité au processus de test puis restauré en finally. `MEMORA_OLLAMA_KEEP_ALIVE=0`, aucune modification du défaut de l'application ni du service Ollama. Préflight mémoire≥50% imposé par script.

| Mesure | Qwen3.5:4b | Gemma4:e4b |
|---|---|---|
| Temps rapport même corpus | 10,094s | 8,756s |
| Action Alice | ownerAlice, pas de date, source s1 | ownerAlice, pas de date, source s1 |
| Date vendredi de Bob | RéunionBob bien séparée mais aussi rangée en action, formulation « Bob aura lieu sa réunion... » | RéunionBob seulement résumé/sujets, formulation correcte |
| Décisions | [] | [] |
| Reformulation « a décidé » | absente dans ce run | absente |
| Références | non vides/autorisées | non vides/autorisées |

Gemma résumé exact : « Alice préparera la démonstration. Bob aura sa réunion du service marketing vendredi. ». Action unique : « Alice préparera la démonstration. », ownerAlice, deadlineNonprécisée, sources s1. Pas d'attribution de vendredi à Alice. Le champ owner du résumé combiné vaut Alice malgré présence d'un événementBob : ne pas interpréter ce champ comme responsable de tout le contenu résumé.

Mémoire système libre observée :64% avant,21% pendant (~3,4GiB encore libres),75% après fin/libération. Aucune pression excessive observée à ces échantillons, aucun processus/service arrêté. Ce n'est pas une mesure exhaustive du pic mémoire GPU.

Preuves `agents/logs/gemma-report-comparison.json` et `.log` : generation_count=1, sortie brute synthétique conservée, six contrôles true. Ruff/py_compile réussis. Ce corpus unique favorise Gemma sur lisibilité/événement vs action et latence de cet essai ; **insuffisant pour changer le modèle par défaut ou affirmer supériorité générale**. Ni chatGemma, ni longs rapportsGemma, ni stabilité sous charge testés ici. Licence/capacités vérifiées séparément par intégrateur avant éventuelle sélection.
