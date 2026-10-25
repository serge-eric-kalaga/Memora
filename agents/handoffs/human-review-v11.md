# V11 backend : révisions humaines, noms d'intervenants, requête de séparation

Code intégré : `backend/api/memora/routes.py`, `store.py`, migration `007_human_review.sql`, tests `backend/test/test_memora_human_review.py`. Aucun accès à la base principale, aucun restart, microphone, email ou inférence. ROOT possède le worker et l'intégration frontend. Routes/store gelés après les vérifications ci-dessous.

## Révision humaine du rapport

`GET /api/memora/meetings/{mid}/reports/{rid}/reviews` exige accès au rapport et renvoie :

```json
{"report_id":"rid","report_version":1,"current_transcript_version":1,"stale":false,"items":[],"history":[]}
```

`items` contient le dernier état par `(category,item_index)` ; `history` est append-only. Chaque entrée : `{id,report,category,item_index,revision,transcript_version,author,editor_name,created,status,corrections,provenance:"human_review"}`. `author` est l'acteur serveur, `created` un timestamp epoch ; le nom invité reste déclaratif.

`PUT /api/memora/meetings/{mid}/reports/{rid}/reviews/{category}/{item_index}` : category `actions|decisions`, index zéro-based.

```json
{"transcript_version":1,"expected_revision":0,"status":"confirmed","corrections":{"owner":"","deadline":"avant vendredi"},"editor_name":"Nom déclaré si invité"}
```

Statuts : `proposed|confirmed|cancelled|needs_review`. Réponse : l'entrée ci-dessus, revision incrémentée. Conflit409 si révision concurrente, transcription différente, rapport d'une ancienne version **ou ancien report_id après régénération de même source**.404 pour autre réunion/rapport/index absent.

Corrections : texte ≤3000 caractères, non vide après trim ; owner ≤100 et deadline ≤200, vides permis pour retirer une attribution/échéance inventée. `corrections` omis/null conserve le snapshot précédent ; objet fourni remplace entièrement ce snapshot ; `{}` retire les corrections et revient aux valeurs IA. La sortie `reports.data` n'est jamais modifiée. Chaque rapport de `GET meeting` ajoute `human_reviews` et `reviews_stale` (version OU ID différents). Aucun transfert automatique d'approbation au rapport régénéré.

Invité sans compte : lecture rapport + permission edit + paramètre global d'édition. Une capacité interne `review` distingue ce droit de l'édition de transcription : un lien rapport-seul peut réviser le rapport, mais ne peut pas modifier/analyser/retranscrire sa source cachée. `create_share` accepte edit si rapport OU transcription partagé. Le nom d'éditeur invité est requis ; révocation/politique courante revérifiées sous verrou SQLite avant écriture. Historique et champs corrigés restent des données **humaines**, jamais faussement attribuées à l'IA. Le chat conserve ses sources antérieures autorisées ; aucun overlay humain n'est injecté dans le contexte.

## Renommage global explicite

`POST /api/memora/meetings/{mid}/speakers/rename` :

```json
{"version":1,"from_speaker":"Intervenant non identifié","to_speaker":"Alice","confirm_unidentified":true,"editor_name":"Nom si invité"}
```

Exige edit + transcription, version courante. Nouveau nom non vide ≤100. Source inconnue : confirmation explicite obligatoire, même pour un segment ; ce label peut agréger plusieurs voix. Le backend ne prétend pas identifier automatiquement une personne. Renomme tous les segments dont le label correspond exactement ; nouvelle version, rapport périmé, historiques préservés, repères audio/texte immuables. Réponse `{version,renamed_segments,stale:true,provenance:"human_global_speaker_rename"}`. Même nom : réponse no_change, sans version supplémentaire.409 version périmée.

Les champs source serveur (speaker_id, langue/scope/confiance, candidats, provenance, autres métadonnées) sont préservés par la correction de texte ; seuls text/speaker/uncertain explicitement fournis peuvent changer. Langue et métadonnées client ignorées. Un nom changé reçoit une provenance humaine, speaker_uncertain=false, speaker_confidence=null ; l'ancien group_id reste. Le renommage global suit la même règle. L'ancien modèle/provenance reste consultable dans la version précédente. `GET transcript` ajoute `provenance` pour les éditions globales, stockée séparément dans `transcript_edits`. La correction existante revalide aussi la révocation sous verrou.

## Séparation volontaire : endpoint, worker ROOT

`POST /api/memora/meetings/{mid}/diarize` :

```json
{"version":1,"request_id":"uuid-ou-identifiant-16-a-80","editor_name":"Nom si invité","num_speakers":2}
```

request_id facultatif (généré sinon), caractères alphanumériques/_/-,16–80 ; num_speakers null/omis = auto, sinon1–8. Exige edit/transcription/audio et nom invité. Refuse source périmée409, état autre que ready/failed ou tout job actif409, audio expiré/absent410, transcription absente409, module/modèle indisponible503. Disponibilité via `diarization.available()` sans chargement ni réseau. Même request_id renvoie le même job ; autres version/options pour la requête courante409. Réponse `{job_id,state:"queued",idempotent:false}` ou état existant/idempotenttrue.

Persisté : job kind `diarize` + analysis_requests `diarize_<request_id>` ; `m.diarization_request={job_id,actor,editor_name,num_speakers,requested_version}`, active_job_id et statequeued. Aucun texte privé dans les logs. Le worker ROOT crée la version source et conserve ses checkpoints/historiques ; cette note ne revendique pas une diarisation parfaite.

## Migration, tests et contrat

Migration007 additive et idempotente : `report_reviews` et `transcript_edits`, cascades à la suppression réunion/rapport/transcription. Initialise uniquement via `store.init()`, après sauvegarde et revue ROOT **avant prochain restart principal**. Jamais appliquée à la base principale par cet agent. Réexécution et conservation de données testées en stockage jetable.

- Nouveaux tests + domaine + audit : **57 passed,2,87s** (`agents/logs/human-review-tests.log`).
- `python3 scripts/memora-test.py` : **279 passed,3 skipped Redis,1 warning préexistant,19,74s** (`agents/logs/v11-backend-tests.log`). Inclut les tests worker ajoutés par ROOT.
- Ruff check/format des fichiers modifiés : PASS.
- Export OpenAPI sans init SQL/Redis/SMTP : PASS ; génération SDK locale et checks OpenAPI/SDK : PASS. Logs `v11-openapi*.log`, `v11-sdk*.log`.

Couverts : isolation utilisateur/réunion/rapport, révision concurrente et ancien report_id, append-only/effacement humain, invité rapport-seul/permissions/politique, révocation entre accès et écriture, préservation/spoof des métadonnées, unknown confirmation, timestamps/historiques, contexte chat inchangé, cascade suppression, disponibilité/audio/jobs/idempotence diarize, migration répétée. Les tests du domaine mockent seulement l'IA/disponibilité pour isoler ces contrats ; ils ne constituent pas une recette navigateur, audio ou production. ROOT doit encore intégrer/migrer/tester la version complète en services isolés avant livraison.
