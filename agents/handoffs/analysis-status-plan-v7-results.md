# V7 expérimental : contexte actif court

ai.py inchangé ; modifications uniquement dans le probe `--active-only`. Même Gemma/schéma/règles, extractions V1 préservées. Deux plans seuls, pas nouveau map/retranscription. Résultats/bruts/hashes `agents/logs/analysis-plans-gemma-v7.json`, log séparé. GPU libéré.

- Annulation :4candidats,1581caractères,8,684s. Ancienne décision2400 et ancienne action Alice deviennent remplacées et sont retirées des catégories actives. Décision finale4700 conservée. **Échec** : le constat « La préparation de la maquette par Alice est annulée. » reste current dans actions. L'explication reconnaît l'annulation mais classe la vérité de l'énoncé plutôt que sa nature de tâche.
- Indépendant :2candidats,865caractères,6,026s. Mariam20janvier et Rayan28janvier restent deux actions current correctement sourcées. Aucun faux remplacement observé dans les catégories actives.

Summary/topics reconstruits dans le probe comme copies exactes chronologiques avec préfixe position dans réunion, sans classification ni censure. Cela garde les états successifs comme historique de lecture, sans promettre une synthèse finale globale. Ces corpus connus ont toutes les preuves finales dans les sources de candidats actifs (s55). Cette couverture fermée ne prouve pas le cas d'une réponse/annulation portée uniquement par un résumé sans candidat actif. ROOT demande un contexte dérivé compact des résumés et une expansion littérale ciblée avant intégration générale.

Résultat global : échec restant de catégorie, pas une validation bout en bout. Piste conceptuelle : séparer classification de nature (tâche réelle/état/annulation) et statut temporel, car current seul peut décrire un constat vrai sans travail à réaliser ; pas de filtre lexical métier ni transformation silencieuse.
