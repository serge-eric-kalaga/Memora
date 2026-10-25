# Choix français explicite : comparaison Whisper Turbo/Full sur réserve existante

Aucun audio privé, nouveau téléchargement ou changement de code/configuration active. GPU libéré. Comparaison demandée après constat que Parakeet accepte le hintfr sans pouvoir réellement forcer le français. **Le choix de langue peut être respecté comme paramètre de décodage, sans garantie absolue sur les mots produits.**

## Méthode et provenance

Réutilisation de la réservev3 consommée, pas nouveauholdout : corpus `backend/test/fixtures/memora/accuracy-corpus.v3.json`, SHA365dda9582568ffc81bf391bd76b920db57536cf7d2d58b2912f65f1f3d34a1b. Quatre sourcesFR×sixprofils =24cas, plus silence/bruit seuls =26appelsFullréels. Même cache préparé, audioSHA/référence identiques contrôlés pour chaqueid aux résultatsTurbo/Parakeet préexistants. Pas modification de références, normalisationnumérique, lexique ou seuils.

Même snapshotadapter que baselineTurbo `agents/logs/asr-baseline-20261025.py`, variantebaseline, languagenative (=frpour24cas, autopour2négatifs), VAD et paramètres identiques. Seul poidsWhisper complet changé dans le processuslab. ModelFull localdéjàprésent repo mlx-community/whisper-large-v3-mlx, revision49e6aa286ad60c14352c404340ded53710378a11, poidsSHA05ff791ce3630fae47e7c51004e9666204d786246ec07cac6110af768099b40d/3083520416octets, intégritécomplète vérifiée avant inférence. Aucune configurationmain chargée/écrite par ce test.

Bruts : `agents/logs/accuracy-full-fr-reserve-v3.json/log`. Comparaison recalculée et références/SHAaudio vérifiées : `accuracy-full-fr-reserve-v3-comparison.json`, reproductible via `scripts/memora-compare-fr-engines.py`. RésultatsTurbo et routeParakeet historiques restent datés de leurs essaisv3 ; Full nouveau n'est pas nouvelle validation aveugle.

## WER numérique micro français

| Profil |TurboFRforcé|FullFRforcé|Parakeetauto, noncontraint|
|---|---:|---:|---:|
|Tous24cas|81/522=15,52%|82/522=15,71%|35/522=6,70%|
|Propre|9/87=10,34%|9/87=10,34%|4/87=4,60%|
|Bruit20dB|17,24%|13,79%|3,45%|
|Bruit10dB|21,84%|24,14%|9,20%|
|Échos|16,09%|19,54%|12,64%|
|Opus32|12,64%|9,20%|4,60%|
|Amplitude−24dB|14,94%|17,24%|5,75%|

Ce sont quatre textes répétés sous six dégradations, pas24réunions indépendantes. Aucun«90%françaisgénéral» atteint ou prouvé. Parakeet reste meilleur sur ce corpus, mais son absence de langueforcée ne répond pas au contrat d'un choixFR explicite. Ne pas effacer ce compromis des résultats.

## Inspection noms, nombres, négations

Lecture manuelle des24pairesTurbo/Full :

- Full corrige Rokia sur6profils, là où Turbo écrit Roquia. Ce gain représente6sondes supplémentaires mais une seule source répétée.
- Full préserve «ne doit pas effacer les archives» sousbruit10 là où Turbo dit «ne doit pas dépasser les archives» ; Grafana reste abîmé dans les deux («tabou…»). Docker conservé dans les deux dans ces sorties.
- Full dégrade encore davantage le cascourtvoixJacques : Salif devient salut, sujetpersonnel changé, mots inventés et jeudi perdu dans deux profils qui conservaient la sondechezTurbo. Une sortiebruit10 inclut un fragmentanglais malgréfrforcé ; Turbo avait aussi un fragmentanglais dans un autre profil de ce casdifficile. Donc même languagefr ne garantit pas absence totale de dérive.
- Gaoua est malorthographié dans les deux (Gawa/Gaua/Gawah). Condition «si la connexion fonctionne», statut hypothèse et salle nonréservée conservés. Pas correctionuniverselle des lieux.
- Montants5600/56000 et négation de paiement conservés dans les deux sur6profils. Aucun nouveau changement de montant constaté. Négation de signature globalement conservée, mais nom/acteurSalif souvent faux ; ne pas qualifier les faits de complètementfidèles à partir d'une sonde de négation seule.

Sondes lexicales préexistantes : Turbo49/66, Full54/66, Parakeet55/66. DeltaFullvsTurbo =+6Rokia,+1effacer,−2casSalif/jeudi. Ces sondes ne sont pas un juge sémantique. Les hypothèses originales et passes parsonde figurent dans le comparatifJSON.

Deux négatifs sans texte pour les trois moteurs.

## Temps et ressources

Sur26cas sélectionnés : Turbo40,472s, Full62,454s, Parakeet15,124s. PicRSS observé dans les lignes sélectionnées : Turbo2,219Gio, Full3,415Gio, Parakeet2,708Gio. Mesures includes chargement/contrôles, anciennes séries pourTurbo/Parakeet et nouvelle pourFull ; pas benchmark matériel pur synchronisé. Full n'apporte pas de dominationglobale malgré coût supérieur.

## Recommandation bornée

**Choisir Turbo pour le routage français explicitement forcé**, comme compromis ressources/bruitfort/échos/amplitudefaible et respect d'un véritable paramètrelanguagefr. Full n'a aucun gainWERglobal sur ce sousensemble, coûte davantage et dégrade les cascourtsdifficiles ; il apporte néanmoins des gainsnoms/uneaction précise qu'il faut documenter. Ce n'est pas une preuve que Turbo est toujours plusprécis ni que le problème personnel est résolu.

Garder Parakeet uniquement en mode explicitementautomatique/noncontraint si le produit veut préserver son avantage mesuré sur le français synthétique, sans le présenter comme françaisforcé. Aucun remplacement lexical ou traductionLLM silencieuse après ASR. La transcription d'une réunionexistante doit rester une action volontaire versionnée. Décision/intégration confiées à ROOT, aucune activation effectuée ici.

## Reproduction

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 backend/.venv/bin/python scripts/memora-benchmark-accuracy.py --run --prepared --corpus backend/test/fixtures/memora/accuracy-corpus.v3.json --split holdout --cases reserve3-fr-facture reserve3-fr-service reserve3-fr-short-hard reserve3-fr-proposition silence noise-only --model-path .memora/models/mlx-large-v3 --adapter-path agents/logs/asr-baseline-20261025.py --variant baseline --language native --label full-fr-reserve-v3-new
backend/.venv/bin/python scripts/memora-compare-fr-engines.py
```

La secondecommande relit les chemins de résultats historiques nommés dans le script ; adapter son entrée avant un nouveau nom, ne pas écraser les preuves. Aucun réglage n'a été changé en réaction aux résultats et aucune nouvelle série retunée n'a été lancée.
