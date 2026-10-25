# Chat conversationnel isolé par droits

Fichiers produits : backend/api/memora/routes.py et ai.py. Nouveau test dédié test_memora_conversation.py ; script synthétique scripts/memora-qa-conversation.py. Pas migration, worker/provider/UI/main/service modifié.

## Contrat

POST /meetings/{mid}/chat conserve body{question}. Retour ajoute `id`, `created` epochsecondes, `context_scope` (transcript ou report:<id>), `history_omitted`. Champs existants answer/sources/question/version conservés. GET réunion conserve tableauchat mais filtre actor ETscopeaccessible ; anciennesversions même scope peuvent rester visibles UI, ne rentrent jamais dans contexteLLM. Anciens chats sanscontext_scope visibles propriétaire uniquement, jamais réinjectés ; invités ne reçoivent pas ceslegacy au scope indéterminé.

actor existant : propriétaire user:id, invité SHA(token+guest_session). Headerguest_session valide requis pour reprendre la même conversation ; sinon nouvelactoréphémère, aucun historique partagé implicite. Autorisation réunion/incarnationownerUID toujours vérifiée par access. Contexte : même meeting/actor/version/scope ; sixderniers échanges maximum et6000caractèresJSON, tours entiers jamais coupés ; nombre omis explicite. SQL ne charge que sixderniers tours. Rapportseul doit correspondre versioncourante, et regénérationmêmeversion change reportscope donc aucun ancienrésultat/ancienchat réutilisé.

ai.answer accepte quatrième paramètre optionnelhistory (troisparamètres toujours compatibles). Historique explicitement donnéesnonfiables, ancienanswer jamais preuve, pronoms résolus à partir de cette conversation mais faits réétablis transcriptioncourante. AucunrewriteLLMtranscription. Touslots sources actuels restent traités sans troncature silencieuse. Sortie citations filtrée à IDs autorisés actuels ; reportonly n'expose pasIDssource. Freshaccess après inférence puis share_access sous writerlock empêche publication après révocation/expiration/changementdroits/version/reportid. Pas extension des droits invités.

## Validation

Preuve Gemma4:e4b réelle : troisquestions synthétiques figées avant inférence, source Alice dossierSaphirvendredi et Bobdémonstrationmardi, budgetexplicitementnonétabli. Alice[s1]3,378s ; « Et son échéance ? » vendredi[s1]3,715s (pas mardi) ; budgetnonétabli[s3]3,382s. Preuves conversation-real.json/log. Pas donnéespersonnelles ni ASR/audio. GPU libéré ROOTprévenu. Artefact observé : modèle répète `sources:["u1"]` dans prose ; correctif borné supprimeuniquementtrailerJSONfinal contenantIDsunitésvalides, citationsstructurées restent remappées. Ce nettoyage testé isolément après inférence, pas encore nouvelappelréel sur codefinal.

Première vérificationharness interdisait toutchiffre, donc rejetait aussi u3 ; remplacée par contrôle montantdevise et logspertour pour éviterpertepreuve. Premierfull313PASS/1échectest malparamétré(sharepermissions au mauvaisniveau), corrigé puis testsconversationPASS. Root relancefullfinal après libération fichiers. Logsconversation-tests.log contient résultatcibléfinal.

Suite globale finaleROOT :315PASS/3RedisSKIP/1warning23,00s. Ruff et format des quatre fichiers modifiésPASS ; OpenAPI et SDK inchangés vérifiés.
