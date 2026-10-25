# Holdout analyse figé avant sorties

2026-10-25T08:20:16Z, aucun appel modèle sur ce corpus par cet agent. Fichier `backend/test/fixtures/memora/analysis/holdout-v1.json`, SHA256 `55bb835496c545b5e19648eae099c16e18c599b8f796dd2cda6c4bbd5e0fe8d3` :8cas,10faits atomiques,1chat.

Couverture : piste conditionnelle vs demande explicite Karim sans acceptation inventée ; refus collectif explicite8000EUR (doit rester une vraie décision négative) ; engagement nouscollectif sans Nora seule ; pasavant3novembre borne démarrage et non deadlinefin ; no laterthan9décembre borne supérieure/ demandeEthan ; annulation ancienne tâcheAwa15décembre puis remplacementIdriss18décembre ; propositionserveurEN nonapprouvée et refusassignationRachel ; possibilité conditionnelleNadia avecfinancementnonconfirmé/aucunengagement. Lexique, noms et dates distincts du tuning, sansjeudi/copieexempleprompt.

Attentes et contre-affirmations écrites AVANT inférence. Ne pas corriger les attentes à partir des sorties pour masquer échecs ; si ambiguïté véritable, noter arbitragereview et son impact, sans sélectionner après coup le verdict favorable. Les dates sans année restent sansannée.

CLI nouvelle `--corpus PATH`, appliquée au run etscore/hachage. Exemple à exécuter uniquement après signalROOT/fenêtreGPU :
`backend/.venv/bin/python scripts/memora-benchmark-analysis.py --run --corpus backend/test/fixtures/memora/analysis/holdout-v1.json --output agents/logs/analysis-holdout-v1.json`
Puis revue sémantique manuelle des8cas,10faits et1réponse ; score avec les mêmes --corpus/--output et --score agents/logs/analysis-holdout-v1.review.json.

Tuning corrigé reste corpus cases-v1.json12cas/15faits/3chats ; sortie distincte analysis-benchmark-v2.json proposée, ne pas écraser baselinev1. Les deux scores doivent être séparés, pas moyenner pour annoncer90%. Le corpus holdout est limité et construit par l’agent connaissant les catégories d’erreurs, mais aucune sortie de ces nouvellesphrases n’était connue ni utilisée pour modifier le prompt.

Préparation vérifiée sansIA : CLIdefaultavec--corpus renvoie8IDs/hash/inferencefalse ;3tests scoring offline PASS ; RuffPASS. Aucune éditionai.py, pas téléchargement/inférence. Attente signalROOT.
