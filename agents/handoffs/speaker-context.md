# Contexte IA : noms corrigés, horodatages, frontières et provenance

## Code intégré (périmètre borné)

`backend/api/memora/ai.py` et `backend/test/test_memora_ai.py` uniquement côté application/tests existants. Nouveau script de preuve `scripts/memora-qa-speaker-context.py`. Aucun audio ou source utilisateur lu ; corpus entièrement synthétiques définis dans le script.

- `reading_units` conserve speaker/start/end originaux, sans créer de repères manquants (None). Les textes originaux et données persistées ne changent pas.
- Jointures de jour isolé conservatrices conservées. `speaker_parts` existe UNIQUEMENT sur unités jointes, avec texte exact de chaque fragment, locuteur, temps et offsets ; top-level speaker=None si locuteurs différents. La duplication de texte reste limitée aux rares jointures pour que le modèle n'ait pas à compter les caractères.
- `source_context` transmet métadonnées utiles mais retire IDs originaux du payload modèle pour éviter confusion avec IDs temporaires de citation.
- Construction des unités AVANT leur mise en lots : phrase + vendredi restent atomiques même près d'une frontière. IDs unitaires globaux stables. `report_prompt(..., units=...)` ne reconstruit ni ne réindexe les unités ; exemple de citation adapté au premier ID du lot.
- Rapport et chat utilisent le même contexte canonique, instructions première personne/speaker nommé, contraintes enum uIDs, puis expansion déterministe vers références originales. La réduction du chat conserve les IDs originaux, sans nouveau remap ni accès à d'autres sources.
- `ProcessingError`, avertissements d'incertitude et fallback anglais préservés.

Diagnostic réel initial : le modèle donnait déjà ownerAlice/deadlinevendredi mais ne produisait que actions, résumé vide ; ProcessingError a refusé la publication. Correction bornée complémentaire : schéma Report exige les cinq catégories, summary minItems1, citations enum inchangées. Pas de synthèse simulée ni de résumé inventé côté application ; garde-fou d'erreur reste actif pour réponse non conforme.

## Tests exécutés

`cd backend && .venv/bin/python -m pytest test/test_memora_ai.py -q` : **14 réussis, 0,33s**. Ruff format/check réussis. Tests ajoutés : métadonnées conservées, fragments à speakers différents, texte par part uniquement pour jointures, repères absents non inventés, frontière de lots, IDs globaux/prebuilt units, citations originales rejetées si devinées, expansion après chat et conservation lors de réduction, schéma résumé obligatoire.

`backend/.venv/bin/python scripts/memora-qa-speaker-context.py` : vrais appels qwen3.5:4b, trois corpus PASS.

| Cas synthétique | Rapport réel | Chat réel | Temps rapport / chat |
|---|---|---|---|
| Alice : « Je préparerai la démonstration vendredi. » | ownerAlice, vendredi, source s1 | Alice + vendredi, s1 | 9,164s / 3,550s |
| Alice : phrase inachevée puis Alice « vendredi. » | ownerAlice, vendredi, s1+s2 | Alice + vendredi, s1+s2 | 9,311s / 3,849s |
| Alice prépare sans date ; Bob donne vendredi pour SA réunion marketing | Alice deadlineNonprécisée, s1 ; Bob vendredi, s2 | « Alice s'engage à préparer la démonstration. L'échéance n'est pas établie dans les sources fournies. », s1 | 10,190s / 4,105s |

Toutes les sources des cinq catégories non vides et appartenant au corpus ; pas de démonstration classée comme décision dans les trois cas (decisions=[]). Preuves locales `agents/logs/speaker-context-qa.json`, `.log` et `speaker-context-generations.json` (sorties brutes exclusivement synthétiques, non versionnées).

Régression réelle des anciens trois corpus via `scripts/memora-qa-report-fragments.py --integrated` en cours au moment de cette note ; normal et adjacent déjà PASS. Journal séparé `agents/logs/report-fragments-metadata-regression.log`.

## Limites observées

