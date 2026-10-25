# Cohérence des rectifications entre lots — défaut confirmé

Deux cas synthétiques figés avant première inférence, corpus cross-batch-v1.json SHA256752d0e37cd385ebcbfeadde1703deb3356a547ed5452c4d93b518327f6aa216d.55segments/cas, **4lots** réels parcas (pas3annoncés avant mesure). Bavardagefictif sansnouvelengagement au milieu ; sources/attentes exactes dans fixtureversionnée. Aucune donnée utilisateur lue. ai.report/answer GemmaV3 réels locaux,2cas uniquement, pas de retest/modifai.py. GPU libéré après158,388s d’appels≈2min38s, ROOT informé.

Preuves : agents/logs/analysis-cross-batch-v1.json/log/.review.json ; ai_sha256af7b3e1cc3319696899f158e8e75dcac942d7822efeb922b628e30b8c07a27e9, identique snapshotV3. Revue sémantique manuelle, aucunjugeLLM.

## 1. Annulation/action et correction/montant tardives : FAIL

Début : Aliceprépareramaquette12janvier[s1] ; collectifvalide2400EUR[s2]. Toutfin[s55] : cettepréparationannulée et plusdemandée, ancienbudgetannulé/remplacépar4700EURfinal. Rapport53,894s ; chat30,821s.

Rapportfinal contient simultanément :
- actions « Alice préparera la maquette pour le douze janvier. » [s1], ownerAlice/deadline12janvier, **encorepositive**, et itemannulation[s55].
- decisions « Un budget de deux mille quatre cents euros est validé. » [s2], encorepositive, et décisionannulation/remplacement4700[s55].
- résumés anciensaffirment actionfuture etvalidation2400, puisannulationplusbas, aucun statutexplicite historique/remplacé desitemsanciens.

Le faitfinal et sa source ne sont PAS perdus ; la synthèse n’applique PAS leur effet sur itemsantérieurs. Citations autorisées ne résolvent pas cette cohérence.

Chat àquestionbudgetfinalactuel/Aliceencoretenue prépare répond « Il existe des informations contradictoires… », cite anciens2400/action etfinal4700/annulation[s2,s1,s55]. C’est prudentfaceàcontradictionréelle, maisici la source55 est une **rectification finale explicite** : attendu budgetactuel4700 etAliceplusobligée. Échec de miseàjourglobale, pas inventiondechiffre.

Causecode vérifiée : report construit combined et append chaqueitemdechaquelot puisreturn, sansréconciliation globale desannulations/corrections. answer réduitfindings partiels maisneconservepasexplicitementstatutrectification/ordretemporel dans sa structure ; modèle traite les deuxversions comme contradictionindécidable.

## 2. Dernier fait indépendant, sans annulation : PASS ciblé

DébutMariamcompterendu20janvier[s1], budget1800[s2]. FinRayanvérifieaccès28janvier[s55], dit tâchesdistinctes/aucuneannulation/budgetinchangé. Rapport47,588s,chat26,085s.

Reportactions conservent Mariam20janvier ET Rayan28janvier, sanséchangedates ; budget1800conservé. Chat « Rayan vérifiera les accès le vingt-huit janvier. » [s55]. Ce contrôle doit demeurer aprèsfix : une correction tardive n’autorise pas supprimer les faits antérieurs sansrapport.

Suite ROOT : réconciliation globale bornée, chronologie/provenance conservées, rectificationexplicite désactiveancienitemactif etpeutleconserver commehistoriqueclairementétiqueté ; nepasappliquer « dernierlot gagne » àtout. Chat doitdifférencier rectificationexplicite etcontradictionnonrésolue. Aucunpatch réalisé par cetagent ; ce nouveaucontre-exemple étend le périmètre despetitscorpus≥90 précédents, donc nepasétendreleursclaimsauxlonguesréunions sansnouvellevalidation.

Script reproductible scripts/memora-qa-cross-batch.py --run refuseécraserpreuves existantes ; --output PATH permet un nouveau fichier pour retestROOT ; CLIpréparation sans--runnechargepasIA. RuffPASS.
