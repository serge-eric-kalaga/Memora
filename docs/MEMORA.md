# Memora — guide local Docker et PostgreSQL

Les notes de travail et preuves historiques dans `.agents/` sont locales et non versionnées. Les outils de vérification et leurs prérequis sont décrits dans [l’index des scripts](../scripts/README.md).

## Démarrage quotidien

```sh
./scripts/memora-start.sh
./scripts/memora-status.sh
./scripts/memora-stop.sh
```

Ces commandes utilisent Docker Compose. L’application est à [127.0.0.1:3000](http://127.0.0.1:3000), l’API à [127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) et les emails locaux à [127.0.0.1:8025](http://127.0.0.1:8025). PostgreSQL écoute uniquement sur127.0.0.1:5433 pour la maintenance locale ; son mot de passe est privé. L’arrêt conserve les volumes. **Ne pas utiliser `down -v` sur la stack Memora** : cela supprimerait les données PostgreSQL.

Architecture : conteneurs `postgres` (PostgreSQL16), `backend` (FastAPI), `worker` (processus durable indépendant), `frontend` (Next.js standalone) et `mailpit` (capture SMTP). Les comptes sont dans le schéma PostgreSQL `public`, les réunions/versions/partages/tâches dans `memora`. Les audios restent dans `.memora/data/`, monté au même chemin absolu ; les photos de profil restent dans `backend/static/uploads/`. Changer l’emplacement du projet nécessite de régénérer la configuration et vérifier les chemins.

Sur macOS Apple Silicon, MLX/ECAPA utilisent les bibliothèques et modèles natifs existants, via un compagnon authentifié lié à127.0.0.1:8091 ; le script de démarrage le gère. Ce calcul reste sur le Mac car MLX/GPUApple n’est pas pris en charge dans les conteneurs Linux. Ollama reste indépendant et n’est jamais réinstallé ou arrêté. Les conteneurs appellent l’hôte avec `host.docker.internal` ; aucun fournisseur IA externe n’est utilisé.

## Première installation ou migration depuis SQLite

Prérequis : Docker Desktop actif, Node/npm et Python3.12/uv pour les outils natifs, Ollama existant, modèles locaux documentés plus bas. Prévoir de la place pour les images Docker, les modèles et les sauvegardes. Sur une installation déjà préparée, ne pas réinstaller les modèles.

`./scripts/memora-install.sh` prépare les dépendances natives verrouillées, les modèles requis et les bases SQLite de bootstrap ; il n’est pas le lanceur quotidien. Après la migration, ne plus utiliser SQLite comme base applicative. Les fichiers `.memora/backend.env` restent la configuration du moteur natif et la source des clés applicatives existantes ; le générateur Docker les conserve afin de garder mots de passe, sessions et emails chiffrés compatibles.

Pour migrer une installation existante, arrêter l’ancienne API et attendre la fin de tout enregistrement/traitement. L’importeur refuse un worker actif, une réunion en capture ou une tâche active. Puis :

```sh
python3 scripts/memora-docker-env.py
docker compose --env-file .memora/docker/compose.env build
docker compose --env-file .memora/docker/compose.env up -d --wait postgres
backend/.venv/bin/python scripts/memora-import-postgres.py --apply
./scripts/memora-start.sh
```

Le générateur écrit des fichiers privés0600 dans `.memora/docker/`, sans secret dans le dépôt. L’importeur sauvegarde les deux SQLite avec leur API de sauvegarde, crée les schémas et migrations PostgreSQL, importe les données dans une transaction puis compare le contenu complet de chaque table. IDs, UID de compte, hashes de mots de passe, partages, versions, corrections, tâches et dates sont conservés ; les séquences sont avancées pour les futurs comptes. Une cible occupée est refusée, jamais écrasée. Les SQLite et leurs sauvegardes sont conservés comme point de retour explicite ; le lancement Docker n’y écrit pas. Les empreintes de tables et de médias restent exclusivement dans `.memora/docker/import-complete.json` privé. Une marque PostgreSQL est vérifiée au lancement pour refuser une base recréée après perte de volume.

Pour reconstruire après changement du code : `docker compose --env-file .memora/docker/compose.env build`, puis `./scripts/memora-start.sh`. Ne pas redémarrer pendant une capture ; les tâches durables reprennent après interruption. Les nouvelles images doivent être reconstruites : aucun montage du code source n’est nécessaire au fonctionnement. Les outils natifs restent nécessaires pour l’inférence et les recettes ; leurs environnements ne sont jamais copiés dans les images.

## Vérification Docker isolée

`backend/.venv/bin/python scripts/memora-verify-docker.py` crée une stack indépendante avec comptes, PostgreSQL, stockage, SMTP et ports réservés aux tests, puis exécute le navigateur avec un microphone factice. Définir `PLAYWRIGHT_CHROMIUM_EXECUTABLE` si nécessaire. Il retire uniquement ses conteneurs/volumes temporaires et ne lit pas les enregistrements de l’application. Les poids locaux et Ollama sont partagés pour l’inférence. Voir `.agents/testing.md` pour les preuves et limites réellement observées.

## Essayer le parcours

1. Se connecter et créer une réunion en choisissant **Importer un audio**. Les WAV synthétiques de `backend/test/fixtures/memora/` peuvent être utilisés sans données personnelles.
2. Choisir le fichier ; le transfert affiche sa progression et les fragments confirmés. La validation réelle du contenu précède la transcription puis l’analyse serveur. On peut quitter la page une fois la finalisation acceptée.
3. Consulter le rapport, la transcription et l’audio. Une citation ouvre le passage autorisé et positionne la lecture.
4. Poser une question dans le chat. Les sources appartiennent uniquement à cette réunion ; une information absente doit être signalée.
5. Corriger un passage ou un nom. Une nouvelle version est créée, l’ancienne reste consultable et le rapport est marqué à actualiser. Régénérer conserve les rapports précédents. L’historique du chat indique les versions anciennes.
6. Créer un partage ouvert ou protégé, choisir les contenus, l’édition et une expiration facultative. Ouvrir le lien dans une fenêtre privée pour vérifier l’accès sans compte. Révoquer puis réessayer.
7. Envoyer une invitation à des adresses synthétiques réservées, puis consulter la capture locale. Aucun email ne sort de cette machine.

Pour enregistrer, informer les participants puis cliquer volontairement sur **Enregistrer**. Le navigateur demande le microphone ; aucune capture n’est lancée au chargement. Pause suspend les nouvelles paroles ; Reprendre continue le même flux. Terminer sauvegarde les derniers fragments puis lance l’analyse. La durée affichée exclut la pause. Les essais automatisés utilisent exclusivement le microphone factice Chromium alimenté par un WAV.

La création propose **Français**, **Anglais** ou **Automatique/bilingue**. L’interface présélectionne sa langue ; l’API conserve `auto` par défaut pour les clients qui ne précisent rien. Ce choix guide la reconnaissance, sans garantir l’exactitude. La capture demande 128 kbit/s et des contraintes audio adaptées à la parole lorsque le navigateur les accepte ; le format et les réglages effectivement appliqués dépendent du navigateur.

**Retranscrire l’audio** demande confirmation puis crée une nouvelle version, conserve les corrections et rapports antérieurs dans leur historique, et lance l’analyse de la nouvelle source. L’audio doit encore être disponible et aucun autre traitement final ne doit être actif. Ce traitement nécessite les droits de modification et d’audio, y compris pour un invité. Il ne corrige pas automatiquement une réunion existante à l’insu de son auteur.

Les tâches conservent un checkpoint transactionnel après transcription et après rapport. Après arrêt du processus, elles reprennent la phase restante sans retranscrire une source déjà publiée ni dupliquer son rapport. Un ancien état de traitement sans tâche active devient relançable, en conservant les versions ; aucune transcription ou génération n’est lancée automatiquement pour le réparer.

Chaque régénération explicite de rapport peut produire une nouvelle révision même si la transcription n’a pas changé. Le frontend fournit un identifiant de requête ; son rejeu ne lance pas un second traitement. Une ancienne tâche terminée après une plus récente ne peut pas remplacer le résultat courant.

### Interruption et reprise

Les fragments MediaRecorder sont produits environ toutes les 10 secondes et découpés à 2 Mo au maximum. Ils sont enregistrés dans IndexedDB avant envoi. Un fragment n’est indiqué comme distant qu’après accusé de réception serveur. Le serveur contrôle séquence et SHA256, accepte un rejeu identique et refuse un contenu différent au même emplacement. Une interruption entre écriture du fichier et commit SQL est réconciliée avant le fragment suivant.

**Reprendre la sauvegarde** renvoie les fragments locaux non confirmés. Pour un import partiel, rechoisir le même fichier rejoue les fragments de manière idempotente. Un autre fichier est refusé si son contenu diffère. Après fermeture ou perte du microphone, les fragments présents peuvent être finalisés ; une nouvelle capture ne reprend pas arbitrairement un second flux incompatible dans le fichier existant.

La fermeture du navigateur, la mise en veille, le verrouillage mobile ou un quota IndexedDB peuvent empêcher la capture. Les données jamais capturées ou jamais sauvegardées ne sont pas récupérables. La copie IndexedDB temporaire n’est pas chiffrée par Memora et reste sur le profil du navigateur jusqu’à confirmation serveur ; utiliser un profil de confiance et garder la page ouverte en cas d’erreur de stockage. Le serveur peut purger l’audio à sa date de conservation ; cette politique ne prétend pas gérer les copies faites hors de l’application.

La transcription en direct est provisoire, obtenue après réception et traitement des fragments, pas mot à mot instantanément. Les aperçus longs analysent une fenêtre récente de 120 secondes tout en conservant les passages précédents disponibles ; la transcription finale relit l’audio complet. Aucune latence universelle n’est promise. À la limite configurée, la capture s’arrête, les fragments sont sauvegardés et l’utilisateur finalise le contenu disponible ; l’analyse ne prétend pas inclure la suite non enregistrée.

## Configuration et paramètres

`scripts/memora-env.py` crée `.memora/backend.env` avec secrets aléatoires, droits 0600 et dossier privé 0700. `.env.memora.example` décrit les variables sans secrets. Le mode local n’utilise pas les services ou bases des projets de référence ni la configuration Compose historique du template.

| Paramètre | Valeur initiale | Bornes et effet |
|---|---:|---|
| Durée maximale |120 minutes|1–240, snapshot à création ; arrêt capture et rejet audio trop long|
| Taille maximale audio |250 Mo|1–500 ; fragments backend ≤5 Mo, frontend ≤2 Mo|
| Conservation audio |30 jours|1–365 ; date fixée à création, purge par worker|
| Modification invitée |Désactivée|Administrateur autorise la capacité ; chaque lien doit ensuite l’accorder|
| Langue rapport/chat |Français|fr/en, snapshot à création|
| Email de disponibilité |Activé|Compte propriétaire avec email ; aucun participant supposé ajouté|
| Expiration partage UI |7 jours|Facultative ; backend maximum 366 jours|

Ce sont des valeurs initiales techniques réversibles, pas des arbitrages métier explicitement validés. Les modifications administratives sont historisées avec ancien/nouveau réglage et auteur ; elles concernent les nouvelles réunions. Elles ne raccourcissent pas silencieusement la conservation des réunions existantes. Un administrateur n’obtient pas l’accès aux réunions d’autres comptes.

Quotas locaux :20 créations/minute/compte,20 partages/minute/compte,6 analyses/minute/réunion,20 questions/minute/compte ou lien,20 tentatives erronées/minute/lien et origine réseau. Les appels réussis d’un partage protégé ne consomment pas le quota de mots de passe erronés. Les valeurs sont des protections techniques initiales. L’upload conserve au moins 512 Mo libres sur le volume ; cette garde ne garantit pas une capacité illimitée.

## IA locale et limites

- **Transcription directe, anglais et automatique/bilingue final : MLX Whisper0.4.3, modèle large-v3-turbo**, GPU Apple Silicon. Poids1,61Go de la [conversion MLX publique](https://huggingface.co/mlx-community/whisper-large-v3-turbo), révision épinglée et SHA256 officiel vérifié. Modèle original et MLX sous licence MIT. La [détection de parole Silero](https://github.com/snakers4/silero-vad/blob/master/LICENSE), MIT, utilise les assets ONNX déjà inclus dans Faster Whisper : aucune API audio externe. Chaque portion vocale conserve ses positions dans l’audio original ; le modèle est libéré avant les autres inférences. PyAV décode sans exécutable FFmpeg système.
- **Français final : Whisper large-v3-turbo via MLX**, avec `language="fr"` et `task="transcribe"`. Ce conditionnement respecte le choix explicite de langue, sans garantir chaque mot. Parakeet TDT0.6Bv3 reste une option locale expérimentale : plus précis sur notre réserve française, mais son décodeur ne permet pas de forcer le français. Ses poids vérifiés sont conservés ; aucun modèle supprimé.
- **Alternative CPU : Faster Whisper1.2.1/base**, MIT, environ148Mo, int8/4threads. Gardé pour comparaison et configuration explicite ; son français complexe est moins précis dans les essais. Aucun basculement silencieux après une erreur MLX.
- **Analyse/chat : gemma4:e4b déjà présent dans Ollama**, environ6,1Gio de poids locaux, [modèle Ollama](https://ollama.com/library/gemma4:e4b), [licence Apache2.0 du modèle officiel](https://huggingface.co/google/gemma-4-E4B-it). Sortie JSON validée côté serveur, température0, contexte16384tokens. Sélection après reproduction d’une reformulation trop affirmative avec Qwen et comparaison sur décisions futures, responsables, dates, chat et longues sources. Aucun nouveau modèle Ollama téléchargé, fournisseur payant ou API externe de remplacement.
- **Embeddings : aucun index externe requis.** Chaque question parcourt les lots autorisés de la version courante puis réduit les réponses pertinentes. La correction change immédiatement la source ; aucun ancien index ne reste actif.
- **Intervenants : séparation locale volontaire, sans identification nominative.** Un traitement optionnel regroupe les voix en étiquettes numérotées, avec abstention pour les segments multivoix. Aucun nom ni identité biométrique n’est déduit. Un renommage peut porter sur un segment dans l’éditeur, ou sur tous les passages d’une même étiquette depuis « Gérer les intervenants ».

Configuration centralisée : `MEMORA_OLLAMA_URL`, `MEMORA_MODEL`, `MEMORA_ASR_ENGINE`, `MEMORA_LIVE_ASR_ENGINE`, `MEMORA_FRENCH_ASR_ENGINE`, `MEMORA_PARAKEET_MODEL_PATH`, `MEMORA_MLX_MODEL_PATH`, `MEMORA_ASR_MODEL` et `MEMORA_MODEL_DIR`. `memora-env.py` recommande, pour une nouvelle installation Apple Silicon native, MLX Whisper Turbo pour le français final, le direct, l’anglais et le bilingue. Les autres plateformes utilisent Faster Whisper CPU. Une configuration existante est conservée exactement ; les nouveaux modèles ne sont pas activés silencieusement dans un environnement déjà créé. `memora-install.sh` prépare le moteur réellement configuré. Préparation reproductible MLX :

```sh
backend/.venv/bin/python scripts/memora-download-mlx.py
backend/.venv/bin/python scripts/memora-download-mlx.py --check-only
ollama list
```

Sur cette installation, `MEMORA_ASR_ENGINE=mlx-whisper`, `MEMORA_LIVE_ASR_ENGINE=mlx-whisper` et `MEMORA_FRENCH_ASR_ENGINE=mlx-whisper` constituent la configuration retenue. Le chemin `MEMORA_MLX_MODEL_PATH` désigne le modèle local vérifié. Aucun modèle absent n’est téléchargé implicitement pendant une réunion ; une erreur laisse la réunion relançable. Le téléchargeur reprend les fragments, épingle provenance/taille/SHA256 et vérifie un modèle déjà présent sans le réécrire ni le télécharger de nouveau.

En mode automatique, la langue dominante est détectée indépendamment dans chaque portion vocale séparée par le VAD (pause300ms, marge200ms). L’interface indique cette portée et l’absence de confiance chiffrée. Une alternance sans pause ou une portion très courte reste difficile ; VAD peut manquer une voix faible. Le mode Anglais guide Whisper ; le mode Français conditionne explicitement Whisper sur `fr`, en transcription et non en traduction. Ce traitement n’identifie pas les personnes.

Validation historique de Whisper Turbo, avant la nouvelle route française : les sept cas synthétiques de validation conservent le bilingue sans traduction et n’ajoutent aucun texte sur silence/bruit. Sur le français complexe, WER après normalisation numérique explicite17,5% avec base contre2,5% avec MLX ; l’écart restant correspond à « M. »/« Monsieur ». Le bilingue garde une différence « Mémora »/« Memora » ; Python et anglais sont exacts sur ces exemples. Quinze minutes synthétiques ont été transcrites en54,29s, avec début et phrase finale retrouvés, deux langues et pic mémoire processus d’environ2,83GiB. Ces résultats ne garantissent pas l’exactitude sur une voix ou une réunion naturelle particulière. Méthode et preuves : validation ASR (note locale non versionnée : `.agents/handoffs/asr-final-validation.md`).
Ne télécharger un modèle Ollama supplémentaire que si nécessaire après contrôle licence, taille et mémoire. Ici aucun téléchargement Ollama n’a été nécessaire : Gemma et Qwen étaient déjà présents. Sur une autre machine sans Gemma, `ollama pull gemma4:e4b` doit être une préparation explicite après vérification de l’espace, de la licence et de la RAM, pas un téléchargement pendant une réunion. Ne pas sélectionner un modèle cloud. Les besoins du modèle s’ajoutent aux dépendances et audios.

Gemma a conservé la modalité future sur les corpus courts et longs examinés. Rapport3lots41,241s et chat18,693s, source finale conservée ; absence/injection testées aussi. Mémoire libre système minimale échantillonnée19% pendant les probes sur cette machine16Gio, puis récupération après déchargement : charge supérieure à Qwen, sans promesse sur une machine déjà saturée. La classification d’une discussion en « action » reste perfectible ; aucune certification d’exactitude sémantique universelle. Les citations valides ne suffisent pas à prouver une paraphrase : relecture humaine des décisions et engagements nécessaire. Preuves : comparaison modale (note locale non versionnée : `.agents/handoffs/report-modality-comparison.md`), validation Gemma (note locale non versionnée : `.agents/handoffs/gemma-full-validation.md`). Whisper small a été essayé, puis écarté comme défaut : il a omis une partie anglaise du corpus testé. Ses fichiers locaux de comparaison ne sont pas versionnés.

Le moteur Faster Whisper renseigne une langue par segment ; les anciens résultats MLX sans VAD indiquent une langue dominante initiale et les nouveaux une estimation par portion vocale. L’interface distingue aussi la langue choisie explicitement. Ces étiquettes ne prouvent pas la langue de chaque mot. Accents, noms propres, bruit et transitions restent imparfaits : contrôler et corriger les passages importants puis régénérer. Les indicateurs d’incertitude ne garantissent pas l’absence d’erreur.
Les longues sources sont traitées par lots bornés et conservent leurs références, locuteurs et horodatages. Les fragments de phrase adjacents sont réunis avant le découpage des lots ; les citations reviennent toujours aux segments originaux. Une date dite dans une autre phrase ne suffit pas à attribuer une échéance à une action ; le chat utilise une réduction hiérarchique sans sélectionner silencieusement seulement le début. Cela ne constitue pas un benchmark de deux heures ni une garantie de qualité universelle. Ollama reçoit `truncate:false` et `shift:false` : un contexte trop grand est refusé explicitement plutôt que coupé silencieusement. Les appels d’inférence ASR/Ollama sont sérialisés dans le processus applicatif, avec libération du verrou entre lots et après erreur. Les caches d’Ollama peuvent se libérer quelques instants après une réponse malgré keep_alive=0 ; cette garde ne contrôle pas les autres applications et ne garantit pas une isolation matérielle. Le proxy chat utilise un délai configurable `MEMORA_CHAT_TIMEOUT_MS` (environnement serveur frontend),600000ms par défaut, borné1000–1800000ms ; REST conserve120000ms. Un dépassement504 informe que le calcul backend peut encore finir : consulter l’historique avant de relancer. Le texte source et la question sont des données non fiables pour le modèle ; ils ne déclenchent jamais de commandes, emails ou actions extraites.

Si Docker est retenu ultérieurement, `localhost` du conteneur ne désigne pas l’hôte : utiliser une connexion privée appropriée telle que `host.docker.internal:11434`, puis vérifier depuis ce conteneur. Aucun service Docker n’est nécessaire ni utilisé par le parcours local livré. Ollama n’est pas exposé publiquement.

## Partage, données et effets externes

Les autorisations sont vérifiées pour chaque réunion, transcription, rapport, audio et question. Les liens sont aléatoires ; le mot de passe est conservé sous hash scrypt. L’email ne définit jamais une liste nominative d’accès : un lien peut être retransmis. Si le transcript est masqué mais le chat et le rapport permis, le chat ne reçoit que le rapport visible et ne divulgue pas de citations du transcript.

L’éditeur invité doit avoir un droit explicite, l’activation administrative actuelle et un nom déclaré ; la session aléatoire et l’auteur déclaré sont tracés. Ce mécanisme ne prouve pas son identité civile. Il ne permet ni repartage, ni archivage, ni suppression. Deux corrections basées sur la même ancienne version ne s’écrasent pas : la seconde reçoit 409.

Les corps d’emails en file sont chiffrés avec Fernet, clé dérivée de `SECRET_KEY`, déchiffrés en mémoire puis effacés après remise SMTP. L’envoi conjoint du mot de passe est possible après choix explicite ; le message livré est une copie du destinataire qui ne peut pas être rappelée. Les destinataires reçoivent des messages séparés. Les emails déjà envoyés ne sont pas renvoyés par une reprise normale ; les échecs disposent d’une reprise ciblée. Un crash exactement entre acceptation SMTP et écriture de l’état peut néanmoins provoquer une redélivrance : SMTP ne fournit pas une transaction exactement-une-fois.

Mailpit capture les messages dans son volume local et permet leur inspection. Le serveur natif `memora-mail-capture.py` reste utilisé uniquement par les recettes SQLite isolées. La réception locale vérifie la composition, pas la délivrabilité en production ni la lecture par un destinataire.

**Archive** change le classement et conserve les contenus et les liens actifs. **Supprimer définitivement** demande confirmation, retire l’accès, supprime versions/chat/liens/notifications et fichiers audio locaux ainsi que les emails encore en file. La purge de l’audio seul arrive à sa date de conservation ; transcription, rapports et chat sont conservés jusqu’à suppression explicite. Aucun backup automatique n’est annoncé. Des sauvegardes manuelles, emails reçus et téléchargements demeurent des copies indépendantes.

La suppression d’un compte pose d’abord une barrière liée à son identité permanente. Les accès invités et les publications de traitements tardifs sont bloqués ; fichiers et données associés sont ensuite supprimés. En cas d’erreur de fichier, le compte reste présent pour permettre une nouvelle tentative, et la barrière continue de protéger ses réunions. Les anciennes sauvegardes et emails capturés restent des copies indépendantes.

Le stockage audio/PostgreSQL n’est pas chiffré intégralement par l’application ; il est protégé par les permissions locales et les contrôles d’accès applicatifs. TLS, sauvegardes/restauration d’exploitation, rétention légale, supervision multi-instance et qualification de sécurité nécessitent un travail avant production. Le worker local est mono-instance avec verrou POSIX ; il ne prétend pas remplacer une infrastructure de traitement distribuée.

## Tests et preuves

```sh
backend/.venv/bin/python scripts/memora-test.py
cd frontend
npm run lint
npm run typecheck
npm run api:check
npm run build:memora
# Installer Chromium de Playwright si absent :
npx playwright install chromium
cd ..
backend/.venv/bin/python scripts/memora-verify-docker.py
backend/.venv/bin/python scripts/memora-e2e-api.py
backend/.venv/bin/python scripts/memora-resilience.py
# Reprise après arrêt brutal : uniquement worker/base/audio synthétiques jetables
backend/.venv/bin/python scripts/memora-verify-worker-resume.py
```

Pour la recette intégrée finale entièrement séparée de l’application utilisée :

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE="/chemin/vers/chromium" \
  backend/.venv/bin/python scripts/memora-verify-isolated.py --timeout 2400
```

Ce lanceur crée des comptes, bases, stockage, secrets et capture SMTP jetables, démarre une API et un frontend sur d’autres ports locaux, puis exécute la recette API, le navigateur et l’audit UI. Il arrête uniquement ses processus et supprime son répertoire temporaire en sortie. Les modèles sur disque restent partagés en lecture et Ollama est partagé pour l’inférence locale ; les temps peuvent donc varier si l’application est utilisée simultanément. `--smoke-only` vérifie seulement migrations, authentification et proxy, sans valider le parcours complet. Les artefacts portent le préfixe `isolated-`.

Les tests backend utilisent des bases et un stockage temporaires ; SMTP est neutralisé dans les tests isolés. Les scripts d’intégration utilisent seulement le compte et les fichiers synthétiques locaux. La recette navigateur alimente le microphone factice Chromium par un WAV ; aucun micro physique n’est sollicité. `PLAYWRIGHT_CHROMIUM_EXECUTABLE` permet de choisir un Chromium déjà installé.

Résultats datés et limites : .agents/testing.md (note locale non versionnée : `.agents/testing.md`), traçabilité (note locale non versionnée : `.agents/requirements.md`), recette API réelle (note locale non versionnée : `.agents/handoffs/e2e-api.md`), recette navigateur (note locale non versionnée : `.agents/handoffs/browser.md`). Ne pas confondre ces preuves avec une validation Safari/iOS, une veille physique, une réunion de deux heures ou une capacité de production.

## Mémoire et Git

`AGENTS.md` pointe vers `.agents/README.md` puis `.agents/memory/state.md`. Les notes synthétiques, décisions, carte du code, exigences, plan et preuves de recette sont pérennes et versionnables. Les logs et captures de `.agents/logs/`, les modèles, bases, audios utilisateur, secrets, sessions et emails de `.memora/` restent exclus de Git. Les seules fixtures audio versionnées sont synthétiques. Les références DBChat, ServicePublic et AI_Agora ont été consultées sans modification et sans copie de code faute de licence explicite vérifiée.


### Correctif du choix français et lisibilité

La configuration retenue revient à **Whisper Turbo conditionné français** : Parakeet ne peut imposer la langue, malgré un meilleur WER sur cette réserve. Le symptôme de traduction signalé n’a pas été reproduit sur les quatre cas synthétiques de diagnostic (12 inférences). Aucun enregistrement personnel supplémentaire n’a été retraité. Comparaison sur 24 profils français existants : WER numérique Turbo15,52%, Full15,71%, Parakeet6,70% ; propre Turbo/Full10,34%. Full ne justifie donc pas son surcoût global. Ce corpus ne démontre pas90% de précision générale. Diagnostic (note locale non versionnée : `.agents/handoffs/asr-language-drift-diagnostic.md`) et comparaison conditionnée (note locale non versionnée : `.agents/handoffs/whisper-forced-fr-reserve-v3.md`). Les anciennes transcriptions ne sont pas modifiées automatiquement : choisir Français puis « Retranscrire l’audio » crée une nouvelle version.

Pendant une capture, la forme d’onde, le niveau et la crête proviennent du flux effectivement enregistré. Pause, silence prolongé, saturation et entrée déconnectée ont des états distincts. Le visualiseur ne demande pas une seconde autorisation et ne prouve pas la sauvegarde : les accusés des fragments restent séparés. La transcription dispose d’une hauteur bornée et d’un défilement interne ; titre et correction restent visibles. Les sources du résumé et des sujets sont repliées ; décisions, actions et questions ouvertes gardent leurs citations directes.

## Recherche et validation de précision du 25 octobre

La recherche primaire (note locale non versionnée : `.agents/handoffs/accuracy-research-services.md`) compare les méthodes documentées de Read, Otter, Fireflies, Deepgram et AssemblyAI. Un vocabulaire spécialisé peut aider, mais nos essais de lexique global ont remplacé des noms voisins et supprimé du français. Le remplacement global par Whisper large-v3 a également régressé en bilingue. Ces réglages ne sont pas activés. Température zéro et best_of5 n’ont pas amélioré les hypothèses testées. Aucun correcteur LLM ne réécrit silencieusement la transcription.

La politique historique évaluée ci-dessous choisissait **Parakeet TDT 0.6B v3 pour le français final**, et conserve **Whisper Turbo pour le direct, l’anglais et l’automatique/bilingue**. Parakeet ne force pas la langue : le choix français sélectionne le moteur ; la langue détectée reste `unknown`, affichée « Langue non déterminée ». Le fournisseur n’expose pas de confiance calibrée : les avertissements prudents ne mesurent pas un taux d’erreur.

| Réserve synthétique v3 historique | WER numérique Turbo | Route Parakeet optionnelle |
|---|---:|---:|
| Audio propre, toutes langues | 6,07% | 4,05% |
| Français propre | 10,34% | 4,60% |
| Anglais propre | 4,55% | 4,55% |
| Alternance propre | 2,78% | 2,78% |
| Bruit20 / bruit10 | 9,31% / 15,38% | 4,45% / 10,93% |
| Opus / faible volume / échos | 6,88% / 12,96% / 12,15% | 4,05% / 9,72% / 10,93% |

12 sources figées avant inférence, six conditions et deux négatifs : 148 traitements comparés, sans retrait de cas difficile. Les conditions d’une même source ne sont pas des voix indépendantes. Les sondes critiques propres passent de 27/30 à 28/30. Protocole complet (note locale non versionnée : `.agents/handoffs/accuracy-reserve-v3.md`). Ce WER applique une normalisation numérique publiée ; le WER strict est conservé séparément. Ces scores ne prouvent pas une précision universelle de 90%, ni celle d’une voix naturelle particulière.

Le test français de 95 secondes (note locale non versionnée : `.agents/handoffs/accuracy-long-fr.md`) traverse quatre fenêtres : 4,21% de WER numérique, sans perte de bloc ni doublon détecté. Soraya/Karim restent mal transcrits : les noms et responsables doivent être relus. Les deux chaînes réelles ASR → rapport (note locale non versionnée : `.agents/handoffs/asr-analysis-chain-real.md`) conservent six faits centraux et les responsables/échéances attendus ; une qualification trop forte « décidé » subsiste dans un résumé. La copie personnelle expressément autorisée reste privée et inchangée ; sa référence reformulée ne permet aucun pourcentage fiable.

### Configuration et reproduction

Dans `.memora/backend.env` :

```sh
MEMORA_ASR_ENGINE=mlx-whisper
MEMORA_LIVE_ASR_ENGINE=mlx-whisper
MEMORA_FRENCH_ASR_ENGINE=parakeet-mlx
MEMORA_PARAKEET_MODEL_PATH=/chemin/absolu/Memora/.memora/models/parakeet-v3
```

Une valeur française vide conserve le moteur principal. La route ne concerne que les transcriptions finales explicitement françaises. L’ancienne option `MEMORA_MLX_FR_MODEL_PATH` ne concerne que le décodeur Whisper et reste expérimentale : gains sur parole propre mais régressions sous bruit/échos, donc aucun défaut recommandé. Aucun enregistrement existant n’est retraité automatiquement.

Préparation explicite : `backend/.venv/bin/python scripts/memora-download-parakeet.py --target /chemin/distinct`, puis `--check-only`. Conversion `mlx-community/parakeet-tdt-0.6b-v3`, révision `ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15`, poids2,508Go et assets épinglés, licence CC-BY-4.0 avec attribution NVIDIA/conversion conservée. Dépendance Darwin ARM64 `mlx-audio==0.6.1` verrouillée ; `uv sync --project backend --frozen`. Le chargement utilise un chemin local vérifié, aucun code Python distant ni téléchargement pendant une réunion. Intégrité complète au premier chargement, cache invalidé après modification de fichier ; les échantillons non finis et repères temporels invalides sont refusés.

Recette isolée :

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE="/chemin/vers/Chromium/installé" \
  backend/.venv/bin/python scripts/memora-verify-isolated.py \
  --asr-engine mlx-whisper --french-asr-engine parakeet-mlx --timeout 2400
```

`--french-asr-engine disabled` impose le moteur principal au français pendant une comparaison ; `inherit` conserve la configuration. Chromium1248 a été utilisé ici. L’import français, son rapport et la correction de locuteur sont vérifiés par API et navigateur, en plus des parcours bilingues/directs. Résultat et empreinte du code au moment des tests : testing.md (note locale non versionnée : `.agents/testing.md`). Les preuves historiques nécessitent leurs snapshots locaux explicitement nommés ; un nouveau benchmark utilise par défaut l’adaptateur versionné actuel et enregistre son SHA.

### Analyse : changements et limites mesurées

Les prompts distinguent proposition, décision, engagement et réalisation ; les responsables et échéances absents ne sont pas inventés. Sur la petite réserve courte, 17/18 affirmations retenues sont conformes (94,44%), et 8/8 faits attendus sont retrouvés. Ce score ne couvre pas toutes les réunions ni toutes les catégories.

Pour plusieurs lots, le moteur conserve les résumés chronologiques et vérifie séparément l’existence d’une tâche, puis les annulations/remplacements/réponses ultérieurs. Les preuves sont des IDs contraints : le backend récupère les passages originaux. Une suppression insuffisamment étayée est refusée ; le fait reste marqué « À vérifier ». Une source très volumineuse qui ne peut être réduite correctement échoue explicitement plutôt que d’être tronquée silencieusement.

La version finale V12 satisfait les cinq vérifications ciblées sur les maps réels conservés, puis un cas long complet (trois lots,94,688s). Ce ne sont pas cinq analyses complètes ni une réserve aveugle : ces cas ont servi au diagnostic après leurs échecs, tous conservés. Un doublon de décision « À vérifier » demeure dans un cas. Preuves et limites V12 (note locale non versionnée : `.agents/handoffs/analysis-reconciliation-v12-final.md`).

### Activation et vérifications finales

Activation locale le25/10 après sauvegarde privée de configuration, zéro traitement actif et aucune capture récente : services redémarrés, HTTP200 sur UI3000/API8080/capture8025/Ollama11434. Comptes et réunions conservés ; aucun enregistrement utilisateur retraité automatiquement. Pour essayer : ouvrir http://127.0.0.1:3000, sélectionner Français pour une nouvelle réunion, ou choisir volontairement Français puis « Retranscrire l’audio » sur une réunion existante. L’opération conserve les anciennes versions ; vérifier les noms puis régénérer après correction.

- Backend final V12 :242 tests réussis,3 ignorés Redis,1 avertissement existant ; Ruff62 fichiers conformes.
- Préparation/configuration/téléchargeurs :48 tests réussis ; frontend7 tests de libellés, lint, types et build réussis.
- Recette complète isolée :55 contrôles réussis (35 API,13 navigateur,7 audit),177,13s ; modèles réels, capture microphone factice, données synthétiques. Cette recette a chargé V11 ; les modifications V12 concernent la fusion multi-lots et sont vérifiées séparément ci-dessus. Les branches courtes et ASR sont inchangées.
- Panne réelle du modèle puis restauration :2 contrôles réussis, source conservée et rapport produit sans réimport.

La première tentative navigateur a échoué avant lancement sur un ancien chemin Chromium ; elle reste consignée. Aucun résultat de test ne prouve le microphone physique, Safari/iOS, une réunion naturelle de deux heures, la charge multiutilisateur ou une aptitude à la production. Commandes et résultats datés (note locale non versionnée : `.agents/testing.md`).

## V1.1 — contrôle audio, correction et relecture humaine

Le contrôle microphone est proposé avant la capture. Il s’active uniquement au clic, permet de choisir une entrée, affiche le niveau et signale silence ou saturation. Un échantillon de dix secondes maximum reste dans l’onglet pour réécoute ; il n’est pas envoyé au backend. Arrêter le test libère le microphone ; un test actif bloque le démarrage concurrent d’une réunion. Le contrôle s’arrête automatiquement après une minute.

Dans Transcription, le lecteur surligne le passage actif. La barre permet de revenir de trois secondes, changer de passage, ralentir la lecture et écouter le passage sélectionné en boucle. Un clic sur un autre repère annule cette boucle. Les raccourcis Alt+flèches et Alt+Espace s’appliquent lorsque la barre est focalisée, sans intercepter la saisie dans l’éditeur. Une correction affiche une comparaison avant/après ; son enregistrement conserve la version précédente et rend le rapport périmé.

Les actions et décisions proposent une **validation humaine séparée du résultat IA** : proposé, confirmé, annulé ou à vérifier. Le texte, le responsable et l’échéance peuvent être corrigés ; une valeur responsable/échéance vide retire explicitement l’attribution. Le résultat IA reste immuable au-dessus. Chaque validation conserve auteur, date et révision. Les mises à jour concurrentes ou portant sur un ancien rapport sont refusées ; les validations restent consultables et deviennent périmées après correction de source. Le chat continue d’utiliser la transcription autorisée, il ne présente pas une correction humaine du rapport comme une phrase prononcée.

Un invité peut réviser le rapport si le partage lui accorde rapport+édition et si l’administration autorise l’édition invitée. Il n’a pas besoin d’un compte ni d’un accès à la transcription pour cette relecture. Corriger/renommer la transcription exige transcription+édition ; séparer les voix exige également l’accès audio. Révocation et droits courants sont recontrôlés côté serveur.

### Intervenants et séparation locale

« Gérer les intervenants » permet de renommer tous les passages portant la même étiquette. Pour une étiquette inconnue, l’utilisateur doit confirmer qu’il a vérifié qu’ils appartiennent tous à la même personne. Un groupe inconnu n’est pas automatiquement une seule voix.

La séparation locale est une action volontaire après transcription. Elle utilise des embeddings de voix appris Resemblyzer0.1.4, le VAD Silero existant et un clustering acoustique CPU ; elle ne repose pas sur une alternance des lignes. Elle crée des étiquettes numérotées, **aucune identité réelle**. Un segment contenant plusieurs groupes de voix reste non attribué, même si l’un est majoritaire. L’audio, le texte, les IDs et les horodatages d’origine restent inchangés ; une nouvelle version de transcription est publiée et le rapport doit être régénéré après relecture. Les anciens noms restent dans l’historique. Le job est idempotent et un résultat tardif ne remplace pas une correction plus récente.

Modèle Apache-2.0 de17,09Mo, provenant du package officiel épinglé, SHA256 `39373b86598fa3da9fcddee6142382efe09777e8d37dc9c0561f41f0070f134e`. Préparation entièrement locale depuis le package installé :

```sh
backend/.venv/bin/python scripts/memora-prepare-diarization.py
backend/.venv/bin/python scripts/memora-prepare-diarization.py --check-only
```

`MEMORA_DIARIZATION_MODEL_DIR` peut désigner un autre répertoire local préparé. `MEMORA_DIARIZATION_CPU_THREADS` borne le traitement de1à8threads, défaut2 ; le réglage PyTorch précédent est restauré même après erreur. L’installateur prépare ces poids si Resemblyzer est installé. Les dépendances sont actuellement conditionnées à macOS Apple Silicon, plateforme validée ; aucun téléchargement CUDA Linux disproportionné n’est imposé. `setuptools` est borné à une version80 compatible avec `pkg_resources`, requis par une dépendance ; le verrou conserve les autres versions existantes.

Les essais synthétiques couvrent deux/trois voix, retours de parole, FR/EN, gain/bruit et silence. La réserve à nouvelles voix retrouve2/2/3groupes et attribue18/18segments ; DER7,57% et8,10% sur les cas propres,12,37% avec gain/bruit. Le DER mesure une erreur temporelle de séparation, pas un taux d’erreur de transcription ni une précision d’identification. Les références utilisent une grille20ms et l’énergie des pistes TTS ; aucune généralisation aux accents/voix naturelles. Les paroles simultanées ne sont pas séparées, les voix proches peuvent être fusionnées, le bruit et les voix faibles peuvent fragmenter les groupes. La limite technique de deux heures n’est pas une preuve de qualité sur une réunion naturelle de cette durée. Protocole et limites (note locale non versionnée : `.agents/handoffs/diarization-local-v1.md`).

Migration domaine007 additive : tables `report_reviews` et `transcript_edits`. Elle ne réécrit ni transcription ni rapport existant. L’import PostgreSQL conserve ces tables ; les migrations domaine additives sont vérifiées au démarrage du worker sous verrou. Les migrations des comptes restent Alembic. Pour le bootstrap SQLite seulement, le script de migration natif vérifie le stockage et sauvegarde les sources. Ne pas substituer une autre base par modification improvisée de variables.


Validation V1.1 finale :284testsbackend/48préparation/16frontendunit réussis ; intégration en phases isolées41API+19navigateur+9auditUI, plus10contrôlesmicroAPIssynthétiques et2contrôles de codecChromium réel surentrée factice (échantillon lu, aucuneémission). Lint/types/build/OpenAPI/SDK etRuff conformes. Les trois interruptions de recettes et leurs correctifs sont conservés, voir .agents/testing.md. Services locaux activés après migration007, empreintes sources préservées. Ces résultats ne prouvent pas microphysique/Safari/iOS/conversationnaturelle ni production.


## Enregistrement en arrière-plan et protection contre la veille

L’onde représente un historique de pics audio réels défilant de droite à gauche. La pause fige cet historique, la reprise le prolonge ; aucun chiffre technique n’est affiché. Le niveau reste disponible uniquement aux technologies d’assistance.

Changer d’onglet ne déclenche aucune pause ni arrêt du MediaRecorder. L’application demande un fragment supplémentaire lors des transitions de visibilité, poursuit la sauvegarde progressive et signale un arrêt inattendu. Garder le navigateur ouvert : fermer la page ou changer de réunion peut arrêter la capture, avec avertissement avant de quitter. L’affichage animé peut être suspendu en arrière-plan sans suspendre le MediaRecorder.

Sur ce Mac avec backend natif local, une protection temporaire `/usr/bin/caffeinate -i -t 120` empêche la **veille automatique inactive du système**, pendant capture ou pause. Le frontend renouvelle le bail toutes30s ; un seul bail par compte, authentification propriétaire et état de capture vérifiés. Fin/démontage/arrêt serveur libèrent la protection ; en cas de disparition du client elle expire sans renouvellement. Aucun réglage d’alimentation permanent, blocage du verrouillage ou maintien forcé de l’écran. Sur une autre plateforme, dans Docker ou pour un navigateur distant, cette protection native n’est pas annoncée ; le Screen Wake Lock facultatif ne maintient l’écran éveillé que tant que la page est visible.

**Une vraie veille forcée, un capot fermé ou un système suspendu peuvent couper le microphone. La capture pendant ces états n’est pas garantie.** Les navigateurs peuvent aussi retarder les fragments au verrouillage. La protection empêche la veille automatique ; elle ne transforme pas une application web en enregistreur indépendant du système. Sources techniques : [Screen Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API), [MediaRecorder et fragments différés](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event). Aucun service worker ni son silencieux artificiel n’est utilisé pour contourner les restrictions du navigateur.


## Intervenants numérotés automatiquement

Pour les réunions créées après cette mise à jour, la transcription finale est suivie d’une séparation locale des voix, avant le rapport. Les groupes portent « Intervenant 1 », « Intervenant 2 », etc. Ce sont des groupes acoustiques, pas une identification des personnes. Les passages trop courts, les voix proches ou les paroles simultanées peuvent rester « Voix à vérifier ». Le moteur vise au plus8groupes par défaut ; ce plafond ne garantit pas la séparation de huit personnes et la correction manuelle reste nécessaire au-delà ou en cas de confusion. Le direct ne promet pas des numéros stables ; l’attribution finale intervient après la capture.

La version ASRv1 est conservée ; une séparation réussie produit v2 sans changer texte, IDs ou horodatages, puis le rapport utilise cette version. Un échec conserve ASRv1 et permet l’analyse avec avertissement. Les reprises durables et les corrections concurrentes ne republient pas une ancienne attribution par-dessus une source plus récente. Un avertissement d’échec reste lié à sa version, pas aux corrections futures.

`MEMORA_AUTO_DIARIZATION=1` est la valeur initiale du serveur ; `0` désactive cette étape pour les prochaines créations. Le choix est figé dans les réglages de chaque nouvelle réunion, sans traitement rétroactif. Les anciennes réunions gardent leur historique ; « Gérer les intervenants » → « Séparer les intervenants localement » reste une action volontaire. Le renommage reste disponible. Une voix incertaine n’est jamais renommée artificiellement « Intervenant1 ».

Preuve réelle synthétique connue :40,17s audio, deux voix et six prises non alternées, labels1/2/2/1/1/2, mêmes texte/IDs/temps entre ASRv1 et labels v2 ; rapport Gemma unique sourcé v2,18,036s pipeline mesuré sur cette machine. Aucun mock ASR/séparation/rapport, aucun audio personnel ni modèle téléchargé. Ce petit exemple ne garantit pas chaque voix naturelle ou une réunion longue. Reproduction : préparer la réserve avec `scripts/memora-prepare-diarization-reserve.py`, puis `backend/.venv/bin/python scripts/memora-qa-auto-speakers.py` ; modèle local et Ollama requis. Voir .agents/handoffs/automatic-speakers-real.md et automatic-initial-speakers.md.

## Naviguer pendant l’enregistrement et discuter avec Memora

Démarrez l’enregistrement depuis une réunion, puis utilisez les liens de navigation internes. Une barre en bas conserve le titre, la durée et les commandes Pause/Reprendre, Terminer et analyser et Retour à la réunion. Un seul enregistrement peut être actif. La déconnexion arrête le microphone. Évitez de recharger la page ou de fermer le navigateur pendant la capture ; une vraie suspension de la machine peut toujours couper le microphone.

Ouvrez l’onglet Chat IA d’une réunion : discussion en zone principale, questions de suivi, historique conservé, réponses avec passages sources et accès audio lorsque le partage l’autorise. Entrée envoie et Maj+Entrée ajoute une ligne. Les anciennes réponses restent identifiables après correction, mais leurs anciennes citations ne pilotent pas l’audio courant. Les six derniers échanges sont utilisés dans la limite de6000caractères ; une indication signale les échanges omis. Le texte source courant demeure la référence factuelle.

## Reprendre une séparation échouée avec l’analyse

Quand la séparation automatique a échoué sur la transcription courante et que l’audio est disponible, « Relancer l’analyse » réessaie d’abord de distinguer les intervenants, puis génère le rapport sur la nouvelle version. Le nombre d’intervenants connu peut être indiqué (1 à8) ; laissez le champ vide pour une estimation automatique, qui peut encore échouer. Les anciennes transcriptions et les anciens rapports restent dans l’historique.

Une correction manuelle plus récente n’est pas réétiquetée automatiquement ; pour remplacer volontairement ces attributions, utilisez la séparation dédiée et sa confirmation. Sans audio disponible ou autorisé, seule la régénération du rapport demeure possible. Une défaillance des voix ne supprime pas la transcription et reste signalée ; elle ne constitue jamais une preuve qu’une seule personne a parlé.

## Couleurs et thèmes

Les pages de connexion, inscription, récupération du compte, profil, administration et réunions partagent la palette violette de Memora, en clair et en sombre. Le sélecteur de thème reste dans l’en-tête. Les couleurs sont centralisées dans `frontend/src/app/theme.css` : modifier les variables sémantiques à cet endroit plutôt que créer une palette par écran. Les couleurs de succès, erreur et avertissement sont distinctes des accents de navigation.

## Intervenants : moteur ECAPA local et limites

Sur macOS Apple Silicon, les nouvelles installations choisissent `MEMORA_DIARIZATION_ENGINE=ecapa-segmented` (voir ci-dessous). Le modèle officiel [SpeechBrain ECAPA-TDNN](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) est annoncé sous licence Apache-2.0, révision `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`, poids d’embedding de 83,3 Mo. `MEMORA_ECAPA_MODEL_DIR` désigne son répertoire local. Préparation : `backend/.venv/bin/python scripts/memora-prepare-ecapa.py` ; contrôle hors réseau : même commande avec `--check-only`. `--from-file` permet de réutiliser une copie dont le SHA256 correspond exactement au modèle officiel. Les dépendances sont verrouillées dans backend/uv.lock ; le script install prépare uniquement le moteur choisi. Aucun téléchargement pendant une réunion, aucun fournisseur externe de secours.

### Séparation des voix sans compte

`ecapa-segmented` utilise ECAPA validé, puis une segmentation neuronale en cas de
comptage acoustique instable. Il ne requiert aucun compte et traite les audios sur
la machine. Les anciens choix `ecapa-tdnn` et `resemblyzer` restent explicites et
leurs modèles sont conservés. Le générateur ne réécrit pas une configuration existante.

```sh
backend/.venv/bin/python scripts/memora-prepare-ecapa.py
backend/.venv/bin/python scripts/memora-prepare-segmentation.py
backend/.venv/bin/python scripts/memora-prepare-segmentation.py --check-only
```

Dans `.memora/backend.env`, choisir `MEMORA_DIARIZATION_ENGINE=ecapa-segmented`.
`MEMORA_SEGMENTATION_MODEL_DIR` désigne par défaut `.memora/models/segmentation-3.0`.
La distribution publique MIT pèse 6,96 Mo et le modèle installé 5,99 Mo ; son script
conserve licence, attribution et empreintes. Aucun accès au réseau pendant le calcul.
Le compagnon natif doit être redémarré **hors enregistrement et hors traitement**
pour charger ce changement ; la configuration Docker est régénérée au démarrage habituel.

Pour une réunion déjà enregistrée, ouvrir Transcription → Gérer les intervenants →
Séparation locale des voix, puis lancer la séparation. Laisser le nombre vide pour
l'estimation automatique, ou fournir le nombre réellement connu. La transcription
est conservée dans l'historique, et le rapport est ensuite à régénérer. Le nouveau
moteur ne renomme aucune réunion historique sans cette action.

Limites : calcul borné à deux heures et huit groupes ; les voix proches, le bruit,
les réponses très courtes et les changements de canal peuvent encore provoquer une
fusion, une fragmentation ou un refus d'attribution. Les activités simultanées
peuvent être détectées, sans séparation des pistes audio. Aucun score de confiance
calibré n'est fourni. Voir les [mesures et échecs connus](DIARIZATION_RESEARCH.md).

Recette isolée avec choix explicite du moteur :
`backend/.venv/bin/python scripts/memora-verify-docker.py --diarization-engine ecapa-segmented`.
Le script ne change pas le moteur de l'application active. Le benchmark
`memora-qa-speaker-consistency.py --engine ecapa-segmented --include-holdout` conserve
un critère strict : il termine en échec si un cas est mal compté ou sans attribution,
même si l'application sait présenter cette incertitude et permettre une reprise.

L’architecture est instanciée par le code SpeechBrain installé et les poids sont lus avec `weights_only=True` ; aucun YAML distant ou code fourni par le modèle n’est exécuté. L’inférence reste CPU, deux threads par défaut. Les fenêtres de comparaison ECAPA durent 3,2 s, avec des cellules horodatées de 0,4 s conservées. Le seuil de distance cosinus de 0,55 est propre à ce modèle et a été choisi sur un corpus synthétique ; il ne s’applique pas à Resemblyzer. Si une estimation de plusieurs voix contredit la comparaison de 1,6 s, le moteur s’abstient et conserve la transcription sans inventer des numéros. Une estimation concordante peut encore être fausse. Les courtes prises de parole, le bruit, les changements de microphone et les voix simultanées restent difficiles.

Le moteur historique reste disponible par choix explicite `MEMORA_DIARIZATION_ENGINE=resemblyzer`, sans suppression de ses poids ; son contrôle de cohérence à 1,6/3,2 s peut également refuser une attribution instable. Les erreurs ne détruisent ni la transcription ni les anciens rapports. Quand vous savez qu’une seule personne parle, indiquez 1 dans Gérer les intervenants → Séparation locale des voix ; sinon laissez le nombre vide pour une estimation. Relancez ensuite le rapport pour prendre en compte les nouveaux libellés. Une réunion déjà traitée n’est jamais réécrite automatiquement lors du changement de modèle.

Recette reproductible : préparer les corpus existants avec `scripts/memora-benchmark-diarization.py --prepare-only`, `scripts/memora-prepare-diarization-reserve.py`, puis `scripts/memora-prepare-speaker-holdout.py`. Ce dernier exige des voix TTS macOS déjà installées et n’en télécharge aucune. Lancer `backend/.venv/bin/python scripts/memora-qa-speaker-consistency.py --engine ecapa-tdnn --include-holdout --output .agents/logs/mon-resultat.json` (chemin neuf). Le rapport distingue comptes corrects, abstentions et erreurs restantes ; il ne mesure pas une précision garantie sur toutes les réunions naturelles. Détails des mesures et des limites dans .agents/testing.md.

## Exporter une transcription ou un rapport

Dans l’onglet **Transcription** ou **Rapport**, cliquer sur **Exporter**, choisir le format puis télécharger. L’export porte sur la version affichée au moment d’ouvrir le dialogue : choisir d’abord la version souhaitée dans l’historique.

- Transcription : **TXT**, **PDF**, **Word (.docx)**, sous-titres **SRT** et **WebVTT (.vtt)**. Les documents conservent les horodatages et intervenants ; les sous-titres conservent les temps, y compris après une heure.
- Rapport : **TXT**, **PDF**, **Word (.docx)** et **Markdown (.md)**. Résumé, sujets, décisions, actions, responsables, échéances et questions ouvertes sont inclus lorsqu’ils existent. Les corrections humaines sont distinguées du résultat IA ; les sources restent limitées aux passages essentiels.

Le document indique sa version et sa date en UTC. Les libellés du document sont en français ; les paroles en français ou anglais restent dans leur langue. Le PDF utilise une police embarquée avec accents latins ; un caractère non couvert est signalé explicitement sous la forme `[U+XXXX]`. Le TXT conserve l’Unicode original. Le texte importé reste du texte littéral dans les documents, y compris en Markdown.

Un invité peut exporter les contenus autorisés par son lien, y compris sans compte. Un accès au rapport seul ne donne accès ni à la transcription ni au texte brut de ses sources. Mot de passe, expiration et révocation sont contrôlés côté serveur avant et après génération. Une copie déjà téléchargée ne peut pas être retirée à son destinataire.

Les fichiers sont produits à la demande en mémoire ; aucune copie d’export n’est conservée sur le serveur. Limites actuelles : source sérialisée5MiB, fichier20MiB,2générations simultanées et20demandes/minute par propriétaire ou lien. Une limite dépassée produit une erreur explicite, jamais un document tronqué. Aucun retraitement IA n’est nécessaire. Les dépendances `reportlab` et `python-docx` sont verrouillées dans `backend/uv.lock` ; aucune migration supplémentaire.


## Temps réel et worker Docker indépendant

Les écrans réunion, tableau de bord/notifications et suivi des emails utilisent `/api/memora/events`, relayé par Next sur `/mapi/events`. Le paramètre facultatif `meeting` sélectionne une réunion ; sans paramètre, le flux est réservé au propriétaire connecté. Les invités utilisent les en-têtes de partage habituels, y compris le mot de passe, jamais des identifiants d’accès dans l’URL.

Le transport SSE transmet uniquement `refresh` avec un objet vide. Les triggers PostgreSQL notifient des canaux dérivés des identifiants de périmètre ; aucun texte, email, token ou mot de passe n’est émis. `LISTEN` est établi avant la première invalidation. Une transaction annulée ne produit pas d’événement. Les notifications ne constituent pas un historique durable : chaque reconnexion demande une lecture complète de l’état autorisé. Les rafales sont regroupées côté navigateur ; le battement de 15 secondes n’entraîne pas de lecture métier.

Les abonnements sont bornés à 32 par processus API et 3 par canal. À chaque événement et battement, le serveur revérifie la session ou le partage. L’expiration et la révocation ferment le flux ; le client recharge alors la ressource pour effacer les contenus devenus inaccessibles. Les endpoints métier restent responsables de l’autorisation de chaque lecture. Une panne du flux déclenche une reconnexion progressive (plafond de 30 secondes, plus une petite variation aléatoire) et un secours par GET toutes les 15 secondes. Un flux silencieux plus de 45 secondes est reconnecté. SQLite, conservé pour les tests isolés, utilise ce secours ; le transport interprocessus est PostgreSQL.

`backend/api/memora/realtime.sql` installe les triggers idempotents à l’initialisation du schéma, sans nouvelle table métier ni modification des contenus. Leur livraison ne nécessite pas de réimporter les données. Le proxy Next propage l’annulation de la requête au flux backend et ne lui applique pas le timeout des requêtes courtes.

Le service Compose `worker` exécute `python -m api.memora.worker_main` dans la même image que FastAPI, sans port HTTP publié. Son contrôle de santé utilise un heartbeat de processus ; le verrou exclusif partagé est acquis avant toute récupération des tâches `running`. L’API utilise `MEMORA_DISABLE_WORKER=1` et initialise le schéma avec `recover_jobs=False`, pour ne pas modifier une tâche du worker déjà active. Le mode natif de recette conserve son worker embarqué historique.

La file `jobs`, les versions, checkpoints et garanties d’idempotence existants sont conservés. La boucle retente les erreurs de connexion/transaction au stockage ; les erreurs fonctionnelles du modèle restent visibles et relançables. Le redémarrage reprend la dernière phase validée, sans garantir qu’une phase non commitée ne sera jamais recalculée. Le contrôle de santé atteste que le processus est vivant ; il ne prouve pas à lui seul que PostgreSQL ou un modèle répond. Le chat HTTP synchrone ne fait pas partie de cette file : sa génération n’est pas reprise automatiquement après un crash de l’API.

Choix : SSE convient aux mises à jour serveur → navigateur et traverse le proxy HTTP existant. La file PostgreSQL suffit au worker local unique ; Celery ajouterait un broker et de nouvelles règles d’acquittement à qualifier. Les architectures de DBChat, AI_Agora et ServicePublic ont été consultées en lecture seule comme références, sans copie de code ni secrets. Voir les documentations de [LISTEN](https://www.postgresql.org/docs/16/sql-listen.html), [NOTIFY](https://www.postgresql.org/docs/16/sql-notify.html) et des [acquittements Celery](https://docs.celeryq.dev/en/stable/userguide/tasks.html#acks-late) pour les garanties des mécanismes.

Vérifications reproductibles : tests `backend/test/test_memora_realtime.py`, `test_memora_postgres_live.py` (base jetable explicite), `test_memora_worker_standalone.py`, `frontend/tests/memora-realtime.test.mjs` et `memora-realtime-browser.mjs` (uniquement stack Docker synthétique). `scripts/memora-verify-docker.py` exécute aussi ce dernier. Les tests de mort du worker emploient une inférence contrôlée synthétique pour examiner les checkpoints ; ils ne mesurent pas la précision du modèle.

Validation locale du 25 octobre 2026 pour ce jalon :

- Suite backend : **403 tests réussis, 10 ignorés, 3 avertissements**, en 30,54 s. Les tests PostgreSQL optionnels sont exécutés séparément : **7 réussis** sur bases synthétiques jetables.
- Client temps réel : **4 tests réussis**, couvrant connexion partagée, trames fragmentées, reconnexion, révocation et actualisation de secours.
- Recette Docker complète : **22 groupes navigateur, 20 groupes d’audit UI et 8 groupes temps réel réussis**, avec vrais moteurs locaux sur données synthétiques et emails reçus dans Mailpit. Audit UI et 8 contrôles temps réel rejoués avec succès sur les images finales.
- Arrêt brutal `SIGKILL` puis reprise du worker vérifiés en sous-processus avec inférence synthétique contrôlée : checkpoint conservé, pas de nouvelle ASR pour la source publiée et pas de rapport dupliqué. Les erreurs de base et les accusés de commit perdus sont également testés.
- Lint, types, contrat OpenAPI/client généré, build Docker et contrôles de syntaxe réussis ; le lint frontend conserve cinq avertissements préexistants.
- Activation locale : cinq conteneurs sains, compagnon natif actif, quatre sondes HTTP réussies. Empreintes de toutes les tables du domaine identiques avant/après, aucune capture ni tâche active lors de la bascule. Aucun audio personnel retraité, email externe ou service public créé.

La première tentative de recette a été arrêtée avant les tests navigateur, car le Chromium par défaut de Playwright était absent. La validation utilise le Chromium déjà installé via `PLAYWRIGHT_CHROMIUM_EXECUTABLE` ; aucun résultat de cette première tentative n’est compté comme une réussite.


## Nettoyage du template et incident audio du 26 octobre 2026

Les pages et composants de démonstration du template ont été retirés : ancien guide développeur `/documentation`, CodeBlock, HomeActions et styles orphelins. Les pages produit, comptes, profil, administration, thèmes et traductions encore utilisées sont conservés. Le backend ne monte plus le Socket.IO de démonstration et son message « hello world ». Le module Celery sans tâches, l’ancien middleware de collecte des corps de requêtes, les utilitaires orphelins, le faux générateur SMS et la page HTML de démonstration dans les logs ont été supprimés. Le worker durable PostgreSQL et le transport SSE de Memora restent en place. Les anciennes migrations sont conservées.

Celery, python-socketio, PyMySQL, pycryptodome, bcrypt et requests ne sont plus des dépendances directes. Les bibliothèques toujours requises transitivement restent dans le verrou. Pytest et Faker sont réservés au groupe de développement. Le verrou a été régénéré et contrôlé sans mise à niveau des versions conservées ; le projet Python porte désormais le nom `memora-backend`. Les services de profil, stockage, permissions, récupération de mot de passe, vérification email, cache et quotas restent disponibles.

Le dossier local ignoré `monitoring/`, qui ne contenait que d’anciennes sauvegardes du template, a été supprimé après vérification de l’absence de référence et de montage dans les conteneurs, y compris arrêtés. Son ancien fichier `.env.grafana` inutilisé a été retiré. Les données actives PostgreSQL, audios, modèles et sauvegardes Memora ne font pas partie de ce nettoyage. L’endpoint de métriques HTTP est conservé car il fait encore partie du backend et de ses vérifications.

L’erreur « moteur audio local indisponible » a été reproduite comme une absence du compagnon natif alors que les cinq services Docker avaient redémarré. Le compagnon a été relancé, puis une transcription française réelle du WAV synthétique Python a réussi depuis le conteneur backend. Aucune réunion personnelle n’a été relancée automatiquement. Les nouvelles vérifications de démarrage et de statut contrôlent l’identité HTTP et un endpoint authentifié, sans journaliser le token.

La supervision de ce compagnon par launchd a été essayée mais n’a pas atteint l’état prêt (`EX_CONFIG 78`). La cause système précise n’a pas été établie ; aucune restriction macOS n’a été contournée. L’essai a été désactivé et sa définition retirée ; le moteur natif direct fonctionnel a été rétabli. La branche de supervision non validée n’est pas conservée dans le code livré. Après un redémarrage du Mac, lancer `./scripts/memora-start.sh` ; les conteneurs seuls ne garantissent pas la disponibilité de l’audio.

Validation du nettoyage : 398 tests backend réussis, 10 ignorés et 3 avertissements (les 5 anciens tests spécifiques Celery/Socket.IO ont disparu avec leurs modules) ; 50 tests de scripts réussis, dont 9 contrôles du lancement natif ; 36 tests unitaires frontend réussis. Lint, types, OpenAPI/SDK, verrou et build Docker réussis. La recette Docker isolée a validé 22 groupes navigateur, 20 groupes d’interface et 8 groupes SSE, avec vrais modèles sur données synthétiques, email reçu dans Mailpit et persistance après redémarrage de l’API. Aucun démarrage automatique de session n’est annoncé.

Activation vérifiée après garde zéro capture, zéro tâche et aucune écriture audio récente : les cinq conteneurs sont sains, le compagnon natif répond au contrôle authentifié, les quatre sondes HTTP réussissent et toutes les empreintes des tables métier sont identiques avant/après. Une nouvelle transcription réelle du WAV français synthétique a réussi depuis les conteneurs nettoyés. Le résultat et les identifiants des réunions personnelles n’ont pas été utilisés comme données de test.

### Recours Community-1 local, sans compte

Sur Apple Silicon avec macOS 15+ et Swift/Xcode 6.2+, un recours complet est
optionnel. Il intervient seulement si ECAPA puis la segmentation ne trouvent pas
un nombre stable de voix. Il ne remplace pas les résultats déjà réussis.

```sh
backend/.venv/bin/python scripts/memora-prepare-community.py
backend/.venv/bin/python scripts/memora-prepare-community.py --check-only
```

Configuration dans `.memora/backend.env` :

```dotenv
MEMORA_DIARIZATION_ENGINE=ecapa-segmented
MEMORA_DIARIZATION_RECOVERY=community-coreml
```

`MEMORA_COMMUNITY_MODEL_DIR` et `MEMORA_COMMUNITY_TOOL_DIR` permettent de déplacer
les répertoires `.memora/models/community-coreml` et `.memora/tooling/community-coreml`.
Le script install respecte ces chemins. La préparation télécharge uniquement une
distribution publique épinglée et compile un outil natif ; elle ne change aucun
service ni aucune réunion. Pour une copie locale des téléchargements examinés,
`--from-lab CHEMIN` attend `source.tar.gz` et `models/`. Après configuration,
redémarrer les services avec le lanceur habituel, hors capture/traitement. Les
anciens résultats restent inchangés : relancer explicitement la séparation puis
le rapport depuis la réunion concernée.

Les deux méthodes restant faillibles, des passages courts ou multivoix peuvent
rester sans attribution. L’incertitude de comptage est conservée comme telle,
sans être présentée comme une panne du serveur. L’indication du nombre connu
reste possible ; elle n’établit pas l’identité ni l’exactitude de chaque passage.
Les [mesures et limites](DIARIZATION_RESEARCH.md) distinguent comptage et attribution.
Recette Docker isolée avec ce recours :
`backend/.venv/bin/python scripts/memora-verify-docker.py --diarization-engine ecapa-segmented --community-recovery`.
