# Scripts Memora

Ce dossier contient les outils nécessaires à l’installation, au fonctionnement et à la vérification de Memora. Les diagnostics ponctuels de développement et les anciennes expériences devenues redondantes ont été retirés. Les notes des agents de code restent dans `.agents/`, hors Git.

Les commandes ci-dessous s’exécutent depuis la racine du dépôt. Le [guide principal](../README.md) décrit l’installation complète et les précautions de maintenance.

## Usage quotidien

```sh
./scripts/memora-start.sh
./scripts/memora-status.sh
./scripts/memora-stop.sh
```

Ces trois commandes délèguent aux lanceurs `memora-docker-start.sh`, `memora-docker-status.sh` et `memora-docker-stop.sh`. Ils gèrent les cinq services Docker, dont le worker indépendant, et le compagnon IA natif. L’arrêt conserve les volumes et les données.

| Script de fonctionnement | Rôle |
|---|---|
| `memora-docker-env.py` | Générer la configuration privée Docker en préservant les identités applicatives. |
| `memora-postgres-check.py` | Vérifier que PostgreSQL correspond à la base importée et validée. |
| `memora-docker-bridge.py` | Démarrer, contrôler et arrêter le compagnon natif local. |
| `memora-inference-host.py` | Exécuter les inférences audio natives appelées par l’application Docker. |

## Installation et maintenance

| Scripts | Utilité |
|---|---|
| `memora-install.sh`, `memora-env.py` | Installer les dépendances verrouillées, préparer les modèles sélectionnés et la configuration initiale. |
| `memora-import-postgres.py` | Importer les SQLite dans un PostgreSQL vide, avec sauvegardes et comparaison des données. Ne pas relancer pour un démarrage normal. |
| `memora-migrate.py`, `memora-bind-owners.py` | Préparer les bases SQLite de bootstrap ou mettre à niveau un ancien stockage avant import. Ils restent utilisés par l’installateur et les tests. |
| `memora-demo.py` | Préparer un compte synthétique de démonstration ; ses identifiants restent privés. |
| `memora-download-mlx.py` | Préparer et vérifier les poids Whisper MLX épinglés. |
| `memora-prepare-ecapa.py` | Préparer et vérifier les poids du moteur de séparation ECAPA. |
| `memora-prepare-segmentation.py` | Préparer les poids MIT ONNX de segmentation, distribués publiquement sans compte ; `--check-only` vérifie les fichiers hors réseau. |
| `memora-prepare-diarization.py` | Préparer les poids de l’alternative Resemblyzer, encore configurable. |
| `memora-download-parakeet.py`, `memora-download-large-v3.py` | Préparer les modèles alternatifs si explicitement sélectionnés dans la configuration. L’installateur les utilise encore ; ils ne sont pas nécessaires au démarrage quotidien. |

