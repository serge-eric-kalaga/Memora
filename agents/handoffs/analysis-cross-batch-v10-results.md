# V10 — deux longs connus, rapport et chat réels

Exécution complète séquentielle Gemma4:e4b existant, corpus figé cross-batch-v1 (55segments/4lots par cas). Pas d'ASR/audio, pas de données privées. `agents/logs/analysis-cross-batch-v10.json` contient hashes AI/corpus, rapports/chats et CHAQUE génération brute/timing ; log séparé et snapshot `analysis-ai-v10.py`. GPU libéré, ROOT informé.

## Annulation/correction

Rapport63,686s ; chat31,223s. Critères ciblés PASS : actions vide ; décision unique budget initial annulé et remplacé par4700, source s55 ; ancienne validation2400 et travail Alice ne sont plus catégories actives. Résumés/topics gardent textes successifs, chacun préfixé « À mm:ss dans la réunion », puis source finale explicite annulation/remplacement à22:55. Le chat répond littéralement « Le budget final actuel est de quatre mille sept cents euros. Alice ne doit plus préparer la maquette. », sources[s55]. Pas de conflit indécidable ni vieille tâche encore demandée.

## Faits indépendants

Rapport56,566s ; chat21,738s. Critères ciblés PASS : action Mariam20janvier source s1 et action Rayan28janvier source s55 conservées indépendamment. Budget1800 conservé en résumé chronologique ; aucune fausse annulation/substitution. Chat « Rayan vérifiera les accès le vingt-huit janvier. », sources[s55].

## Portée et limites

Total173,213s pour deux rapports et deux chats. Ce sont cas de régression connus après corrections, pas réserve aveugle ni précision générale90%. Le traitement multi-lots produit une synthèse chronologique dans summary/topics ; l'état final des tâches/décisions/questions est réconcilié séparément. Les dates/owners originaux restent inchangés. Aucun ID arbitraire trié pour déterminer la chronologie ; ordre de la liste de sources utilisé.

Les preuves finales de ces deux cas sont dans les sources de candidats actifs. Le mécanisme de seconde vérification pour une preuve uniquement dans un résumé a des tests isolés (vrai/refus/citation inventée/questionrésolue) mais pas encore de validation réelle indépendante. Les trois nouveaux cas figés par api_tests sont reçus en lecture seule ; aucun modèle ne les a vus ici, aucun lancement sans autorisation. Leur runner devra remapper IDs opaques déterministes en gardant fixtureSHA et table inverse, sans transmettre attentes aux modèles.

Tests CPU avant réel :60 réussis en0,33s (AI/reconciliation/ASRroute/MLX), Ruff conforme. Singlebatch inchangé ; anciens scores V3 restent preuves versionprécédente, pas recréés comme validation V10. Toutes les tentatives V4–V8 ratées restent conservées.
