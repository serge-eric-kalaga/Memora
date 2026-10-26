# Memora

**Enregistrer une réunion, retrouver ce qui a été dit et transformer les échanges en un compte rendu exploitable.**

Memora est une application de réunions, de transcription et d’analyse IA construite à partir d’un template **FastAPI + Next.js**. Elle rassemble l’audio, la transcription horodatée, le rapport, les actions et un chat fondé sur les passages de la réunion.

La V1 fonctionne localement avec **Docker Compose et PostgreSQL**. Sur la configuration macOS Apple Silicon retenue, la transcription et la séparation des voix utilisent un compagnon natif ; la génération des rapports et les réponses du chat utilisent l’installation **Ollama** de la machine. Les contenus ne sont pas envoyés à un fournisseur IA externe.

> Cette documentation décrit une application utilisable localement. Elle ne constitue ni une qualification pour la production, ni une garantie de précision sur toutes les voix et toutes les conditions d’enregistrement.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Démarrer une installation déjà préparée](#démarrer-une-installation-déjà-préparée)
- [Première installation et import PostgreSQL](#première-installation-et-import-postgresql)
- [Essayer Memora](#essayer-memora)
- [Temps réel et traitements durables](#temps-réel-et-traitements-durables)
- [IA locale et choix de langue](#ia-locale-et-choix-de-langue)
- [Configuration](#configuration)
- [Données, sauvegardes et mises à jour](#données-sauvegardes-et-mises-à-jour)
- [Structure du projet](#structure-du-projet)
- [Tests et vérifications](#tests-et-vérifications)
- [Dépannage](#dépannage)
- [Limites connues](#limites-connues)
- [Documentation complémentaire](#documentation-complémentaire)

## Fonctionnalités

| Domaine | Ce que propose Memora |
|---|---|
| Réunions | Tableau de bord, recherche, consultation des réunions terminées et archives. Archivage distinct de la suppression. |
| Enregistrement | Microphone activé par action explicite, choix d’entrée, vérification audio, onde défilante, pause et reprise. Une barre de contrôle accompagne la navigation entre les pages de l’application. |
| Sauvegarde | Fragments conservés temporairement dans le navigateur avant envoi, accusés de réception serveur et reprise des fragments non confirmés. Import d’audio avec progression et validation du contenu. |
| Transcription | Aperçu provisoire pendant la capture, résultat final horodaté, choix français/anglais/automatique, signalement des passages incertains. |
| Intervenants | Regroupement local des voix en intervenants numérotés lorsque l’attribution est possible, renommage et correction manuelle. |
| Rapport | Résumé, sujets, décisions, actions, responsables, échéances et questions ouvertes lorsque ces éléments sont établis. Relecture humaine des décisions et actions. |
| Chat IA | Discussion sur une réunion, réponses liées à ses sources et accès aux moments correspondants de l’audio selon les droits. |
| Historique | Versions de transcription et de rapport conservées. Une correction signale le rapport à actualiser ; sa régénération conserve les résultats précédents. |
| Partage | Liens ouverts ou protégés par mot de passe, contenus et droits configurables, accès invité sans compte, expiration et révocation. |
| Notifications | Disponibilité du rapport dans l’application et emails capturés localement par Mailpit. |
| Exports | Transcription : TXT, PDF, DOCX, SRT et VTT. Rapport : TXT, PDF, DOCX et Markdown. Export de la version affichée, soumis aux droits d’accès. |
| Administration | Durée maximale, taille d’import, conservation de l’audio et capacité de modification des invités, avec bornes de validation. |

## Architecture

```text
Navigateur
    │
    ▼
Next.js — interface et relais vers l’API           Docker : 127.0.0.1:3000
    │
    ▼
FastAPI — authentification, réunions et flux SSE   Docker : 127.0.0.1:8080
    ├── Worker indépendant — file persistante et IA
    ├── PostgreSQL 16 — comptes et données métier  Docker : 127.0.0.1:5433
    ├── Mailpit — capture des emails de test       Docker : 127.0.0.1:8025
    ├── Fichiers audio — stockage local persistant
    ├── Compagnon IA — transcription et voix       Hôte   : 127.0.0.1:8091
    └── Ollama — rapports et chat                  Hôte   : 127.0.0.1:11434
```

Les cinq services Compose sont `frontend`, `backend`, `worker`, `postgres` et `mailpit`. Le worker utilise la même image Python que l’API mais s’exécute dans un conteneur indépendant. Un redémarrage de l’API ne redémarre pas ce processus de calcul. PostgreSQL utilise le schéma `public` pour les comptes et le schéma `memora` pour les réunions, versions, tâches et partages.

**Pourquoi une partie native ?** MLX exploite le GPU Apple et ne fonctionne pas dans les conteneurs Linux de Docker Desktop. Le lanceur gère donc un compagnon natif authentifié. Après un redémarrage du Mac, relancer `./scripts/memora-start.sh` : le redémarrage automatique des conteneurs Docker ne démarre pas à lui seul ce processus natif. Les conteneurs le joignent, ainsi qu’Ollama, via `host.docker.internal` : leur `localhost` désignerait le conteneur lui-même.

Les ports publiés par Compose sont liés à l’interface locale. Ollama reste un service indépendant : les scripts Memora ne le réinstallent pas et ne l’arrêtent pas.

## Prérequis

Pour reproduire la configuration locale actuelle :

- **macOS Apple Silicon** pour la chaîne MLX retenue ; la configuration CPU alternative demande un choix explicite et ne constitue pas une recette Docker multiplateforme validée.
- **Docker Desktop démarré**, avec Docker Compose prenant en charge les fichiers d’environnement au format `raw`.
- **Python 3.12** et **uv** pour l’environnement natif et les outils de maintenance. L’installateur peut préparer uv dans un environnement local s’il est absent.
- **Node.js 24 et npm**, conformément aux contraintes du frontend, pour installer les outils et exécuter les vérifications locales.
- **Ollama déjà installé et actif**, avec le modèle configuré disponible localement.
- De l’espace pour les images Docker, les modèles, les audios et les sauvegardes. La taille des modèles ne représente pas toute la mémoire nécessaire à leur exécution.

Les dépendances Python sont verrouillées dans `backend/uv.lock` ; celles du frontend dans `frontend/package-lock.json`. Le projet utilise **Docker Compose**, sans composant PHP ni besoin de Composer.

## Démarrer une installation déjà préparée

Toutes les commandes suivantes s’exécutent depuis la racine du dépôt :

```sh
./scripts/memora-start.sh
```

Le lanceur prépare la configuration Docker privée, démarre PostgreSQL, vérifie la marque d’import et la cohérence de la base, démarre le compagnon IA puis les services applicatifs. Il refuse de lancer l’application si l’import PostgreSQL n’est pas validé.

| Accès | Adresse |
|---|---|
| Application | http://127.0.0.1:3000 |
| Documentation interactive de l’API | http://127.0.0.1:8080/docs |
| Boîte de réception Mailpit | http://127.0.0.1:8025 |
| SMTP de capture local | `127.0.0.1:1025` |
| PostgreSQL, maintenance locale | `127.0.0.1:5433` |

Pour consulter l’état ou arrêter Memora :

```sh
./scripts/memora-status.sh
./scripts/memora-stop.sh
```

L’arrêt conserve les données PostgreSQL, les fichiers audio et les emails capturés. Les scripts `memora-start`, `memora-status` et `memora-stop` délèguent aux lanceurs `memora-docker-*`.

**Compte de démonstration :** lorsqu’il a été préparé sur la machine, ses identifiants sont dans `.memora/demo.json`, fichier privé exclu de Git. Aucun mot de passe universel n’est inclus dans ce README. Le script de préparation du compte est décrit dans [l’index des scripts](scripts/README.md).

## Première installation et import PostgreSQL

Cette étape est distincte du lancement quotidien. Elle prépare les dépendances natives, les modèles choisis et les bases SQLite de bootstrap, puis les importe dans PostgreSQL. Une installation existante garde ses identités et ses clés.

### 1. Préparer l’environnement natif

Vérifier d’abord Docker et les modèles Ollama existants :

```sh
docker compose version
ollama list
```

Préparer ensuite le projet :

```sh
./scripts/memora-install.sh
```

Ce script installe les dépendances verrouillées, génère la configuration privée et prépare les modèles correspondant au moteur configuré. Il peut télécharger les poids manquants ; il ne faut pas le relancer à chaque démarrage. L’exemple des variables est dans [.env.memora.example](.env.memora.example).

### 2. Préparer Docker et importer les données

Pour une migration existante, terminer les enregistrements et les traitements puis arrêter l’ancienne API avant l’import. L’importeur refuse un stockage actif et une base cible déjà occupée.

```sh
python3 scripts/memora-docker-env.py
docker compose --env-file .memora/docker/compose.env build
docker compose --env-file .memora/docker/compose.env up -d --wait postgres
backend/.venv/bin/python scripts/memora-import-postgres.py --apply
./scripts/memora-start.sh
```

L’import sauvegarde les SQLite, applique les migrations PostgreSQL, conserve les identifiants, mots de passe hachés, versions, corrections, partages et dates, puis compare le contenu des tables. Les séquences sont ajustées pour les futures créations de comptes.

La validation produit `.memora/docker/import-complete.json`, conservé localement. Le démarrage vérifie également une marque dans PostgreSQL pour détecter une perte ou un remplacement du volume. **Ne pas créer ou modifier manuellement cette preuve pour contourner un échec d’import.**

Après bascule, PostgreSQL est la base applicative. Les anciennes bases SQLite restent des sources de migration et des sauvegardes ; elles ne reçoivent plus les écritures de l’application Docker.

## Essayer Memora

### Enregistrer ou importer

1. Se connecter, créer une réunion et sélectionner **Français**, **Anglais** ou **Automatique/bilingue**.
2. Pour enregistrer, informer les participants, vérifier le microphone puis cliquer sur **Enregistrer**. Le navigateur demande l’autorisation ; aucune capture ne commence au chargement de la page.
3. Vérifier l’onde audio, utiliser **Pause** et **Reprendre** si nécessaire. La navigation dans l’application conserve la capture et sa petite barre de contrôle.
4. Cliquer sur **Terminer** pour sauvegarder les derniers fragments et déclencher le traitement final.

Pour tester sans microphone, importer un audio synthétique, par exemple `backend/test/fixtures/memora/french.wav` ou `english.wav`. Le transfert affiche sa progression ; l’audio est validé avant transcription et analyse.

La transcription en direct est **provisoire** : elle dépend de la réception des fragments et de la disponibilité du moteur. La transcription finale relit l’audio complet. Lorsque la finalisation est acceptée, le traitement continue côté serveur et une notification annonce la disponibilité du rapport.

### Relire, corriger et discuter

La page de réunion réunit **Rapport**, **Transcription**, **Chat IA** et lecteur audio. Les sources permettent de réécouter un passage autorisé. Le chat répond à partir de la réunion ; une information absente ne doit pas être présentée comme acquise.

Corriger une phrase ou un intervenant crée une nouvelle version. Le chat utilise la transcription courante ; les anciens échanges restent rattachés à leur version. Le rapport devient à actualiser : le régénérer conserve les rapports précédents. **Retranscrire l’audio** relance la reconnaissance et crée aussi une version distincte ; ce n’est pas la même opération que régénérer seulement le rapport.

La séparation des voix produit des étiquettes telles que **Intervenant 1** et **Intervenant 2**, sans déduire les noms réels. Depuis **Gérer les intervenants**, on peut renommer une étiquette ou relancer la séparation avec un nombre connu. Les attributions restent à vérifier.

### Partager et exporter

Créer un lien ouvert ou protégé, sélectionner ses contenus et droits puis, si nécessaire, une expiration. Un invité n’a pas besoin de compte pour exercer les permissions accordées. Un lien et son mot de passe peuvent être retransmis : les adresses destinataires d’un email ne constituent pas un contrôle nominatif d’accès.

Dans les onglets Rapport et Transcription, **Exporter** télécharge la version affichée. Les mêmes droits s’appliquent aux fichiers : un lien limité au rapport ne donne pas accès à la transcription.

Les emails de cette installation sont visibles dans Mailpit. Pour une recette, utiliser des adresses synthétiques ; cette capture ne prouve pas une délivrabilité sur Internet.

## Temps réel et traitements durables

Le tableau de bord, les notifications, la page réunion et l’état des emails reçoivent les changements par **SSE** (Server-Sent Events). Le navigateur garde une connexion HTTP ouverte ; PostgreSQL signale les changements validés via `LISTEN/NOTIFY`, puis le navigateur recharge les données autorisées concernées. En fonctionnement normal, il n’interroge plus ces écrans toutes les quelques secondes.

Ce flux à sens unique répond au besoin d’afficher les résultats des traitements. Les créations, corrections et fragments audio restent des requêtes HTTP avec validation et accusé de réception. Un WebSocket bidirectionnel n’est pas nécessaire pour ce parcours. Les battements du flux ne déclenchent pas de GET de données.

La connexion est partagée entre les consommateurs du même périmètre dans un onglet. Après coupure, le client se reconnecte avec temporisation progressive et recharge l’état courant pour récupérer les événements manqués. Si le flux est indisponible, une actualisation de secours toutes les 15 secondes reste active jusqu’à son rétablissement. Les permissions sont revérifiées à chaque événement et au plus tard au battement suivant (15 secondes) ; chaque requête de données reste elle-même autorisée côté serveur.

Le service Docker **`worker`** prend en charge la transcription provisoire/finale, la séparation des voix, la génération des rapports, les emails capturés et la rétention. Les tâches et points de reprise sont enregistrés dans PostgreSQL, indépendamment du navigateur. Un verrou sur le volume de données empêche deux workers locaux de traiter la même file simultanément.

- **Coupure réseau du navigateur** : les tâches déjà reçues continuent côté serveur. Les fragments d’enregistrement encore locaux doivent être retransmis après reconnexion.
- **Redémarrage de l’API** : le worker poursuit son calcul ; l’API ne remet pas ses tâches actives en file.
- **Arrêt brutal du worker** : Docker le redémarre et les tâches interrompues reprennent au dernier checkpoint validé. Une phase non validée peut être recalculée ; une source déjà publiée et les rapports précédents sont conservés.
- **Indisponibilité de PostgreSQL** : le worker réessaie ses opérations de stockage et conserve sa tâche en cours ; une reprise après redémarrage utilise la file persistante.
- **Erreur du modèle** : l’échec reste visible et relançable, sans boucle de tentatives illimitée masquant le problème.
- **Machine éteinte ou réellement en veille** : le calcul est suspendu ; il reprend lorsque la machine et les services redémarrent. Aucun logiciel local ne peut continuer à calculer sur une machine arrêtée.

Cette V1 conserve la file PostgreSQL existante plutôt que d’ajouter Celery et un broker Redis. Elle est prévue pour **un worker de calcul** sur cette installation, pas pour une ferme distribuée. Le **chat IA reste une requête synchrone** : son historique est sauvegardé après réponse, mais une génération de chat interrompue par un arrêt de l’API n’est pas une tâche durable automatiquement reprise.

Pour les détails du transport, des limites et des tests, voir [Temps réel et worker](docs/MEMORA.md#temps-réel-et-worker-docker-indépendant).

## IA locale et choix de langue

| Rôle | Configuration retenue sur ce Mac | Points à connaître |
|---|---|---|
| Transcription | MLX Whisper, `large-v3-turbo` | Modèle local d’environ 1,61 Go ; le choix français impose `fr` et la tâche de transcription. |
| Détection de parole | Silero VAD | Repère les portions vocales en conservant leur position dans l’audio. Une voix très faible peut être manquée. |
| Séparation des intervenants | ECAPA-TDNN avec reprise par segmentation neuronale ONNX ; recours optionnel Community-1 CoreML/VBx | Modèles locaux sans compte requis ; environ 83 Mo + 6 Mo, et 21 Mo pour le recours Mac ; groupes vocaux estimés, sans identification nominative. Voir le [guide](docs/MEMORA.md#recours-community-1-local-sans-compte). |
| Rapport et chat | `gemma4:e4b` dans Ollama | Modèle existant sur cette machine ; son absence produit une erreur, sans remplacement par une API externe. |
| Alternative de transcription | Faster Whisper CPU, choix explicite | Qualité et latence différentes ; pas de basculement silencieux après un échec MLX. |

Vérifier les modèles sans lancer de transcription :

```sh
ollama list
backend/.venv/bin/python scripts/memora-download-mlx.py --check-only
backend/.venv/bin/python scripts/memora-prepare-ecapa.py --check-only
```

Le mode **Français** transcrit en français, sans demander une traduction en anglais. Le mode **Automatique/bilingue** détecte la langue par portion vocale ; une alternance très rapide reste difficile. Les passages incertains sont signalés, mais l’absence de signal ne garantit pas l’exactitude.

Les longues sources sont traitées par lots avec références aux passages. Les limites de contexte ou de ressources donnent une erreur explicite plutôt qu’une troncature silencieuse. Une correction modifie la source utilisée par le chat ; aucun index externe n’est nécessaire dans cette V1.

Les modèles, licences, options et mesures historiques sont détaillés dans le [guide IA](docs/MEMORA.md#ia-locale-et-limites). Les résultats sur des corpus synthétiques ne permettent pas de promettre « 90 % de précision » pour toutes les réunions.

## Configuration

La configuration privée est générée, pas stockée dans Git :

| Fichier | Rôle |
|---|---|
| `.env.memora.example` | Variables documentées, sans secrets ; référence pour comprendre les options. |
| `.memora/backend.env` | Configuration native, chemins de modèles et clés applicatives. |
| `.memora/docker/compose.env` | Paramètres de Compose, chemins absolus, ports et identifiants PostgreSQL privés. |
| `.memora/docker/backend.env` | Configuration du backend conteneurisé et accès au compagnon IA. |

Le générateur Docker préserve les identités et clés existantes. Ces fichiers contiennent des secrets : ne pas les copier dans un ticket, un log partagé ou un commit. Déplacer le dépôt peut invalider les chemins absolus ; régénérer la configuration et vérifier les montages avant redémarrage.

Principaux réglages administratifs initiaux :

| Réglage | Valeur initiale | Bornes ou comportement |
|---|---:|---|
| Durée maximale | 120 minutes | 1 à 240 minutes |
| Taille maximale d’import | 250 Mo | 1 à 500 Mo |
| Conservation de l’audio | 30 jours | 1 à 365 jours |
| Capacité de modification invitée | Désactivée | Doit aussi être accordée sur le lien concerné |
| Langue du rapport et du chat | Français | Français ou anglais |
| Expiration proposée pour un partage | 7 jours | Facultative ; maximum serveur de 366 jours |

Ce sont des valeurs initiales configurables. Les paramètres liés à la création d’une réunion y sont conservés ; modifier un réglage ne raccourcit pas silencieusement la conservation d’un ancien audio. Les détails des quotas et validations figurent dans le [guide de configuration](docs/MEMORA.md#configuration-et-paramètres).

## Données, sauvegardes et mises à jour

### Emplacements à préserver

- **Volume PostgreSQL Compose** : comptes et données métier actives.
- **`.memora/data/`** : fichiers audio persistants.
- **`.memora/models/`** : poids locaux des modèles.
- **`.memora/docker/` et `.memora/backend.env`** : configuration, secrets et preuve d’import.
- **`.memora/backups/`** : sauvegardes de migration ; elles ne remplacent pas une sauvegarde régulière de PostgreSQL après la bascule.
- **`backend/static/uploads/`** : fichiers de profil.
- **Volume Mailpit** : emails capturés localement.

**Ne pas exécuter `docker compose down -v` pour arrêter Memora.** Cette commande supprimerait ses volumes persistants. Utiliser `./scripts/memora-stop.sh`.

Une sauvegarde exploitable doit couvrir PostgreSQL, les médias et les clés nécessaires à leur lecture. Copier uniquement le code ou les anciens SQLite ne sauvegarde pas l’état actuel. La rétention peut supprimer l’audio arrivé à échéance ; l’archivage n’est pas une sauvegarde. La révocation d’un lien ne retire pas les copies déjà téléchargées.

### Reconstruire après une modification du code

Attendre la fin d’un enregistrement ou d’un traitement avant une opération de maintenance :

```sh
./scripts/memora-stop.sh
docker compose --env-file .memora/docker/compose.env build
./scripts/memora-start.sh
./scripts/memora-status.sh
```

Les images embarquent le code : modifier un fichier source ne met pas automatiquement à jour les conteneurs. Les traitements durables disposent de points de reprise, mais un arrêt reste une interruption. Les dépendances natives doivent également être synchronisées si leur verrouillage change.

## Structure du projet

```text
Memora/
├── backend/               API FastAPI, domaine, migrations, tests et uv.lock
├── frontend/              Interface Next.js, composants, tests et package-lock.json
├── scripts/               Lancement, installation, migrations et vérifications
├── docs/                  Guide fonctionnel et technique détaillé
├── docker-compose.yml     Services locaux et volumes persistants
├── .env.memora.example    Exemple de configuration sans secrets
├── .memora/               Données et configuration privées, hors Git
└── .agents/               Notes locales des agents de code, hors Git
```

Les scripts opérationnels font partie du projet et restent versionnés. Les scripts de benchmark sont optionnels pour l’usage quotidien ; [leur index](scripts/README.md) précise leur rôle et leurs prérequis. Les fichiers de consignes et de mémoire des agents de code sont ignorés par Git et ne sont pas requis pour utiliser un clone du projet.

## Tests et vérifications

Les recettes doivent utiliser des comptes et audios synthétiques, avec bases et stockage isolés. Les commandes ci-dessous sont des outils reproductibles ; leur présence dans le README ne signifie pas qu’elles viennent d’être exécutées sur votre machine.

### Tests backend et outils

```sh
backend/.venv/bin/python scripts/memora-test.py
backend/.venv/bin/python -m pytest scripts/tests -q
(cd frontend && node --test tests/memora-realtime.test.mjs)
backend/.venv/bin/ruff check --config backend/pyproject.toml scripts
```

Le lanceur backend prépare des bases et un stockage temporaires. Les contrats PostgreSQL et l’import se vérifient séparément, avec le PostgreSQL local démarré :

```sh
backend/.venv/bin/python scripts/memora-verify-postgres.py
```

Ce script crée deux bases synthétiques dédiées et les supprime après vérification ; il ne réinitialise pas la base applicative.

### Frontend

```sh
cd frontend
npm ci
npm run lint
npm run typecheck
npm run api:check
npm run build:memora
cd ..
```

### Parcours complet Docker

Après préparation des dépendances, modèles et images :

```sh
cd frontend
npx playwright install chromium
cd ..
backend/.venv/bin/python scripts/memora-verify-docker.py
```

Cette recette démarre une stack indépendante, utilise un microphone factice, des données synthétiques et une capture SMTP, puis nettoie ses ressources temporaires. Les modèles et Ollama restent partagés pour le calcul : éviter une recette lourde pendant une réunion. Si Chromium est déjà installé ailleurs, renseigner `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.

Pour un audit d’interface uniquement :

```sh
backend/.venv/bin/python scripts/memora-verify-docker.py --ui-audit-only
```

Les contrôles isolés ne prouvent pas le fonctionnement du microphone physique, une veille réelle, Safari/iOS ou une charge de production. Les benchmarks IA et leurs contraintes figurent dans [l’index des scripts](scripts/README.md) et le guide détaillé.

## Dépannage

| Symptôme | Vérification et action |
|---|---|
| L’application ou le service de connexion est indisponible | Exécuter `memora-status.sh`, vérifier Docker Desktop puis les journaux du backend et du frontend. Une page Next.js accessible ne prouve pas que l’API fonctionne. |
| Le lancement indique « Import PostgreSQL non validé » | Reprendre la procédure d’import et lire l’erreur. Ne pas supprimer les données ni fabriquer le fichier de validation. |
| La transcription échoue ou indique « moteur audio local indisponible » | Exécuter `memora-status.sh`, puis `memora-start.sh` si le compagnon natif est arrêté. Docker peut redémarrer sans ce processus natif. Vérifier ensuite les modèles avec `--check-only`, puis relancer explicitement le traitement échoué. |
| Le rapport ou le chat échoue | Vérifier Ollama et la présence du modèle configuré avec `ollama list`. Une panne de modèle ne nécessite pas de réimporter l’audio. |
| Le microphone ne fonctionne pas | Vérifier les permissions du navigateur et du système, sélectionner la bonne entrée puis utiliser la vérification microphone de Memora. |
| Des fragments restent à sauvegarder | Garder le même profil de navigateur et utiliser la reprise proposée. Pour un import interrompu, sélectionner le même fichier. |
| Un ancien résultat ne reflète pas une correction | Vérifier la version de transcription affichée puis régénérer le rapport. Pour changer la reconnaissance audio, utiliser la retranscription. |
| Le nombre d’intervenants est incorrect | Vérifier les voix et relancer la séparation locale, en indiquant le nombre connu si nécessaire. Ne pas assimiler un numéro à une identité certaine. |
| Un changement de code n’apparaît pas | Reconstruire les images puis relancer hors enregistrement ; un simple rafraîchissement du navigateur ne reconstruit pas Docker. |
| Un email n’arrive pas dans une boîte externe | Le fonctionnement local capture les messages dans Mailpit ; consulter `127.0.0.1:8025`. |

Pour consulter les journaux des services sans modifier les données :

```sh
docker compose --env-file .memora/docker/compose.env logs --tail=100 backend worker frontend
```

Inspecter les journaux localement et masquer tout contenu sensible avant de les partager.

## Limites connues

- **Précision IA** : noms propres, voix faibles, bruit, chevauchements et changements de langue peuvent produire des erreurs. Relire les décisions, responsables et échéances avec les passages sources.
- **Intervenants** : la séparation peut confondre deux voix ou diviser une seule personne. Le moteur peut s’abstenir ; la correction manuelle reste nécessaire dans certains cas.
- **Arrière-plan et veille** : changer de page dans l’application ou d’onglet peut conserver la capture. La protection contre la veille automatique ne permet pas d’enregistrer une machine réellement endormie ou un microphone coupé par le système. Fermer le navigateur peut interrompre l’enregistrement.
- **Reprise** : seuls les fragments effectivement capturés et sauvegardés peuvent être récupérés. IndexedDB dépend du profil du navigateur et de son quota ; sa copie temporaire n’est pas chiffrée par Memora.
- **Ressources** : durée, taille d’import, mémoire et espace disque sont bornés. Le fonctionnement local ne promet ni simultanéité illimitée, ni latence constante.
- **Validation** : microphone physique, Safari/iOS, veille réelle, réunion naturelle de deux heures, charge multiutilisateur, accessibilité exhaustive et délivrabilité externe ne sont pas couverts par les seules recettes synthétiques.
- **Production** : exposition publique, exploitation, sauvegardes avec restauration éprouvée et qualification de charge demandent un travail dédié. Le build Next.js optimisé n’est pas, à lui seul, une qualification de production.

## Documentation complémentaire

- [Guide Memora](docs/MEMORA.md) : règles de gestion, IA, modèles, configuration, partage, reprises et limites détaillées.
- [Index des scripts](scripts/README.md) : commandes quotidiennes, maintenance et outils de diagnostic.
- [Exemple de configuration](.env.memora.example) : variables documentées sans secrets.
- [Docker Compose](docker-compose.yml) : services, ports, volumes et contrôles de santé.
- [Contrat OpenAPI](backend/openapi.json) : contrat versionné de l’API ; la documentation interactive est disponible sur l’API locale démarrée.
