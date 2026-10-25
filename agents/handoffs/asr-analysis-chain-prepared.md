# Deux chaînes ASR → rapport figées avant résultats Parakeet v2

Fixture `scripts/fixtures/memora-asr-analysis-chain.v1.json`, SHA256 `b38072c539f69bb7be6e67a83d064edb0669c7afd75b086683e3814a367a2875`. Aucun modèle appelé pour cette préparation, aucune lecture des sorties Parakeet v2. Références tirées uniquement du corpus accuracy-corpus.v2.json et de son manifeste audio préparé ; SHA corpus, référence texte et audio contrôlés. Aucun cas sélectionné sur son score. Deux cas clean fixes, pas une preuve généraliste de qualité bruit/2h.

1. `reserve-fr-budget` : facture non réglée aujourd’hui ; montant1600euros plutôt que16000 ; actionfutureNadia/vérifierrelevé/mercredimatin.
2. `reserve-mixed-infra` : servicePythonattendaccord ; interdictionrestartavantvendredi ; actionfutureInès/conservertoutessauvegardes/sanséchéance.

Ces sources comportent contraintes/négation, faits financiers/techniques et actions nominales explicites. Elles ne comportent pas une approbation positive à inventer pour remplir la rubrique décisions. Vendredi est borne minimale du redémarrage, pas promesse de redémarrer vendredi ni deadline de sauvegarde. Nadia/Inès sont sujets nommés des actions, pas attribution des voix. Aucune année/datecalendaire inventée.

## Exécution future après signal ROOT uniquement

Réutiliser le harness ASR existant, --prepared --corpus backend/test/fixtures/memora/accuracy-corpus.v2.json --split holdout --cases reserve-fr-budget reserve-mixed-infra --profiles clean --language native, --adapter-path et --model-path correspondant **au candidat décidé avant run**. --run et label distinct `chain-selected-v1`. Choisir runtimebackend oulab adapté ; Parakeet exige envHF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1. Pas de lancement pendant autreGPU.

Ne pas reconstruire les audios/voix ni changer les attentes après résultats. Conserver provenance/hashes/segments complets + runtimeASR. Si ASR manque un fait, **ne pas le remettre dans les segments envoyés au rapport**.

Puis deux appels réels `backend.api.memora.ai.report` (import habituel via environnement backend configuré) sur les deux listes de segments réellement reconnues, langue de rapportfr, modèleGemma retenu et timeout réel. Sauver sortieJSON entière, modèle/promptversion/temps/sources. Ce sont les deux cas boutenbout demandés, sans mocks. Ne pas importer modèle ASR lab dans le même processus LLM ; déchargerASR avant Gemma.

Option diagnostic utile si un rapport échoue : deux appels supplémentaires sur `reference_analysis_segment` figé. Ce segment couvre volontairement **tout l’audio**, durée réelle vérifiée : pas de fauxhorodatages phrase/mot. Sources alors seulements1. Distinguer ces rapports sourceparfaite des rapports ASR, ne pas les mélanger pour annoncer réussite boutenbout. Cette option ajoute2inférences à réserver séparément.

## Mesures séparées

- Transcription : WER/CER stricts et normalisésnumériques du harness, puis contrôle humain indépendant de chacun des6faits/contraintes de fixture. Montants, négations, personnes, temporalité et langues. Pas un simple score lexical : « ne…pas » à mauvaiseplace ne valide pas négation.
- Rapport fidèle à sa source : présence correcte des actions, responsables/échéances établis, négations/modalités préservées, aucune assertion inventée ; chaque sourceID existe dans les segments ASR fournis et son passage permet de retrouver l’affirmation. Pas besoin catégorieexac tepourcontraintes si senspréservé ; actionsnommées doivent rester actions à suivre. Échéance inconnue doit rester inconnue.
- Boutenbout : factsaccurate / facts6, assertionsfaussesetcontreaffirmations interdites, couvertureactions2, attributionresponsables2, échéanceNadiaexacte1/absenceéchéanceInès1, citationsvalides. Toutfait absentASR doit être qualifié perteASR ; toutfait présentASR déforméparrapport = erreurLLM ; l’invention peut avoir lesdeuxsources, à revoir sanscorrectionoracle.
- LatenceASR/rapport séparées, modèles/révisions/config/hashes, nombresegments et éventuelletroncature. Pas de moyenne entre baselineperfectsource et pipelineASR.

Preuve préparatoire : JSON parsé, 2références identiques aux chunks figés, SHA audios/corpus conformes. Aucun test IA exécuté ici. Aucune éditionai.py ou testsAI ; uniquement fixture/préparation de validation.
