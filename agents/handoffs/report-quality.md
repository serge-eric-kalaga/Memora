# Qualité rapport sur fragments ASR — test réel

Corpus synthétique exact : s1 « Bonjour, nous décidons de lancer le projet Memorale Indie, Alice préparera la démonstration », s2 « vendredi. », s3 budget anglais. Objectif : action Alice échéance vendredi, sources s1+s2 ; décision uniquement lancement explicite. Contre-exemple : date vendredi dans autre phrase marketing après sujet budget, sans attribution à Alice.

Script `scripts/memora-qa-report-fragments.py`, modèle réel qwen3.5:4b ; aucune simulation. Trois premières variantes (règle adjacency, exemple pédagogique Mina/mardi, présentation continue avec IDs) améliorent classification décision/action mais ne remplissent pas vendredi : assertions échouent, aucune modification de ai.py intégrée. Un quatrième candidat règle ponctuation terminale est en cours. Ne pas considérer qualité résolue avant test réussi des DEUX cas.

Prétraitement + remap uIDs autorisé par intégrateur : regroupement strict d'un jour FR/EN seul, adjacent (écart 0–1,5s), précédent sans ponctuation terminale. Les textes et timestamps persistés ne changent pas. Modèle reçoit id u1/u2 explicitement et textes littéraux ; références retournées sont développées via mapping local uniquement. Corpus fragmenté : essai réel 10,62s réussi, Alice vendredi et sources s1+s2 ; aucun travail Alice en décisions. Contre-exemple encore en cours. Ne pas annoncer intégration à ce stade.

## Correctif retenu et intégré

`backend/api/memora/ai.py` uniquement côté métier IA : helpers `reading_units`, `report_prompt`, prompt renforcé et mapping dans `report`. Aucune modification des transcriptions persistées, des timestamps, routes, workers ou états.

Regroupement conservateur : jour de semaine FR/EN seul ; précédent sans ponctuation finale ; timestamps présents et écart 0–1,5s ; ne regroupe pas une interrogation comme « vendredi? », une nouvelle phrase avec sujet, ni une date éloignée. Les unités d'analyse utilisent IDs temporaires u1/u2 ; expansion locale vers IDs originaux uniquement. Référence originale « s1 » inventée par modèle au lieu d'un uID rejetée. Le garde-fou d'erreur si résumé sans source valide demeure.

Candidat réel qwen3.5:4b : normal 10,32s, fragment 11,50s, contre-exemple tous réussis. Les assertions vérifient Alice + échéance + sources exactes, aucun travail démo dans décisions, aucune attribution du vendredi marketing, et toutes les sources de toutes les catégories non vides/autorisées.

Tests isolés : 5 réussis (0,51s), y compris non-mutation des sources, gap trop long, ponctuation, nouveau sujet, interrogation et absence de timestamps, expansion provenance et rejet réindexation s1 non autorisée. Ruff format et check réussis.

Commande réelle intégrée en cours : `backend/.venv/bin/python scripts/memora-qa-report-fragments.py --integrated`, journal `agents/logs/report-fragments-integrated.log`. Normal intégré déjà validé, 23,12s (latence variable si modèles sollicités en parallèle).

Limites : la relecture humaine reste nécessaire ; noms ASR mal reconnus conservés sans invention. Le modèle peut résumer « nous décidons de lancer » par « le projet est lancé » malgré consigne de modalité ; formulation de résumé à vérifier, pas garantie de fidélité parfaite. Regroupement ne couvre volontairement pas toutes expressions temporelles ni fragments à la frontière de lots très longs.

## Résultat intégré final

Commande `--integrated` terminée avec succès : normal, adjacent, unrelated tous PASS. Contre-exemple intégré 12,18s : action Alice `deadline=Non précisée`, source s1 ; vendredi marketing reste dans sa propre source s3, sans fuite de date. Toutes les références des cinq catégories validées. Le backend doit être relancé par intégrateur pour charger le prompt/helper ; anciens rapports ne sont pas remplacés automatiquement.
