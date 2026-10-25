# Benchmark ASR supplémentaire — préparation figée

25 octobre 2026. Aucune inférence exécutée pendant cette préparation. Aucun microphone, audio personnel, réseau, modification backend ou service principal. Synthèse locale `say` avec voix déjà disponibles ; permission native nécessaire car le sandbox produisait des AIFF vides (détection ajoutée).

## Corpus

Source versionnable : `backend/test/fixtures/memora/accuracy-corpus.v1.json`.
SHA256 figé avant première sortie ASR : `91f026d6202af48894e4b11b3e3a4deadc4b436fe709f6ff9bd8346fe070be1b`.
18 énoncés :8 tuning,8 holdout,2 contre-exemples lexique tuning. Thomas/Samantha côté tuning ; Amélie/Jacques/Daniel/Karen côté holdout, textes distincts. Les voix macOS ne représentent pas toutes les voix naturelles ni les accents d'Afrique francophone.

6 conditions par source : propre, bruit gaussien stationnaire SNR20/10dB, échos FIR synthétiques, Opus32kbit/s, amplitude -24dB. Deux négatifs silence/bruit avec glossaire absent. 110 fichiers,693,95s acoustiques cumulées ; répétitions acoustiques non indépendantes. Nombres contrastés2400/24000 et3500/35000, négations/corrections, homophones, noms, phrases courtes pauses400ms, code-switch pauses300ms et0ms. Contre-exemples Khadija/mémoire face glossaire Kadiatou/Memora, Catherine face Kathleen.

Audios et manifeste dérivé ignorés Git : `.memora/accuracy-benchmark/v1/`. Le manifeste conserve SHA par audio, durée et références. Le bruit utilise une graine fixe, SNR relatif aux échantillons |x|>0.01 ; les échos ne prétendent pas reproduire une vraie salle. Voix faible simulée par gain, pas un vrai chuchotement. Les pauses insérées ne suppriment pas les pauses naturelles de TTS. Les profils/cas ne réécrivent jamais les références.

## Commandes

Préparer uniquement (défaut, aucune importation MLX/inférence) :
`backend/.venv/bin/python scripts/memora-benchmark-accuracy.py`

Après autorisation de sérialisation GPU par ROOT :
`backend/.venv/bin/python scripts/memora-benchmark-accuracy.py --run --label turbo-baseline-auto --split tuning --profiles clean --language auto --variant baseline`

Comparaison contexte à paramètres identiques : baseline puis context avec `--language native` (fr/en mono forcés ; mixte auto inchangé). Ne pas comparer baseline auto à contexte native comme si seul le contexte changeait.

`--variant baseline|context|vocabulary|context-vocabulary`, `--cases source-id ...`, `--profiles clean noise20 noise10 reverb opus32 quiet24`, `--split tuning|holdout|all`, `--model-path PATH`, `--adapter-path PATH`.
Adapter par défaut snapshot `agents/logs/asr-baseline-20261025.py`, SHA enregistré dans chaque sortie. Modèle par défaut turbo ; manifeste provenance/revision/taille et SHA complet exigés avant inférence, safetensors ou npz, whitelist turbo/large-v3-mlx. Aucun téléchargement implicite, mode HF offline.

Contexte expérimental : regrouper régions consécutives seulement en langue forcée fr/en, gap≤1s et span≤25s ; auto inchangé. Vocabulaire : `initial_prompt='Terms: '+noms explicites du manifeste`, jamais phrases de référence/négations/nombres. Monkeypatchs dans le processus du benchmark uniquement, aucun changement production.

## Mesures et limites

WER et CER stricts NFC/casse/ponctuation normalisées, accents conservés ; S/D/I et dénominateurs explicites. Mesures numériques séparées : dictionnaire auditable dans le script + séparateurs milliers ;2400 reste différent de24000. Pas de correction silencieuse des noms. Résultats par cas et agrégats micro **split:condition**, évitant de mélanger holdout/tuning ou traiter les perturbations comme nouveaux locuteurs indépendants. Contrôles lexicaux ordonnés (écart≤12tokens), fausses insertions de glossaire et hallucinations négatives séparées. Ils ne valident pas toute la sémantique d'une négation.

Objectif opérationnel proposé : WER numérique holdout propre≤10%, soit1-WER≥90%, avec inspection séparée des erreurs critiques et dégradations par groupe. Ce seuil n'est ni une garantie sur réunion naturelle, ni une validation de diarisation ou de l'analyse LLM. Le holdout est figé ; ne pas modifier les références ou choisir les paramètres à partir de ses erreurs puis annoncer un holdout indépendant. Une nouvelle itération informée par ce holdout nécessite un nouveau corpus de validation.

