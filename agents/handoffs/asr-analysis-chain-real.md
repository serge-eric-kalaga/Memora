# Chaîne réelle sur les deux cas figés

Deux cas exécutés sans DB ni configuration principale, modèles réels locaux : ai.transcribe factory→ai.report Gemma4:e4b. Politique simulée par env du seul processus : principal/liveTurbo, expliciteFRfinalParakeet. Aucun segment corrigé à partir de référence, aucun mock IA, aucun diagnostic parfait supplémentaire.

Snapshot ai.py lu et compilé une fois, SHA194e05163c84d0be5430208dded1bdd1e93b78ab16325dbaf67dbc8f33bd984e, conservé agents/logs/chain-ai-loaded.py. Disqueai.py a changé ensuite pendant éditionQAautorisée ; les deux appels utilisent bien le même module chargé, pas les changements tardifs. Hashesadapters/manifests/audios/fixture/config/digestGemma dans asr-analysis-chain-real.json. L'initialiseur api appelait settingssecrets/DB au premier essai avantGPU ; namespacepackage local __path__ vers vraisfichiers utilisé pour isoler ces initialiseurs, codefactory/modèles/Gemma réels conservés.

| Cas | ASR | LatenceASR | WERstrict | WERnumérique | RapportGemma |
| --- | --- | --- | --- | --- | --- |
| reserve-fr-budget clean | Parakeet | 3.529s |18.52% (nombresécrits→chiffres) |0% |15.398s |
| reserve-mixed-infra clean | Turbo |3.297s |0% |0% |11.024s |

Revue sémantique séparée : ASR conserve6/6faits centraux, rapportsconservent6/6faits centraux, responsablesactionsNadia/Inès2/2, échéanceNadiamercredimatin et absenceéchéanceInès2/2. 1600EUR≠16000 conservé ; pasdepaiementaujourd’hui ; accordPythonenattente ; pasderestartavantvendredi (pasdepromesserestartvendredi). CitationsIDsvalides et sources relues pourles2cas, repèresaudio dessegments réels. Attributionvoixresteinconnue. Parakeetlanguageunknown, confianceNone/uncertainTrue conservateur ; TurboFR/ENregiondetectionconservé.

**Réserve de formulation** : résuméFR commence « Il a été décidé que… » alors que source est la déclaration collective « nous ne réglons pas … aujourd’hui », sans délibération/accord explicitement décrits. Le fait négatif opérationnel n'est pas inversé et aucunpaiementpositif n'est inventé, mais statutdélibératif est plusfort ; ne pas déclarer qualificationdecisionstrictementparfaite. Casbilingueclassecorrectement décisionsvides, actionInès, attenteaccord et bornevendredi.

Sorties et revue : agents/logs/asr-analysis-chain-real.json, asr-analysis-chain-real.review.json et .log. GPUlibéré immédiatementaprès2chaînes ; aucune autoinférence/réanalysepersonnelle/mainconfig/restart. DeuxcasTTS courtsclean seulement : ne prouvent ni2h/naturel/bruit ni politiqueFRglobale. Revucontre attentesfigées AVANT sortiesParakeetv2, aucune sélection surscore.
