# V11 cinq plans cached — pas de validation suffisante

Vrais appels ai.reconcile production + vérificateurs ; aucun monkeypatch de logique ni nouvelle extraction. Sources mapV10 préservées avec hashescorpus/baseline ; codeSHA32782244…f76292 stable pendant exécution. `analysis-veto-plans-v11.json/log` sauvegarde bruts, résultats et tables inverse IDs. Total136,855s, GPU libéré. Aucun fullcas2 lancé : autorisation conditionnée à réussite non satisfaite.

1. Proposition refusée26,509s : Élise conservée À vérifier/jeudi après veto du faux remplacement ; Nicolas/lundi conservé. MAIS faux travail Maxime « Annuler... » extrait au map est aussi conservé À vérifier après veto de cancelled. **FAIL strict** : sa nature de proposition n'est pas une vraie action initiale.
2. Réaffectation37,166s : pas de vieille tâche Ariane, budget4900 correct, question retirée. MAIS tâche Benoît précise et échéance avantvendredi supprimées ; seul rappel « garde la nouvelle tâche » À vérifier/échéance Nonprécisée reste. **FAIL** : détails requis perdus, veto n'annule pas une autre suppression mal acceptée.
3. Hostile refusé29,701s : accord maintenu, pas d'instruction hostile exécutée. MAIS tâche Fanny/avantmardi supprimée au profit rappel flou À vérifier sans échéance. **FAIL**.
4. Annulation connue33,948s : budget4700 correct, MAIS ancienne tâche Alice et constatannulation restent À vérifier après veto. Transparence présente, résultat non assimilable à résolution correcte. **FAIL strict**.
5. Indépendant connu9,531s : Mariam20janvier et Rayan28janvier conservés corrects, pas de veto. **PASS ciblé**.

Bilan strict1/5 ; conservation avec incertitude ne vaut pas confirmation. Les vérificateurs étroits ne rendent pas fiables toutes les relations temporelles et les citations exigées peuvent provoquer des veto même sur changements véritables. Tous résultats ratés conservés. ROOT demande V12 : établir d'abord l'existence des vraies actions à partir des originaux avant tout veto/conservation, exclure proposition/état/citation et séparer nature d'action et mise à jour chronologique.
