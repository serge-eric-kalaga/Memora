# Test français de 95 secondes : chunks et référence complète

Source : `backend/test/fixtures/memora/accuracy-long-fr.v1.json`.
SHA256 : **20b416c551262d59b978fc9cdf11678288d29e4d73f96b354040b389da333dbe**.
Audio : `.memora/accuracy-benchmark/vlong-fr-1/long-fr-boundaries-clean.wav`.
SHA256 audio : **cf06bcda5e8e7e3c1c6950b7e4ddfb38a39e8d5cfe4c2efe36f61d4b6288ddc4**.

## Préparation figée avant ASR

Synthèse locale Thomas, 170 mots/min ; aucune voix privée, microphone ou GPU pendant la préparation. Audio mono 16 kHz, **95 s exactement**, dont 82,303 s TTS (pauses naturelles incluses) et 12,697 s de padding explicite. Quatre blocs commencent à 0/28/56/84 s, sans troncature de parole. Les textes ont été enrichis avant toute inférence pour réduire les pauses ; les SHA ci-dessus identifient la référence finale.

Le code officiel Parakeet utilise un stride de 28 s : fenêtres 0–30, 28–58, 56–86, 84–95. Les nouvelles phrases et montants commencent donc dans les chevauchements. Montants distincts : 6300/63000, 7400, 8500/85000, 9600 ; acteurs, tâches et modalités différents par bloc. Référence complète : **231 tokens stricts, 214 numériques**. Aucun succès ne repose seulement sur des marqueurs.

Helper reproductible : `scripts/memora-prepare-long-asr.py`, caches TTS liés au SHA du texte/options ; refuse un dépassement de slot au lieu de tronquer. Manifest avec SHA et alignements dans `.memora/accuracy-benchmark/vlong-fr-1/manifest.json`. Préparation et vérification : `agents/logs/accuracy-long-fr-{prepare,verify}.log`.

## Exécution réelle production

Backend venv, `--production-factory --fr-engine parakeet-mlx --fr-model-path .memora/models/parakeet-v3`, français final. Vrai provider Parakeet et bon modèle/SHA observés : aucune sortie simulée.

**4,427 s** pour 95 s audio. 20 segments natifs entre 0 et 93,12 s, tous bornés dans [0,95]. Les quatre blocs sont présents, chacun des six montants apparaît une fois. Étapes et fin uniques : aucun bloc perdu ou doublon de chevauchement détecté. «À la» devient «A la» : accent compté, pas bloc manquant.

Mesures sur **tout le texte** :

- WER numérique : **9/214 = 4,2056%**, S6/D0/I3 ; CER numérique 22/1308 = 1,68196%.
- WER strict : **30/231 = 12,987%**, nombres écrits/chiffres inclus ; CER strict 9,36%.
- WER numérique par bloc : 4/62, 3/66, 2/65, 0/21. Inspection par starts natifs avec tolérance 1 s, sans réécrire l'ASR.
- Huit sondes lexicales sur huit passent ; cela ne prouve pas une fidélité sémantique parfaite.

**Erreurs concrètes :** Soraya → Sorella ; «Karim ne doit rien signer» → «car il ne doit rien signer», avec perte du responsable explicite malgré la négation préservée. Dépense/supplémentaire deviennent pluriels ; deux unités «euros» sont ajoutées. D0 numérique ne signifie donc pas qu'aucune information n'est perdue : Karim est substitué. Aucun comparatif Turbo long effectué ; pas de conclusion relative pour ces noms.

Pics RSS 1,501 Gio et allocations MLX 3,172 Gio : métriques distinctes, pas à additionner ou confondre avec une isolation matérielle. Une seule voix synthétique, quatre fenêtres/trois merges : pas une validation naturelle de 15 min ou 2 h.

Preuves : `agents/logs/accuracy-routed-fr-parakeet-long95.{json,log}` ; inspection complète `accuracy-long95-inspection.json`. Empreinte du bytecode/constantes `transcribe` chargé (positions de lignes neutralisées) : **0406fd75fd31fa2512625b509e49075dd37a0f5460ecc4f7b0c60c4c7ad373c5**.

Tous les processus sont terminés et le GPU libéré. Preuve **préguard `np.isfinite(samples)`**, ajouté ensuite par ROOT ; SHA distinct documenté, sans changement du modèle/chunks. La chaîne courante devra être vérifiée séparément. Services principaux et données utilisateur intacts.
