# Memora V1 — fonctionnement local

Memora enregistre ou importe un audio, transcrit avec Whisper, analyse avec Ollama, conserve les versions et partage les contenus selon des permissions vérifiées par l’API. Cette livraison vise une utilisation locale sur cette machine, avec des données synthétiques de démonstration. Elle n’est pas qualifiée pour une exploitation en production.

## Démarrer et arrêter

Prérequis validés sur cette machine : macOS Apple Silicon natif arm64, Python pour installer uv (le projet utilise Python3.12), Node.js24 et npm. Prévoir environ8Go libres pour dépendances, build et modèle de transcription, puis l’espace nécessaire aux audios. Le chemin CPU Faster Whisper reste configurable sur les autres plateformes ; sa précision est inférieure sur le corpus français testé et il ne constitue pas la configuration de précision retenue ici. Ollama existant doit répondre sur `127.0.0.1:11434` avec `gemma4:e4b` installé. Aucun script ne réinstalle Ollama ni ne supprime ses modèles.

Depuis la racine :

```sh
./scripts/memora-install.sh
# Si aucun modèle d’analyse adapté n’est présent : voir section IA avant téléchargement.
./scripts/memora-start.sh
backend/.venv/bin/python scripts/memora-demo.py
./scripts/memora-status.sh
./scripts/memora-stop.sh
```

`memora-demo.py` s’exécute après démarrage de l’API ; au premier lancement, démarrer les services avant de l’exécuter. Il crée uniquement le compte synthétique de démonstration et lui donne les droits administratifs dans la base locale isolée. Les identifiants sont dans `.memora/demo.json`, fichier privé non versionné. Un compte personnel peut aussi être créé dans l’interface ; il ne devient pas administrateur automatiquement.

Pour mettre à jour une installation existante, arrêter les services avant `memora-install.sh`. L’installation appelle `scripts/memora-migrate.py` : ce lanceur refuse une base différente des deux SQLite privées du projet et refuse de migrer pendant qu’un worker détient son verrou. Il sauvegarde les bases dans `.memora/backups/`, applique Alembic et les migrations du domaine, vérifie le schéma puis rattache les anciennes réunions à l’identité permanente du compte. Les sauvegardes privées sont exclues de Git et restent à conserver ou supprimer explicitement ; la rétention audio ne les purge pas.

La migration de sécurité `0007_account_uid` invalide les anciennes sessions : se reconnecter avec les mêmes identifiants. Un compte supprimé puis recréé reçoit une nouvelle identité même si SQLite réutilise son numéro. L’accès aux réunions, notifications et statuts email vérifie cette identité. Le rattachement des données anciennes refuse les comptes absents, les réunions antérieures au compte et les dates ambiguës dans sa seconde de création ; les compteurs de migration signalent ces cas sans accorder automatiquement un accès. `memora-bind-owners.py --dry-run` permet de revoir le bilan sans écriture.

