# V8 : statuts catégoriels sans current pour actions

Deux plans seuls depuis mêmes extractions préservées, Gemma existant, pas données privées. Snapshot `agents/logs/analysis-ai-v8.py`, preuves brutes/hashes `analysis-plans-gemma-v8.json` et log. GPU libéré.

Définition de work_to_do : travail explicitement encore demandé ou engagé à accomplir ; le schéma l'autorise uniquement pour actions et leur interdit current. Nonactions gardent current. Not_action reste catégorie actions seulement. Application conserve work_to_do comme tâche.

- Annulation8,316s : budgetinitialsuperseded, ancienneactioncancelled, budgetfinalcurrent, constatannulationnot_action. Actions finales vides. Critères ciblés satisfaits sur ce cas connu.
- Indépendant4,771s : **échec**. Les deux tâches explicites Mariam et Rayan sont not_action ; explications se contentent de répéter qu'ils feront les travaux. Aucun candidat restant publiable dans le résultat expérimental restreint ; garde refuse le résultat plutôt que publier un faux succès. Aucun correctif automatique/silencieux.

Conclusion : changer le nom du statut supprime l'ambiguïté observée sur l'annulation mais ne rend pas fiable la classification des vraies tâches au futur. Pas de full rerun ni de généralisation de succès. Delta V8 dans ai.py limité à enum, schéma par catégorie et définition de prompt ; contexte actif court reste exclusivement monkeypatch du probe, non intégré à la production. À arbitrer avant toute intégration/reprise des tests.