- Le modèle peut résumer « Je préparerai » par « Alice a décidé de préparer », même si decisions=[] ; ce choix de formulation ne prouve pas une approbation explicite. L'état « budget ouvert » a parfois aussi été ajouté à actions. Qualité sémantique parfaite non revendiquée.
- Le warning historique sur absence d'attribution automatique reste inchangé comme demandé ; sa formulation générique « intervenants non identifiés » mérite adaptation lorsqu'un utilisateur a corrigé des noms.
- Unité à locuteurs différents : métadonnées distinctes prouvées par tests isolés ; aucune preuve réelle de tous dialogues ambigus possible. La règle demande de ne pas convertir une proposition de date d'un autre locuteur en échéance approuvée.
- Pas de modification du worker, des versions, des permissions ou des transcriptions persistées. Un redémarrage du backend et une régénération volontaire restent nécessaires pour appliquer le nouveau prompt aux rapports existants ; le chat reçoit le contexte courant sans cache d'unités.

## Révalidation finale après renforcement sémantique demandé

Consigne ajoutée au contexte partagé rapport/chat : interdiction de transformer « Je préparerai » en approbation s'applique aussi à summary/topics/chat, pas seulement à decisions. Aucun filtre lexical de production ni post-traitement simulé. Un premier renforcement avait régressé le chat négatif (vendrediBob attribuéAlice) : assertion réelle l'a détecté. Contrôle final ajouté au prompt chat contre assemblage de personne/action/date sans relation explicite, avec contre-exemple pédagogique Mina/Zoé distinct des sources testées.

Dernier run réel `scripts/memora-qa-speaker-context.py` : **trois cas PASS** ; ni résumés, sujets, actions, décisions ni chat ne contiennent la reformulation « a décidé » dans ces cas. Premier cas9,736s/3,688s ; fragment9,374s/4,169s ; date d'un autre locuteur10,094s/4,065s. Dernier chat négatif exact : « Alice préparera la démonstration ; l'échéance n'est pas établie. », sources s1+s2 (autorisées ; s2 explique le contexte de la date écartée).

Régression finale réelle des trois anciens corpus : **normal PASS13,75s, adjacent PASS13,37s, unrelated PASS15,48s**. Ancien couple phrase/vendredi conservé sans régression constatée. Journal `agents/logs/report-fragments-metadata-regression.log` ; rapports complets `agents/logs/report-fragments.json`.

14 tests isolés et Ruff passent ; dernière commande pytest0,33s. Les limites générales restent valides : ces corpus ne prouvent pas toutes les paraphrases ; étatbudget reste parfois aussi rangé en actions dans le premier cas (fragment propre). Warning d'attribution générique inchangé. Cette correction est validée pour les relations de locuteurs/dates explicitement exercées, pas une garantie de perfection sémantique universelle.

Comparaison unique Gemma documentée séparément dans `agents/handoffs/gemma-report-comparison.md`. Après fin des probes, ai.py et tests ont été libérés à l'intégrateur pour ses changements ultérieurs (refus d'overflow de contexte) ; aucune modification par cette tâche après cette libération.

## Refus explicite de troncature/context shift

`generate` transmet désormais **truncate=false et shift=false au premier niveau de /api/chat**, conformément au probe réel et à la confirmation de l'intégrateur (pas sous options). Modèles, température, contexte configuré et provenance inchangés.

Preuve réelle fournie par intégrateur, relue dans `agents/logs/context-overflow-probe.json` : requête synthétique12016tokens, contexte2048tokens, réponse HTTP400 après1,86s : dépassement explicite, sans compteur de prompt évalué. Ce probe constitue la preuve serveur ; les nouveaux tests ci-dessous sont isolés HTTPMockTransport, pas une deuxième inférence.

Un HTTP400 portant l'erreur officielle de dépassement est converti en ProcessingError au message fixe : contexte local insuffisant et traitement interrompu pour éviter une troncature silencieuse ; adapter découpage/capacité avant relance. Ni corps serveur, ni source, ni valeurs du prompt ne sont interpolés. Autres erreurs HTTP conservent leur chemin habituel.

Tests ajoutés : capture du vrai payload sérialisé (deux booléens top-level + enum sources conservée), refus overflow et absence d'un marqueur synthétique privé dans le message exposable. **16 testsAI réussis en0,42s**, Ruff format/check réussis. Aucune nouvelle inférence ou modification de modèle pour ce patch. ai.py et test_memora_ai.py libérés à l'intégrateur après validation.
