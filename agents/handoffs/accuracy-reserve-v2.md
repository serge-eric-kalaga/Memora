# Réserve ASR v2 — figée avant toute inférence

25 octobre2026. Suite au holdoutv1 désormais consommé, ROOT demande une nouvelle réserve indépendante pour évaluer d'autres familles de moteur. Aucun résultat v1 n'est requalifié aveugle. Aucune transcription/GPU lancée pendant cette préparation. Aucune donnée ni voix utilisateur. Pas de modification backend/adapters/services principaux.

## Références et critères préenregistrés

Manifest source versionnable `backend/test/fixtures/memora/accuracy-corpus.v2.json`.
SHA256 **d659c2c6612c168d12c12e843bd36be872a5dea4af760a547e9aa2de8f8e7850**.
12sources inédites :4FR,4EN,4bilingues ; aucun texte corrigé d'après une sortie ASR. Voix Thomas/Amélie/Jacques et Samantha/Daniel/Karen/Moira, rates152–202mots/min. Oral «Alors», «Bon», «Well», phrases courtes, montants1600/16000 et2800/28000, noms/technique, négations, échéances conditionnelles/propositions. Déclaration numérique figée dans le manifeste avant sorties.

Deux cas difficiles **explicitement conservés** : `reserve-fr-short-hard` Jacques/phrases courtes400ms, `reserve-mixed-continuous-hard` Jacques+Karen/gap0ms. Autres mixtes300/400/200ms. Les voix sont majoritairement déjà utilisées ; la réserve ne repose pas uniquement sur des voix inédites. Les noms et faits sont nouveaux, des termes techniques récurrents restent intentionnels. Pas de lexique injecté par défaut.

Chaque source×6conditions propre/bruit20/bruit10/échos/Opus32/amplitude-24dB+silence/bruit négatifs = **74fichiers,570,17secondes acoustiques cumulées**. Cache séparé `.memora/accuracy-benchmark/v2/`, jamais écrasementv1. Même protocole acoustique déterministe documenté dans le handoffv1 ; grainev2=20261026. Profils d'une source non indépendants, TTS non représentatif de toute réunion naturelle.

Critère primaire avant inférence : WER numérique micro propre≤10% (1-WER≥90%), indicateur opérationnel synthétique uniquement. Rapporter aussi strict/CER/S-D-I, chaque langue/profil/source, erreurs critiques lexicales, hallucinations, régressions, latence/RAM. Aucun cas supprimé pour améliorer un agrégat. Une perte de négation/échéance doit être inspectée, pas compensée silencieusement par les autres mots. Critères dans `acceptance` JSON. Réserve entièrementholdout ; pas de tuning dessus puis réutilisation comme aveugle.

## Harness prêt

`scripts/memora-benchmark-accuracy.py --corpus backend/test/fixtures/memora/accuracy-corpus.v2.json --split holdout --prepared` : vérifie SHA corpus et tous audios préparés, aucune synthèse/dépendancefaster-whisper ni GPU. `--run` reste obligatoire pour inférer et requiert signalROOT pour sérialiser GPU.

Vérification modèle accepte explicitement les deux repos Whisper et `mlx-community/parakeet-tdt-0.6b-v3`, poids `model.safetensors` pour ce dernier ; manifeste provenance/revision/taille/SHA et assets annexes vérifiés. Variantes contexte/vocab/décodage/routageWhisper rejetées pour Parakeet. Paramètre langue Parakeet déclaré **hint de compatibilité, pas décodeur forcé**, aucune fausse preuve de détection. Runtime expérimental `.memora/asr-lab/bin/python`, adapter de frontend `scripts/memora-parakeet-experimental.py` ; téléchargement/validationSHA encore du ressortfrontend/ROOT.

Commande future (NE PAS exécuter avant signalROOT et modèlecomplet) :
`.memora/asr-lab/bin/python scripts/memora-benchmark-accuracy.py --run --prepared --corpus backend/test/fixtures/memora/accuracy-corpus.v2.json --split holdout --language native --variant baseline --label parakeet-reserve-v2 --model-path .memora/models/parakeet-v3 --adapter-path scripts/memora-parakeet-experimental.py`

Vérifications obtenues :74SHA/format16k/nonvide, répartition4/4/4, toutes sondes critiques trouvent les références, montants distincts, CLI `--prepared` réussie avec backendvenv etlabvenv, Ruffcheck/format et auto-tests PASS. Logs `agents/logs/accuracy-reserve-v2-{prepare,verify,lab-verify}.log`. Source/cache et manifeste figés ; sorties ASR pour v2 : **aucune**. Scripts de rescore réutilisent désormais le dictionnaire numérique enregistré dans chaque sortie, empêchant la normalisationv2 de modifier silencieusement une ancienne mesure.

