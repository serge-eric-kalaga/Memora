# Réconciliation V6 : deux plans réels, échec sémantique

Exécution isolée Gemma4:e4b existant, keep_alive0 ; aucune ASR ni données personnelles. Deux plans seuls depuis extractions réelles préservées V1, pas un nouveau parcours bout en bout. Source figée `agents/logs/analysis-ai-v6.py`, hashes AI/corpus/baseline intégrés dans `agents/logs/analysis-plan-v6.json`. Bruts, résultats déterministes et temps préservés ; log séparé. GPU libéré et ROOT prévenu.

## Cas annulation/correction — 32,010s

Le plan reclasse les anciennes préparations Alice et validations2400 comme remplacées, références s55. Application déterministe les retire des catégories actives et les affiche explicitement en historique avec références ancienne+finale. Le budget final4700 et l'annulation explicite restent dans summary/decisions selon extraction originale. Amélioration réelle sur le défaut initial.

**Échec restant** : c20 « La préparation de la maquette par Alice est annulée. » est classé current et demeure dans actions. Ce constat d'annulation n'est pas une tâche. Le modèle explique correctement le texte mais ne respecte pas la catégorie, malgré statut not_action disponible seulement pour les actions.

## Cas indépendant — 21,671s

Les deux actions Mariam20janvier et Rayan28janvier, ainsi que budget1800, restent présents. Cependant le plan marque à tort le résumé de l'engagement Mariam comme remplacé en citant s55 : explication « c1 est remplacé par c5 », alors que c5 est simplement l'action extraite de la même source initiale. Aucun changement réel. Il marque aussi des discussions répétées comme remplacées par les occurrences suivantes s37. Ce sont des répétitions, sans rectification explicite.

**Échec** : ces faux statuts produisent des historiques « remplacé » factuellement faux. Un simple contrôle de référence ultérieure ne prouve donc pas la relation sémantique de remplacement. Le schéma borne les catégories mais ne garantit pas la vérité de la classification.

## Conclusion bornée

Schéma anyOf techniquement accepté ;55 tests mock/provenance passent mais les deux plans réels ne satisfont pas tous les critères. Aucune nouvelle inférence/full rerun lancé. Ne pas attribuer ces résultats à une réussite générale, ni aux scores courts V3.

Piste à arbitrer avec ROOT : distinguer explicitement répétition/current des véritables transitions, exiger un extrait littéral exact de la modification ultérieure et sa cible avant toute suppression, puis vérifier dans une étape étroite indépendante les seuls changements proposés. Le contrôle de sous-chaîne peut prouver l'origine de l'extrait ; il ne prouvera pas à lui seul son interprétation. Éviter toute suppression lexicale ou conversion silencieuse de statut. Une alternative prudente est refus explicite du traitement multi-lots lorsque cohérence non vérifiable, tout en conservant sources et versions ; ce serait une limite fonctionnelle, pas une réparation achevée.

## Comparaison Qwen3.5:4b sur les mêmes plans

Essai expérimental local uniquement via `--model qwen3.5:4b`, aucun changement ai.py ni configuration principale. Deux appels, même schéma/candidats/règles. Preuves `analysis-plans-qwen-v6.json` et log, avec bruts et hash ai identique. GPU libéré après fin.

Annulation :40,489s, rejet garde propre-source. Le candidat ancien montant2400 est current avec seulement s55 alors que son explication reconnaît le remplacement ; plusieurs autres références current visent une autre occurrence répétée. Aucun résultat n'est appliqué silencieusement. Indépendant :43,861s, guards passent mais vraie action Mariam supprimée comme not_action, expliquée abusivement comme état d'engagement sans tâche. **Échec sémantique**, pas d'activation du modèle spécialisé. Total84,350s contre53,681s Gemma, sans meilleur résultat fiable. Instantané système40% mémoire libre pendant le second appel ; pas de série/pic RAM enregistré, ne pas en déduire un pic de processus.