Vérifications obtenues : Ruff check/format PASS ; auto-tests métriques PASS (S/D/I, accents,2400≠24000, négation absente) ;110SHA audio vérifiés, WAV16kHz non vides ; première et seconde préparation sans inférence. Log `agents/logs/accuracy-prepare.log`. Les caches et logs restent ignorés Git. Résultats ASR encore **non mesurés** pour ce nouveau corpus.

## Première comparaison réelle tuning (terminée)

GPU réservé par ROOT puis rendu après248cas (4×62),155,544s d'inférence cumulée. Aucun holdout transcrit. Adapter figé turbo, langue native (FR/EN forcés, mixte auto), tous six profils. Fichiers `agents/logs/accuracy-{baseline,context,vocabulary,context-vocabulary}-native-tuning.{json,log}`, comparaison `accuracy-tuning-comparison.json`.

Normaliseur **v2-currency-and-canonical-probes-all-occurrences** : cent→100 ; symboles $/€/£ conservent dollars/euros/pounds avant suppression de ponctuation ; probes passent par le même normaliseur et cherchent toutes les occurrences possibles d'un terme répété. Auto-tests montant2400≠24000, dollar≠euro, accents, négation absente, secondnot valide PASS. Strict inchangé, références/corpus inchangés. Baseline/contexte/vocab première métrique conservée en `.metric-v1.json`, rescoring uniquement textuel sans nouvelle inférence via `--rescore`. Baseline propre numérique était3,85%, devient2,56% après équivalences de format ; critique16/20 devient18/20 après canonicalisation et correction de recherche répétée. Les deux derniers échecs lexicaux propres sont signature/signatures et Khadija/Kadija, pas deux pertes de négation.

| Variante | Propre | Bruit20 | Bruit10 | Opus32 | Faible24 | Échos | Fausses insertions glossaire |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline |2,56%|10,26%|12,18%|7,05%|7,69%|2,56%|0|
| contexte |2,56%|10,26%|12,18%|7,05%|7,05%|2,56%|0|
| vocabulaire |5,77%|5,77%|12,18%|9,62%|10,26%|5,77%|6|
| contexte+vocabulaire |5,77%|5,77%|12,18%|9,62%|9,62%|5,77%|6|

WER numérique micro par strate tuning uniquement (156tokens propres après normalisation). WER strict propre baseline13,25%, inchangé par rescoring. Modèle a notamment produit maire pour mer, Kadija pour Khadija et Zephyr pour Zéphyr. Tous les huit contrôles négatifs (2×4 variantes) sans texte, y compris glossaire absent.

**Régression observée, pas masquée :** vocabulaireKadiatou remplace Khadija prononcé dans les six conditions ; à l'inverse baseline écrit Kadija. PromptPython sur mixed-continuous propre supprime toute la phrase française et garde seulement «We will not deploy before Monday.» dans vocab et combinaison. Un gain bruit20 ne compense pas ces régressions sémantiques. Ne pas activer le lexique global. Contexte seul ne change presque rien sur ce corpus ; aucun motif suffisant de modification production sur cette seule preuve.

Les références demeurent figées, aucune optimisation sur holdout. Les repliages de température MLX existants peuvent introduire une variabilité : graine acoustique fixe, aucune nouvelle graine d'inférence imposée afin de conserver les options de baseline. Prévoir répétitions contrôlées pour attribuer un faible gain d'un token. Aucun résultat naturel revendiqué, pas de seuil90% déclaré globalement atteint.

Préparation grande variante : le runner enregistre désormais mémoire physique, RSS maximum du processus (Darwin bytes, Linux converti), pic allocations MLX lorsqu'il est chargé, et compteurs vm_stat avant/après chaque cas. Somme free+inactive+speculative exposée comme **proxy**, pas une garantie de mémoire libre. `--max-rss-gib` défaut12 arrête entre deux cas si le high-water du processus dépasse12GiB, conserve les sorties partielles ; ce n'est pas une limite mémoire matérielle ni une protection pendant une inférence unique. Mesure locale à vide :16GiB physiques, proxy≈7,8GiB disponible avant grandmodèle. Aucun grandmodèle chargé pour cette préparation. Attente ROOT pour SHA et libération GPU ; holdout toujours intact.