## Candidate préenregistrée avant résultats v2

Après tuningv1 Parakeet62cas, ROOT fige **Parakeet vanilla chunk30s/overlap2s**, sans changement de décodage ni lexique. Comparaison sur réservev2 encore intacte : Turbo snapshot74 puis Parakeet74, mêmes voix/audio/conditions/languehintnative ; aucun tuning ni retrait de cas après ces résultats. Publier chaque langue/profil et omission critique observée en tuning. GateROOT : aucune activation globale si régressions critiques. Ne pas interpréter un WER moyen comme permission de masquer une décision/négation perdue.

TuningParakeet préalable :77,491s bout-en-bout (inclut SHA complet2,5GB à CHAQUE appel du prototype, contrairement à Whisper vérifié une fois), RSS2,496GiB/MLX2,561GiB. WERnum propre4,49%, bruit20=7,69%, bruit10=14,74%, Opus3,21%, faible3,85%, échos3,85% ; critiques18/20 propre,19/20Opus. ContreTurbo, gainscompression/faible/bruit20 mais dégradationpropre/bruit10/échos. Cent→sans et omission entière de la phrase anglaise bruit20 directement inspectées. Aucun fauxglossaire, silence/bruit sans texte. Les sorties ne sont pas une preuve de supériorité générale. `accuracy-parakeet-native-tuning.{json,log}`, comparaisonv1 enrichie.

## Résultats réserve v2 —148cas terminés

Turbo74 puis candidate Parakeet vanilla74, mêmes SHA audios, corpuspréenregistré inchangé, aucune exclusion/retouche. GPU rendu, processus terminés. Comparaison `agents/logs/accuracy-reserve-v2-comparison.json` ; sorties détaillées `accuracy-{turbo,parakeet}-reserve-v2.{json,log}`.

| WERnum micro | Turbo | Parakeet |
|---|---:|---:|
| Propre |11,62% (28/241)|7,05% (17/241)|
| Bruit20 |13,69%|7,47%|
| Bruit10 |18,26%|11,62%|
| Opus32 |12,45%|4,98%|
| Faible24 |12,03%|7,88%|
| Échos |17,43%|7,05%|

Propre par langue : FR20/83→6/83 (24,10→7,23%), EN1/86→3/86 (1,16→3,49%), mixte7/72→8/72 (9,72→11,11%). Strict propre17,93→13,15%. Critiques lexicales25/30→24/30. Temps bout-en-bout98,800→86,168s (Parakeet inclut vérification complète des poids à chaque appel). Pics RSS2,250→2,499GiB, allocationsMLX2,039→2,599GiB. Les4négatifs sans texte. Seuil propre numérique global franchi par Parakeet, mais pas chaque langue/profil et pas une précision naturelle garantie.

**Inspection critique paire par paire :**15régressions lexicales,10améliorations. Régressions réelles de termes propres : Banfora→Banfera sur5conditionsFR ; Kubernetes→CubaNeeds sur3conditionsEN. Six autres sont Inès→Ines (accent) et une decision→décision : ces sept échecs de sonde ne sont pas des pertes de négation/sens constatées. Aucun nouveau changement de montant/échéance/négation détecté dans les sondes comparées ; cette inspection limitée n'est pas une preuve sémantique exhaustive.

Améliorations directement inspectées : conserve «ne doit pas payer» sur5conditions FRdifficiles où Turbo produisait des phrases sans rapport ; noms Banta/Mantal au lieu de Binta restent faux. Retrouve Nadia/Noah surbruit10, restitue la phrase anglaise «This is a proposal, not a final decision» échos omise parTurbo et maintient la langue originale du contraste1600/16000 surdeuxcas mixtes traduits parTurbo. **Échec encore présent :** FRdifficile bruit10 «Mental doit le patérier» n'exprime plus «Binta ne doit pas payer». Ne pas compter tous les échecs lexicaux comme pertes sémantiques, ni ignorer les vraies pertes parce que la moyenne s'améliore.

La candidate globale n'est pas déclarée validée pour production. ROOT propose ensuite une autre politique FRfinalParakeet/autresTurbo ; décision **postérieure à v2**, donc v2 ne la redevient pas aveugle. Nouvelle réservev3 demandée avant tout nouveau résultat ; aucune politique sélectionnée après observation de v3 ne pourra revendiquer ce mêmev3 indépendant.
