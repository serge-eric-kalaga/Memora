# Trois longs indépendants V10 — échec strict3/3

Corpus figé SHA ec64b0a74f57a7bc0419f1e7fc649fe14e14f6d166395a0282a02b1c1225449f. IDs source remappés opaques SHA déterministes avant modèle ; table inverse dans résultats, champs kind retirés, attentes jamais transmises. Trois lots par cas. AI SHA enregistré et stabilité pendant exécution vérifiée true. Preuves `analysis-long-independent-v10.json/log`, bruts après chaque génération. Pas de questions dans corpus donc aucun chat inventé. Pas de données privées.

- Proposition d'annulation non retenue,72,065s : **FAIL**. Élise/jeudi extraite correctement au map puis supprimée comme superseded parce qu'une annulation a été proposée, malgré refus final. Nicolas/lundi gardé, pas de tâche Maxime finale. Refus de proposition correctement conservé en décision. Défaut relationnel de réconciliation.
- Annulation/réaffectation/correction,68,009s : **FAIL explicite sans publication**. Plan marque confirmation finale Benoît superseded en citant sa propre source, garde ordre rejette ; pas de rapport final. Ancienne Ariane et question semblent candidates à mise à jour, mais aucun succès partiel n'est assimilé à un résultat utilisable.
- Citation hostile refusée,58,591s : **FAIL**. Accord Aster maintenu, pas de fausse demande de paiement ni marqueur hostile remplaçant rapport. Cependant tâche Fanny/avantmardi extraite initialement est supprimée comme superseded par sa confirmation, et rappel final est not_action. Résultat perd une vraie tâche.

Total198,665s, RAM libre système20–78% sur99échantillons2s ; pas RSS par modèle ni garantie machine. Aucun retuning pendant ces3cas. Code identique, sorties ratées préservées. Pas de claim90% global.

## Quatre courts de régression après les longs

Même code V10 : `analysis-reserve-v2-v10.json/.review.json/.score.json` et log.4rapports37,259s+chat3,615s=40,874s. Sorties/items/chat exactement identiques V3 (contrôle structurel) et relus sur textes synthétiques. Même adjudication :17/18éléments soutenus94,44%,8/8faits,1chat correct,0violationcritique. Défaut inchangé : topic invente « correction de l'exemple » ; u2 inline dans chat anglais traduit. Ceci confirme la non-régression courte, pas les longs ; réserve déjà connue donc pas validation aveugle.

GPU libéré avant chantier CPU V11. ROOT demande ensuite veto conservateur des suppressions non vérifiées, sans convertir un classement en vérité.