Variantes supplémentaires préparées, sans inférence : `--variant temperature-zero` remplace uniquement temperature par0.0 ; `--variant best-of-five` ajoute uniquement best_of5, conserve repli0/0.2/0.4. Code MLX installé `mlx_whisper/transcribe.py:204-224` lu : retire best_of lorsque température0 ; sampling utilise best_of aux températures positives. Vérification locale wrapper factice (aucune IA simulée pour annoncer une fonction livrée) confirme paramètres transmis et autres options inchangées, Ruff/self-tests PASS. Attente ROOT GPU avant essai réel.

## Décodage low-cost supplémentaire —124cas terminés

GPU rendu après deux séries supplémentaires62tuning chacune, même corpus/options/profils/native/Turbo snapshot. **Aucune des124hypothèses ne diffère de la baseline** (comparaison texte exact). Températurezéro41,804s, best_of5=42,332s d'inférence cumulée ; aucune fausse insertion glossaire et silence/bruit sans texte. Tous profils WER/critical identiques baseline. Propre par langue : FR4/84erreurs=4,76%, EN0/44, bilingueauto0/28. Le détail de toutes les langues/profils, S/D/I/CER et critiques figure dans `agents/logs/accuracy-tuning-comparison.json` (six variantes372cas cumulés). Pas d'amélioration démontrée par ces réglages ; ne pas les intégrer pour revendiquer un gain.

Pics mémoire mesurés sur ces deux runs : température0 RSS2,226GiB/allocationsMLX2,036GiB ; best_of5 RSS2,154GiB (allocationsMLX détailléesJSON). Anciennes quatre variantes non instrumentées : mémoireNULL, pas0. Les appels n'ont jamais atteint la limite12GiB. Grandmodèle/holdout toujours non lancés. Logs et JSON `accuracy-{temperature-zero,best-of-five}-native-tuning.*` conservés. Aucune modification production.

## Large-v3 complet —62cas tuning terminés

Modèle `.memora/models/mlx-large-v3` vérifié SHA avant inférence, même adapter figé baseline/langue native/options/corpus/six profils.100,984s cumulés contre42,080s Turbo (~2,40×). Pics RSS3,701GiB / allocationsMLX3,404GiB ; garde12GiB jamais atteinte. Deux négatifs sans texte. Aucune donnée privée consultée ou utilisée. Holdout toujours intact, GPU rendu.

| Modèle | Propre | Bruit20 | Bruit10 | Opus32 | Faible24 | Échos |
|---|---:|---:|---:|---:|---:|---:|
| large-v3 |10,26%|10,90%|12,82%|10,26%|10,90%|10,90%|
| Turbo baseline |2,56%|10,26%|12,18%|7,05%|7,69%|2,56%|

Propre par langue : FR3/84=3,57% (Turbo4/84=4,76%), EN0/44 identique, bilingueauto13/28=46,43% (Turbo0/28). Critiques propres17/20 contre18/20. WER strict propre20,48% contre13,25%. L'amélioration française propre représente seulement un token ; ne pas extrapoler une supériorité générale.

Régressions directement inspectées dans les sorties synthétiques : `mixed-pause-clean` traduit «The budget has not been approved» en «Le budget n'a pas été approuvé» et Aïcha devient Aisha ; `mixed-continuous-clean` traduit «We will not deploy before Monday» en «Nous ne déploierons pas avant dimanche.» malgrétasktranscribe. Ce dernier cas altère aussi l'échéance. Grandmodèle global déconseillé sur cette preuve ; aucune intégration production. Le résultat ne prouve pas qu'une stratégie de routage serait validée : elle nécessiterait son propre choix/préenregistrement et holdout.

Preuves conservées `agents/logs/accuracy-large-v3-baseline-native-tuning.{json,log}`, comparaison enrichie sept variantes434cas `accuracy-tuning-comparison.json` (langue/profil/WER/CER/S-D-I/criticals/RAM). Le corpus SHA et références restent inchangés. Aucun holdout n'a servi au choix.

## Décision préenregistrée avant holdout

ROOT choisit après tuning, **avant toute inférence holdout**, la politique : français explicitement sélectionné en transcription finale→large-v3 ; auto/bilingue/anglais→Turbo ; live→Turbo. Pas de nouveau contexte ni vocabulaire. Large-v3 global rejeté. Le gain FR tuning propre d'un token ne suffit pas à promettre un gain général ; le holdout peut invalider la route.