Adresses : application [localhost:3000](http://localhost:3000), documentation API [127.0.0.1:8080/docs](http://127.0.0.1:8080/docs), capture email [127.0.0.1:8025](http://127.0.0.1:8025). Tous les serveurs sont liés à l’interface locale, sans exposition publique.

Le lanceur conserve les PIDs qu’il a démarrés et ne tue pas les processus occupant un port. Si un port est déjà occupé, il le signale. La commande d’arrêt vérifie le processus avant de lui envoyer SIGTERM. Ollama reste indépendant et n’est jamais arrêté par ces scripts.

Pour utiliser le build optimisé :

```sh
cd frontend
npm run build:memora
cd ..
MEMORA_MODE=production ./scripts/memora-start.sh
```

Le lanceur frontend copie les assets statiques dans le dossier standalone, puis démarre son serveur. Le mode par défaut est le développement avec Webpack. Turbopack a échoué sur un sous-processus CSS `EPERM` dans l’environnement d’exécution ; Webpack a réellement construit l’application. Le mode optimisé ne signifie pas que l’application est prête pour la production.

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

Validation historique de Whisper Turbo, avant la nouvelle route française : les sept cas synthétiques de validation conservent le bilingue sans traduction et n’ajoutent aucun texte sur silence/bruit. Sur le français complexe, WER après normalisation numérique explicite17,5% avec base contre2,5% avec MLX ; l’écart restant correspond à « M. »/« Monsieur ». Le bilingue garde une différence « Mémora »/« Memora » ; Python et anglais sont exacts sur ces exemples. Quinze minutes synthétiques ont été transcrites en54,29s, avec début et phrase finale retrouvés, deux langues et pic mémoire processus d’environ2,83GiB. Ces résultats ne garantissent pas l’exactitude sur une voix ou une réunion naturelle particulière. Méthode et preuves : [validation ASR](../agents/handoffs/asr-final-validation.md).
Ne télécharger un modèle Ollama supplémentaire que si nécessaire après contrôle licence, taille et mémoire. Ici aucun téléchargement Ollama n’a été nécessaire : Gemma et Qwen étaient déjà présents. Sur une autre machine sans Gemma, `ollama pull gemma4:e4b` doit être une préparation explicite après vérification de l’espace, de la licence et de la RAM, pas un téléchargement pendant une réunion. Ne pas sélectionner un modèle cloud. Les besoins du modèle s’ajoutent aux dépendances et audios.

Gemma a conservé la modalité future sur les corpus courts et longs examinés. Rapport3lots41,241s et chat18,693s, source finale conservée ; absence/injection testées aussi. Mémoire libre système minimale échantillonnée19% pendant les probes sur cette machine16Gio, puis récupération après déchargement : charge supérieure à Qwen, sans promesse sur une machine déjà saturée. La classification d’une discussion en « action » reste perfectible ; aucune certification d’exactitude sémantique universelle. Les citations valides ne suffisent pas à prouver une paraphrase : relecture humaine des décisions et engagements nécessaire. Preuves : [comparaison modale](../agents/handoffs/report-modality-comparison.md), [validation Gemma](../agents/handoffs/gemma-full-validation.md). Whisper small a été essayé, puis écarté comme défaut : il a omis une partie anglaise du corpus testé. Ses fichiers locaux de comparaison ne sont pas versionnés.

Le moteur Faster Whisper renseigne une langue par segment ; les anciens résultats MLX sans VAD indiquent une langue dominante initiale et les nouveaux une estimation par portion vocale. L’interface distingue aussi la langue choisie explicitement. Ces étiquettes ne prouvent pas la langue de chaque mot. Accents, noms propres, bruit et transitions restent imparfaits : contrôler et corriger les passages importants puis régénérer. Les indicateurs d’incertitude ne garantissent pas l’absence d’erreur.
Les longues sources sont traitées par lots bornés et conservent leurs références, locuteurs et horodatages. Les fragments de phrase adjacents sont réunis avant le découpage des lots ; les citations reviennent toujours aux segments originaux. Une date dite dans une autre phrase ne suffit pas à attribuer une échéance à une action ; le chat utilise une réduction hiérarchique sans sélectionner silencieusement seulement le début. Cela ne constitue pas un benchmark de deux heures ni une garantie de qualité universelle. Ollama reçoit `truncate:false` et `shift:false` : un contexte trop grand est refusé explicitement plutôt que coupé silencieusement. Les appels d’inférence ASR/Ollama sont sérialisés dans le processus applicatif, avec libération du verrou entre lots et après erreur. Les caches d’Ollama peuvent se libérer quelques instants après une réponse malgré keep_alive=0 ; cette garde ne contrôle pas les autres applications et ne garantit pas une isolation matérielle. Le proxy chat utilise un délai configurable `MEMORA_CHAT_TIMEOUT_MS` (environnement serveur frontend),600000ms par défaut, borné1000–1800000ms ; REST conserve120000ms. Un dépassement504 informe que le calcul backend peut encore finir : consulter l’historique avant de relancer. Le texte source et la question sont des données non fiables pour le modèle ; ils ne déclenchent jamais de commandes, emails ou actions extraites.

Si Docker est retenu ultérieurement, `localhost` du conteneur ne désigne pas l’hôte : utiliser une connexion privée appropriée telle que `host.docker.internal:11434`, puis vérifier depuis ce conteneur. Aucun service Docker n’est nécessaire ni utilisé par le parcours local livré. Ollama n’est pas exposé publiquement.

## Partage, données et effets externes

Les autorisations sont vérifiées pour chaque réunion, transcription, rapport, audio et question. Les liens sont aléatoires ; le mot de passe est conservé sous hash scrypt. L’email ne définit jamais une liste nominative d’accès : un lien peut être retransmis. Si le transcript est masqué mais le chat et le rapport permis, le chat ne reçoit que le rapport visible et ne divulgue pas de citations du transcript.

L’éditeur invité doit avoir un droit explicite, l’activation administrative actuelle et un nom déclaré ; la session aléatoire et l’auteur déclaré sont tracés. Ce mécanisme ne prouve pas son identité civile. Il ne permet ni repartage, ni archivage, ni suppression. Deux corrections basées sur la même ancienne version ne s’écrasent pas : la seconde reçoit 409.

Les corps d’emails en file sont chiffrés avec Fernet, clé dérivée de `SECRET_KEY`, déchiffrés en mémoire puis effacés après remise SMTP. L’envoi conjoint du mot de passe est possible après choix explicite ; le message livré est une copie du destinataire qui ne peut pas être rappelée. Les destinataires reçoivent des messages séparés. Les emails déjà envoyés ne sont pas renvoyés par une reprise normale ; les échecs disposent d’une reprise ciblée. Un crash exactement entre acceptation SMTP et écriture de l’état peut néanmoins provoquer une redélivrance : SMTP ne fournit pas une transaction exactement-une-fois.

Le serveur `memora-mail-capture.py` ne relaie aucun message ; il affiche le contenu HTML sous forme échappée pour inspection. La réception locale vérifie la composition, pas la délivrabilité en production ni la lecture par un destinataire.

**Archive** change le classement et conserve les contenus et les liens actifs. **Supprimer définitivement** demande confirmation, retire l’accès, supprime versions/chat/liens/notifications et fichiers audio locaux ainsi que les emails encore en file. La purge de l’audio seul arrive à sa date de conservation ; transcription, rapports et chat sont conservés jusqu’à suppression explicite. Aucun backup automatique n’est annoncé. Des sauvegardes manuelles, emails reçus et téléchargements demeurent des copies indépendantes.

La suppression d’un compte pose d’abord une barrière liée à son identité permanente. Les accès invités et les publications de traitements tardifs sont bloqués ; fichiers et données associés sont ensuite supprimés. En cas d’erreur de fichier, le compte reste présent pour permettre une nouvelle tentative, et la barrière continue de protéger ses réunions. Les anciennes sauvegardes et emails capturés restent des copies indépendantes.

Le stockage audio/SQLite n’est pas chiffré intégralement par l’application ; il est protégé par les permissions locales et les contrôles d’accès applicatifs. TLS, sauvegardes/restauration d’exploitation, rétention légale, supervision multi-instance et qualification de sécurité nécessitent un travail avant production. Le worker local est mono-instance avec verrou POSIX ; il ne prétend pas remplacer une infrastructure de traitement distribuée.

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
npm run test:memora
cd ..
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

Résultats datés et limites : [agents/testing.md](../agents/testing.md), [traçabilité](../agents/requirements.md), [recette API réelle](../agents/handoffs/e2e-api.md), [recette navigateur](../agents/handoffs/browser.md). Ne pas confondre ces preuves avec une validation Safari/iOS, une veille physique, une réunion de deux heures ou une capacité de production.

## Mémoire et Git

`AGENTS.md` pointe vers `agents/README.md` puis `agents/memory/state.md`. Les notes synthétiques, décisions, carte du code, exigences, plan et preuves de recette sont pérennes et versionnables. Les logs et captures de `agents/logs/`, les modèles, bases, audios utilisateur, secrets, sessions et emails de `.memora/` restent exclus de Git. Les seules fixtures audio versionnées sont synthétiques. Les références DBChat, ServicePublic et AI_Agora ont été consultées sans modification et sans copie de code faute de licence explicite vérifiée.


### Correctif du choix français et lisibilité

La configuration retenue revient à **Whisper Turbo conditionné français** : Parakeet ne peut imposer la langue, malgré un meilleur WER sur cette réserve. Le symptôme de traduction signalé n’a pas été reproduit sur les quatre cas synthétiques de diagnostic (12 inférences). Aucun enregistrement personnel supplémentaire n’a été retraité. Comparaison sur 24 profils français existants : WER numérique Turbo15,52%, Full15,71%, Parakeet6,70% ; propre Turbo/Full10,34%. Full ne justifie donc pas son surcoût global. Ce corpus ne démontre pas90% de précision générale. [Diagnostic](../agents/handoffs/asr-language-drift-diagnostic.md) et [comparaison conditionnée](../agents/handoffs/whisper-forced-fr-reserve-v3.md). Les anciennes transcriptions ne sont pas modifiées automatiquement : choisir Français puis « Retranscrire l’audio » crée une nouvelle version.

Pendant une capture, la forme d’onde, le niveau et la crête proviennent du flux effectivement enregistré. Pause, silence prolongé, saturation et entrée déconnectée ont des états distincts. Le visualiseur ne demande pas une seconde autorisation et ne prouve pas la sauvegarde : les accusés des fragments restent séparés. La transcription dispose d’une hauteur bornée et d’un défilement interne ; titre et correction restent visibles. Les sources du résumé et des sujets sont repliées ; décisions, actions et questions ouvertes gardent leurs citations directes.

## Recherche et validation de précision du 25 octobre

La [recherche primaire](../agents/handoffs/accuracy-research-services.md) compare les méthodes documentées de Read, Otter, Fireflies, Deepgram et AssemblyAI. Un vocabulaire spécialisé peut aider, mais nos essais de lexique global ont remplacé des noms voisins et supprimé du français. Le remplacement global par Whisper large-v3 a également régressé en bilingue. Ces réglages ne sont pas activés. Température zéro et best_of5 n’ont pas amélioré les hypothèses testées. Aucun correcteur LLM ne réécrit silencieusement la transcription.

La politique historique évaluée ci-dessous choisissait **Parakeet TDT 0.6B v3 pour le français final**, et conserve **Whisper Turbo pour le direct, l’anglais et l’automatique/bilingue**. Parakeet ne force pas la langue : le choix français sélectionne le moteur ; la langue détectée reste `unknown`, affichée « Langue non déterminée ». Le fournisseur n’expose pas de confiance calibrée : les avertissements prudents ne mesurent pas un taux d’erreur.

| Réserve synthétique v3 historique | WER numérique Turbo | Route Parakeet optionnelle |
|---|---:|---:|
| Audio propre, toutes langues | 6,07% | 4,05% |
| Français propre | 10,34% | 4,60% |
| Anglais propre | 4,55% | 4,55% |
| Alternance propre | 2,78% | 2,78% |
| Bruit20 / bruit10 | 9,31% / 15,38% | 4,45% / 10,93% |
| Opus / faible volume / échos | 6,88% / 12,96% / 12,15% | 4,05% / 9,72% / 10,93% |

12 sources figées avant inférence, six conditions et deux négatifs : 148 traitements comparés, sans retrait de cas difficile. Les conditions d’une même source ne sont pas des voix indépendantes. Les sondes critiques propres passent de 27/30 à 28/30. [Protocole complet](../agents/handoffs/accuracy-reserve-v3.md). Ce WER applique une normalisation numérique publiée ; le WER strict est conservé séparément. Ces scores ne prouvent pas une précision universelle de 90%, ni celle d’une voix naturelle particulière.

Le [test français de 95 secondes](../agents/handoffs/accuracy-long-fr.md) traverse quatre fenêtres : 4,21% de WER numérique, sans perte de bloc ni doublon détecté. Soraya/Karim restent mal transcrits : les noms et responsables doivent être relus. Les [deux chaînes réelles ASR → rapport](../agents/handoffs/asr-analysis-chain-real.md) conservent six faits centraux et les responsables/échéances attendus ; une qualification trop forte « décidé » subsiste dans un résumé. La copie personnelle expressément autorisée reste privée et inchangée ; sa référence reformulée ne permet aucun pourcentage fiable.

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

`--french-asr-engine disabled` impose le moteur principal au français pendant une comparaison ; `inherit` conserve la configuration. Chromium1248 a été utilisé ici. L’import français, son rapport et la correction de locuteur sont vérifiés par API et navigateur, en plus des parcours bilingues/directs. Résultat et empreinte du code au moment des tests : [testing.md](../agents/testing.md). Les preuves historiques nécessitent leurs snapshots locaux explicitement nommés ; un nouveau benchmark utilise par défaut l’adaptateur versionné actuel et enregistre son SHA.

### Analyse : changements et limites mesurées

Les prompts distinguent proposition, décision, engagement et réalisation ; les responsables et échéances absents ne sont pas inventés. Sur la petite réserve courte, 17/18 affirmations retenues sont conformes (94,44%), et 8/8 faits attendus sont retrouvés. Ce score ne couvre pas toutes les réunions ni toutes les catégories.

Pour plusieurs lots, le moteur conserve les résumés chronologiques et vérifie séparément l’existence d’une tâche, puis les annulations/remplacements/réponses ultérieurs. Les preuves sont des IDs contraints : le backend récupère les passages originaux. Une suppression insuffisamment étayée est refusée ; le fait reste marqué « À vérifier ». Une source très volumineuse qui ne peut être réduite correctement échoue explicitement plutôt que d’être tronquée silencieusement.

La version finale V12 satisfait les cinq vérifications ciblées sur les maps réels conservés, puis un cas long complet (trois lots,94,688s). Ce ne sont pas cinq analyses complètes ni une réserve aveugle : ces cas ont servi au diagnostic après leurs échecs, tous conservés. Un doublon de décision « À vérifier » demeure dans un cas. [Preuves et limites V12](../agents/handoffs/analysis-reconciliation-v12-final.md).

### Activation et vérifications finales

Activation locale le25/10 après sauvegarde privée de configuration, zéro traitement actif et aucune capture récente : services redémarrés, HTTP200 sur UI3000/API8080/capture8025/Ollama11434. Comptes et réunions conservés ; aucun enregistrement utilisateur retraité automatiquement. Pour essayer : ouvrir http://127.0.0.1:3000, sélectionner Français pour une nouvelle réunion, ou choisir volontairement Français puis « Retranscrire l’audio » sur une réunion existante. L’opération conserve les anciennes versions ; vérifier les noms puis régénérer après correction.

- Backend final V12 :242 tests réussis,3 ignorés Redis,1 avertissement existant ; Ruff62 fichiers conformes.
- Préparation/configuration/téléchargeurs :48 tests réussis ; frontend7 tests de libellés, lint, types et build réussis.
- Recette complète isolée :55 contrôles réussis (35 API,13 navigateur,7 audit),177,13s ; modèles réels, capture microphone factice, données synthétiques. Cette recette a chargé V11 ; les modifications V12 concernent la fusion multi-lots et sont vérifiées séparément ci-dessus. Les branches courtes et ASR sont inchangées.
- Panne réelle du modèle puis restauration :2 contrôles réussis, source conservée et rapport produit sans réimport.

La première tentative navigateur a échoué avant lancement sur un ancien chemin Chromium ; elle reste consignée. Aucun résultat de test ne prouve le microphone physique, Safari/iOS, une réunion naturelle de deux heures, la charge multiutilisateur ou une aptitude à la production. [Commandes et résultats datés](../agents/testing.md).

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

Les essais synthétiques couvrent deux/trois voix, retours de parole, FR/EN, gain/bruit et silence. La réserve à nouvelles voix retrouve2/2/3groupes et attribue18/18segments ; DER7,57% et8,10% sur les cas propres,12,37% avec gain/bruit. Le DER mesure une erreur temporelle de séparation, pas un taux d’erreur de transcription ni une précision d’identification. Les références utilisent une grille20ms et l’énergie des pistes TTS ; aucune généralisation aux accents/voix naturelles. Les paroles simultanées ne sont pas séparées, les voix proches peuvent être fusionnées, le bruit et les voix faibles peuvent fragmenter les groupes. La limite technique de deux heures n’est pas une preuve de qualité sur une réunion naturelle de cette durée. [Protocole et limites](../agents/handoffs/diarization-local-v1.md).

Migration domaine007 additive : tables `report_reviews` et `transcript_edits`. Elle ne réécrit ni transcription ni rapport existant. Utiliser le script de migration local après arrêt de l’API ; il vérifie la base ciblée et le verrou du worker avant migration et sauvegarde SQLite. Ne pas migrer une autre base par substitution improvisée de variables.


Validation V1.1 finale :284testsbackend/48préparation/16frontendunit réussis ; intégration en phases isolées41API+19navigateur+9auditUI, plus10contrôlesmicroAPIssynthétiques et2contrôles de codecChromium réel surentrée factice (échantillon lu, aucuneémission). Lint/types/build/OpenAPI/SDK etRuff conformes. Les trois interruptions de recettes et leurs correctifs sont conservés, voir agents/testing.md. Services locaux activés après migration007, empreintes sources préservées. Ces résultats ne prouvent pas microphysique/Safari/iOS/conversationnaturelle ni production.


## Enregistrement en arrière-plan et protection contre la veille

L’onde représente un historique de pics audio réels défilant de droite à gauche. La pause fige cet historique, la reprise le prolonge ; aucun chiffre technique n’est affiché. Le niveau reste disponible uniquement aux technologies d’assistance.

Changer d’onglet ne déclenche aucune pause ni arrêt du MediaRecorder. L’application demande un fragment supplémentaire lors des transitions de visibilité, poursuit la sauvegarde progressive et signale un arrêt inattendu. Garder le navigateur ouvert : fermer la page ou changer de réunion peut arrêter la capture, avec avertissement avant de quitter. L’affichage animé peut être suspendu en arrière-plan sans suspendre le MediaRecorder.

Sur ce Mac avec backend natif local, une protection temporaire `/usr/bin/caffeinate -i -t 120` empêche la **veille automatique inactive du système**, pendant capture ou pause. Le frontend renouvelle le bail toutes30s ; un seul bail par compte, authentification propriétaire et état de capture vérifiés. Fin/démontage/arrêt serveur libèrent la protection ; en cas de disparition du client elle expire sans renouvellement. Aucun réglage d’alimentation permanent, blocage du verrouillage ou maintien forcé de l’écran. Sur une autre plateforme, dans Docker ou pour un navigateur distant, cette protection native n’est pas annoncée ; le Screen Wake Lock facultatif ne maintient l’écran éveillé que tant que la page est visible.

**Une vraie veille forcée, un capot fermé ou un système suspendu peuvent couper le microphone. La capture pendant ces états n’est pas garantie.** Les navigateurs peuvent aussi retarder les fragments au verrouillage. La protection empêche la veille automatique ; elle ne transforme pas une application web en enregistreur indépendant du système. Sources techniques : [Screen Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API), [MediaRecorder et fragments différés](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event). Aucun service worker ni son silencieux artificiel n’est utilisé pour contourner les restrictions du navigateur.
