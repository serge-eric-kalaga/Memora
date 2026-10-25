# Diagnostic borné : Parakeet et français explicite

Aucune lecture d'audio personnel, aucun microphone, aucune modification ai.py/adapters/configuration/services. Audit code installé et sources primaires, puis12inférences GPU séquentielles autorisées sur corpusTTS exclusivement synthétique. GPU libéré après fin.

## Cause structurelle vérifiée, symptôme non reproduit

Le [modèle NVIDIA ParakeetTDTv3 officiel](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) est multilingue25langues et détecte automatiquement la langue, sans prompting additionnel. Ce n'est pas v2anglaisuniquement. La [conversionMLX épinglée](https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3/blob/ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15/README.md) confirme base_modelv3, FRsupporté et CC-BY4.0. L'adapter existant vérifie poids et assets complets SHA avant chargement, pas téléchargement ou remplacement silencieux.

`backend/api/memora/asr_parakeet.py` accepte language=fr pour compatibilité d'interface mais ne force pas le décodage. L'implémentation installée mlx_audio0.6.1, fichier `stt/models/parakeet/parakeet.py`, expose generate(audio,dtype,chunk_duration,overlap_duration,...) et TDTgreedy, sans sélecteur de langue dans decode_chunk. En mode nonstream, kwargsautres que verbose/max_tokens/generation_stream ne sont pas transmis à un décodeurconditionné. Ajouter simplement language='fr' à cet appel ne constituerait donc pas une contrainte réellement appliquée. Aucun patch n'a été fait.

Son `StreamingResult.language='en'` est une valeur par défaut/constante de sortie du package, pas une preuve que le modèle est anglaisuniquement. L'adapter Memora n'utilise pas cette fausse détection : il indique unknown avec confianceNone et uncertainTrue. Changer le badge ne change pas les mots reconnus.

**Conclusion** : choix français + routeParakeet ne garantit pas transcription contrainte en français. Cela explique une possibilité de dérive de langue, mais ne démontre pas la cause acoustique exacte du symptôme signalé. Ce symptôme personnel n'a pas été reproduit ici ; aucun audio privé n'a été inspecté pour prétendre le contraire.

## Comparaison réelle synthétique

Corpus figé `backend/test/fixtures/memora/asr-language-drift-v1.json`, voixThomas française. Trois passages courts sur termeshost/co-host, micro, animateur/amateur, contrôlefrançais. Audio90s par répétitions complètes et silencefinal, pour couvrir les fenêtresParakeet30s/overlap2s. GénérationTTS horssandbox autorisée ; garde audio nonvide. Aucun texte de référence transmis aux ASR comme prompt.

Runner `scripts/memora-qa-asr-language-drift.py`, résultats bruts `agents/logs/asr-language-drift-v1.json/log` : référencesettranscriptions synthétiques, timestamps/langues, adapterSHA, nWER etlatence. Modèles existants vérifiés intégralement contre manifests avant inférence, aucun nouveau téléchargement. Chaque moteur déchargé avant le suivant. Les variables de cheminmodèle sont locales au processusprobe, pas configurationapp.

| Moteur | Langue réellement contrainte |4cas nWER |90s latence |Total4cas |
|---|---|---:|---:|---:|
|Parakeetv3|non, détectionauto|0% chacun|1,161s|6,275s|
|Whisperlarge-v3-turbo|fr explicite, tasktranscribe|0% chacun|4,338s|6,869s|
|Whisperlarge-v3 complet|fr explicite, tasktranscribe|0% chacun|11,490s|19,756s|

Aucun basculement/traduction anglais observé. RAM système libre62% après tousles appels (instantané, pas picRSS). nWERnormalisé : UnicodeNFC/casse/ponctuation supprimée, Levenshtein par mots ; aucune normalisation sémantique cachée. Cette petite série TTS claire ne représente pas voixnaturelle/code-switch acoustique humain/bruit de salle. Tous0% ici ne prouvent pas que le cas utilisateur est résolu.

## Proposition à ROOT, sans modification autorisée réalisée

Pour respecter un choixfrançais explicite, router vers un moteur qui expose et applique réellement language='fr', par exemple TurboFR dans cette comparaison. Cela privilégie le contrat linguistique mais **ne garantit ni absence absolue de traduction/hallucination ni meilleure précision sur tous domaines** : anciennes réserves avaient montré un intérêt Parakeet pour chiffres/nomsfrançais, à garder comme preuve comparative.

Parakeet peut rester un choixauto clairement présenté comme noncontraint, ou un mécanisme de repli audio→ASRfr peut être étudié si sortie suspecte. Un détecteur de langue textuelle seul ne prouve pas une traduction : vrais empruntsanglais/code-switch existent. Aucun filtre remplaçant/traduisant les mots générés après coup ne serait une réparation fidèle. Il faut éviter une promesse de français forcé avec un moteur qui ignore cette consigne.

Commandes reproductibles :

```sh
backend/.venv/bin/python scripts/memora-qa-asr-language-drift.py --prepare
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 backend/.venv/bin/python scripts/memora-qa-asr-language-drift.py --run --output agents/logs/asr-language-drift-new.json
```

Ruffscript conforme. Aucun test/mock ne remplace ces résultats. Pas de nouvel étatapplication ni de retranscription d'une réunion utilisateur ; choix de routage/mainenv laissé à ROOT.