Benchmark prêt `--fr-model-path .memora/models/mlx-large-v3` : SHA complet des deux modèles avant première inférence ; sélection casfr uniquement avant appel, base Turbo pour EN/auto/négatifs ; chemin/SHA réellement choisis enregistrés par cas. Le snapshot reste figé pour isoler la variable modèle. `MEMORA_MLX_FR_MODEL_PATH` défini explicitement (vide pour contrôle baseline), empêchant un héritage accidentel d'une route depuis l'environnement. CLI/self-tests/Ruff PASS. Holdout attendu50cas (8×6+2négatifs), comparé Turbo puis route avec options identiques ; attente signal ROOT avant GPU. Aucun holdout exécuté à ce point.

## Première validation holdout —100cas terminés, politique inchangée

Après signal ROOT, Turbo snapshot puis route FR préenregistrée exécutés séquentiellement sur les8sources holdout intactes×6conditions+2négatifs=50cas chacun. Route utilise **adapter production actuel** `backend/api/memora/asr_mlx.py` et deux modèles SHA vérifiés. Les24casFR choisissent large-v3, les24cas EN/auto et2négatifs Turbo ; chemins/SHA effectifs enregistrés. Aucune hypothèse EN/auto ne diffère entre les deux exécutions. Références/SHA/options non modifiés après découverte des résultats. Aucun contenu privé inspecté ni conservé.

| WER numérique holdout | Turbo | Route FRlarge-v3/autresTurbo |
|---|---:|---:|
| Propre |15,44% (21/136)|9,56% (13/136)|
| Bruit20 |19,85%|19,12%|
| Bruit10 |25,74%|33,09%|
| Opus32 |13,97%|14,71%|
| Faible24 |12,50%|11,03%|
| Échos |13,24%|15,44%|

Propre : FR15/72→7/72erreurs (20,83→9,72%), EN1/36 (2,78%) inchangé, mixte5/28 (17,86%) inchangé. WER strict propre26,03→20,55% ; critiques15/17→16/17. Détail complet langues×profils/WER/CER/S/D/I dans `agents/logs/accuracy-holdout-comparison.json`. Route68,423s d'inférence cumulée contre46,410s (~1,47×) ; pics RSS3,568/2,122GiB, MLX3,404/2,039GiB. Quatre contrôles négatifs sans hallucination. Aucune limite RSS atteinte ; GPU rendu, processus de benchmark terminés.

**Conclusion bornée :** la politique choisie avant holdout franchit de peu le seuil opérationnel préannoncé *propre numérique* (1-WER=90,44%). Ce n'est pas90% général : strict79,45%, bilingue82,14%, bruit20≈80,88%, bruit10≈66,91%. Taille propre136tokens/8énoncés synthétiques et voixTTS, aucune garantie sur réunion naturelle. Les perturbations d'une source ne constituent pas de nouveaux locuteurs indépendants. Le holdout est désormais consommé ; tout nouveau réglage inspiré par ses erreurs doit être validé sur de nouvelles sources.

**Erreurs encore concrètes :** noms Mariama fragmentés/changés, Redis→Rodi ; homophone comte→compte. La route retrouve Fatou/Koudougou dans le cas technique propre et conserve «ne doit pas signer» auparavant altéré par Turbo. En bruit10, la sourceJacques contexte court passe de8/17erreurs Turbo à18/17 (105,88%) avec phrases déformées ; cette régression est conservée, jamais supprimée de la moyenne. Aucun choix modèle par source après holdout. La route n'est pas une preuve d'amélioration sous bruit/réverbération/compression.

Preuves : `agents/logs/accuracy-{turbo,routed-fr-large-v3}-native-holdout.{json,log}`, comparaison distincte `accuracy-holdout-comparison.json`. Tests métriques/Ruff déjà PASS ; modèle/adapter/hash/cas et mesures mémoire dans JSON. Services principaux jamais arrêtés/modifiés par ces benchmarks ; caches audios synthétiques restent sous `.memora/accuracy-benchmark/v1/` ignoréGit. Root décide de la livraison et de sa communication ; aucune nouvelle modification production réalisée par cet agent.

## Reproduction depuis un checkout propre

Après les mesures historiques, ROOT a changé le défautCLI `--adapter-path` vers le fichier versionné `backend/api/memora/asr_mlx.py`, afin de ne pas dépendre d'un log ignoré. Aucun résultat historique n'a été recalculé ou réétiqueté. Pour reproduire exactement ces anciens essais, fournir explicitement `--adapter-path agents/logs/asr-baseline-20261025.py` et conserver cet artefact/SHA ; il reste local ignoré. Pour un nouveau benchmark du code livré, utiliser l'adaptateur versionné courant et son SHA enregistré, sans le présenter comme le snapshot historique. Les audios sont synthétisés par les scripts/version de voix de la machine ; `--prepared` exige le cache/SHA préservé.