Les modèles existants ne doivent pas être supprimés lors d’un nettoyage des scripts. Aucun poids n’est téléchargé automatiquement pendant une réunion. Les commandes de contrôle sans téléchargement sont documentées dans le [guide IA](../docs/MEMORA.md#ia-locale-et-limites).

## Tests de fonctionnement et de reprise

| Scripts | Utilité |
|---|---|
| `memora-test.py` | Exécuter les tests backend avec bases et stockage temporaires. |
| `memora-verify-postgres.py` | Vérifier PostgreSQL et l’import sur deux bases synthétiques jetables. |
| `memora-verify-docker.py` | Recette intégrée Docker : navigateur, modèles locaux, partage, exports, SSE et emails locaux. Option `--ui-audit-only` pour l’audit d’interface et le temps réel. |
| `memora-verify-isolated.py` | Recette native SQLite isolée, également utilisée pour vérifier la reprise du worker. |
| `memora-e2e-api.py` | Contrôles fonctionnels API exécutés notamment par la recette native. |
| `memora-verify-worker-resume.py` | Vérifier les checkpoints et la reprise après arrêt brutal dans un environnement synthétique dédié. |
| `memora-resilience.py` | Vérifier un échec réel du fournisseur local puis la relance sur des données jetables. |
| `memora-mail-capture.py` | Capture SMTP des recettes natives ; Docker utilise Mailpit. |

Les tests des scripts eux-mêmes sont dans `tests/`. Ils vérifient notamment la génération d’environnement, les installateurs, les téléchargeurs, le scoring et l’isolation des recettes. Certains utilisent pytest, d’autres unittest :

```sh
backend/.venv/bin/python -m pytest scripts/tests -q
```

## Non-régression de la qualité IA

Ces outils restent utiles pour vérifier un changement de moteur ou de prompt. Ils ne sont pas exécutés au démarrage de l’application. Lire leur en-tête et leurs options avant utilisation ; les inférences peuvent prendre du temps et concurrencer les réunions en cours.

| Scripts | Périmètre |
|---|---|
| `memora-benchmark-accuracy.py` | Corpus synthétique de précision ASR, préparation des audios et mesures sur références. |
| `memora-benchmark-mlx.py` | Comparaison de transcription MLX/CPU ; contient aussi la vérification des poids appelée par le téléchargeur MLX. |
| `memora-benchmark-long.py`, `memora-prepare-long-asr.py` | Sources synthétiques longues, bilingues ou françaises, pour contrôler la segmentation et les limites de lots. |
| `memora-qa-capture.py` | Mesures codec/transcription et métriques réutilisées par le benchmark MLX. |
| `memora-qa-asr-language-drift.py` | Régression de langue et comparaison sur corpus français synthétique. |
| `memora-benchmark-analysis.py` | Évaluation des rapports avec références et relecture sémantique explicite ; pas de score inventé par le modèle. |
| `memora-qa-long-context.py`, `memora-qa-long-independent.py`, `memora-qa-cross-batch.py` | Conservation des faits et transitions sur sources longues ou réparties en plusieurs lots. |
| `memora-qa-speaker-context.py`, `memora-qa-report-fragments.py` | Attribution des noms corrigés, dates, engagements et fragments de transcription. |
| `memora-qa-gemma-validation.py` | Regrouper les contrôles sémantiques courts et les cas de sécurité du modèle local. |
| `memora-qa-conversation.py` | Questions de suivi, références conversationnelles et information absente. |
| `memora-qa-local.py` | Parcours local ASR → analyse → réponse sur fixtures synthétiques. |
| `memora-benchmark-diarization.py` | Préparation et évaluation de la séparation des voix synthétiques. |
| `memora-prepare-diarization-reserve.py`, `memora-prepare-speaker-holdout.py` | Corpus complémentaires pour vérifier les erreurs d’attribution et de comptage. |
| `memora-qa-speaker-consistency.py`, `memora-qa-auto-speakers.py` | Cohérence du nombre de voix et intégration de la séparation automatique. |

Les outils de qualité peuvent exiger des voix TTS macOS déjà installées, des modèles préparés ou un chemin de sortie neuf. Ils utilisent des données synthétiques, pas les enregistrements personnels de l’application. Les mesures sont propres au corpus utilisé et ne garantissent pas une précision universelle.

## Fichiers locaux et sécurité

Les journaux et comptes rendus restent dans `.agents/`, ignoré par Git. Les données, modèles, secrets, emails et sauvegardes restent dans `.memora/`, également hors Git. Les recettes ne doivent déclencher ni microphone utilisateur ni email extérieur. Les scripts de migration ne doivent jamais servir de commande de réinitialisation de l’application active.

La suppression des anciens scripts n’efface ni les résultats historiques locaux ni les modèles. Le démarrage, les migrations, les recettes Docker et les outils de qualité conservés gardent leurs chemins existants.


## État du compagnon natif après redémarrage du Mac

Docker peut redémarrer ses conteneurs alors que le compagnon natif est encore arrêté. Utiliser `./scripts/memora-start.sh` pour remettre l’ensemble en route. `memora-docker-bridge.py status` vérifie le PID, l’identité HTTP du service et un endpoint authentifié ; un port simplement ouvert ne suffit pas. Le lancement direct est idempotent et reste le mode par défaut (`start --unmanaged` peut le demander explicitement).

Le démarrage automatique à l’ouverture de session n’est pas livré sur ce poste. Un essai de supervision macOS a échoué avant disponibilité ; il a été désactivé et retiré. La commande de démarrage ci-dessus reste la procédure validée après redémarrage.

- `memora-prepare-community.py` : recours de diarisation complet CoreML/VBx,
  optionnel sur Apple Silicon/macOS15+/Swift6.2+. Sources et modèles publics
  épinglés, licences conservées, aucun compte ni activation de service.
  `--check-only` valide hors réseau ; `--from-lab CHEMIN` réutilise les fichiers
  locaux vérifiés. Les ressources de build sont dans `scripts/resources/community-*`.
