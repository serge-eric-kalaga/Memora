# Réserve ASR v3 : préparation et validation réelle

Après v2, ROOT a proposé une autre politique : français explicite final → Parakeet vanilla (chunks 30 s, overlap 2 s) ; anglais, auto/bilingue et live → Turbo. Cette décision postérieure à v2 nécessitait un nouveau holdout. Les références et cette politique ont été figées avant toute inférence v3 ; aucun réglage ni cas n'a été modifié après les résultats.

## Corpus

Source : `backend/test/fixtures/memora/accuracy-corpus.v3.json`.
SHA256 : **365dda9582568ffc81bf391bd76b920db57536cf7d2d58b2912f65f1f3d34a1b**.

12 textes nouveaux (4 FR, 4 EN, 4 mixtes), six conditions et deux négatifs : **74 fichiers, 588,39 s cumulées**. Cache séparé `.memora/accuracy-benchmark/v3/`. Montants 5600/56000 et 3200/32000 ; nouveaux noms, faits, lieux et termes techniques. Deux cas difficiles conservés : Jacques/phrases courtes et Jacques+Karen sans pause. Aucune voix ni donnée privée, aucun lexique injecté. Tous les SHA et sondes de référence ont été vérifiés avant ASR. Critères et normalisation sont dans le JSON.

## Provenance réelle

74 appels Turbo figé puis 74 appels à **`api.memora.ai.transcribe` de production**, via `--production-factory --fr-engine parakeet-mlx --fr-model-path .memora/models/parakeet-v3`. Configuration synthétique en mémoire, aucune application ou base principale créée.

Les wrappers d'observation, dans le processus du benchmark uniquement, ont vérifié exactement un provider et le vrai chemin/repo/SHA par cas : **24 appels Parakeet FR et 50 appels Whisper** (24 EN, 24 mixtes, 2 négatifs). Aucune hypothèse non française ne diffère. Les réponses ASR sont réelles ; seuls les tests CPU de dispatch utilisaient des stubs, identifiés comme tels. Les SHA de factory/providers et chaque appel observé figurent dans les JSON.

## Résultats

| WER numérique micro | Turbo | Route production |
|---|---:|---:|
| Propre |6,07% (15/247)|4,05% (10/247)|
| Bruit 20 dB |9,31%|4,45%|
| Bruit 10 dB |15,38%|10,93%|
| Opus 32 |6,88%|4,05%|
| Amplitude −24 dB |12,96%|9,72%|
| Échos |12,15%|10,93%|

Propre : FR **9/87 → 4/87** (10,34 → 4,60%) ; EN 4/88 = 4,55% et mixte 2/72 = 2,78%, inchangés. FR par profil : 4,60 / 3,45 / 9,20 / 12,64 / 4,60 / 5,75% pour propre/bruit20/bruit10/échos/Opus/faible. Les strates FR échos et plusieurs strates mixtes dépassent 10% : aucun «90% général» démontré. Sondes propres : 27/30 → 28/30.

**Deux régressions lexicales :** Docker → «d'auteur» en bruit10 ; Salif → «Sa vif» avec échos. Huit améliorations, notamment Rokia correctement écrit sur six conditions et Grafana retrouvé en bruit10. Aucune nouvelle perte comparative de négation, montant ou délai détectée dans cette inspection limitée. Des erreurs restent partagées : jeudi déformé avec échos ; «effacer les archives» devient «dépasser les archives» en bruit10. Les sondes ne sont pas un oracle sémantique.

Temps cumulés : **108,557 → 87,572 s**. Pics RSS : 2,219 → 2,708 Gio ; allocations MLX : 2,039 → 2,615 Gio. Quatre négatifs sans texte. Limite RSS 12 Gio non atteinte. Temps bout en bout incluant chargement, contrôles et instrumentation, pas une mesure pure du décodeur.

Preuves : `agents/logs/accuracy-{turbo,routed-fr-parakeet}-reserve-v3.{json,log}` ; comparaison par langue/profil/source, WER/CER/S-D-I et sondes : `accuracy-reserve-v3-comparison.json`. GPU et processus libérés après le test long ; services et données principaux intacts.

## Versions et limites

Preuves **avant ajout du guard `np.isfinite(samples)`**. ROOT a ajouté ce durcissement après libération du GPU ; modèle, chunks et décodage n'ont pas changé. Les SHA diffèrent : ne pas présenter ces essais comme la recette complète du dernier fichier. Une chaîne et recette finales courantes restent à vérifier par ROOT.

Le SHA complet ai.py couvre aussi des helpers LLM modifiés indépendamment pendant les tests. La fonction ASR n'a pas changé ; ne pas attribuer une différence globale du fichier à ASR. Les providers sont restés fixes pendant v3 et long95. Le test long enregistre en plus l'empreinte du bytecode chargé de `transcribe`, indépendante des positions de lignes.

Ce sont 12 sources TTS, pas 148 réunions indépendantes ni une garantie naturelle. Le holdout v3 est désormais consommé ; un réglage inspiré de ses erreurs exige de nouvelles sources pour une validation indépendante.
