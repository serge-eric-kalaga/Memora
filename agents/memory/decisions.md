# Décisions

- Utiliser `agents/` (correction explicite utilisateur), pas `.aagent`.
- Modèle initial qwen3.5:4b : déjà installé, taille 3.4 Go, test JSON réel réussi. Comparer sur corpus synthétique.
- Lecture des références seulement ; pas de réutilisation de code sans licence compatible.
- Les arbitrages du PDF ne sont pas des décisions utilisateur : valeurs initiales documentées et réversibles.
- Données et services Memora isolés du template et des autres projets ; aucun nettoyage de base existante.

- Domaine isolé SQLite/WAL avec transactions et versions ; comptes template restent dans base SQLAlchemy dédiée `.memora/accounts.sqlite3`. Évite MySQL/Redis/RabbitMQ supplémentaires pour démo locale. Worker intégré mono-instance, verrou POSIX ; file persistante reprise au démarrage. Ne prétend pas architecture multi-worker production.
- Capture MediaRecorder10s, fragments≤2Mo, IndexedDB jusqu’à accusé serveur ; séquence+hash idempotents. Reprise capture après fermeture = finaliserpartiel sauvegardé, pas promesse récupération fragments jamais reçus.
- Whisper base MIT + multilingual=True retenu après comparaison réelle small (MIT) qui a omis anglais. Aucun modèle Ollama téléchargé/remplacé. Langue détectée par segment ; confiance indicateur imparfait. Pas identification voix automatique.
- Rapports par lots de sources16kcaractères, sorties structurées ; chat map/réduction bornée, aucune recherche hors réunion. Si transcript masqué, chat uniquement rapport partagé, citations transcript supprimées.
- Défauts initiaux : durée120min (bornes1–240), upload250Mo (1–500), audio30jours (1–365), partage7jours proposé UI, guesteditfalse, languefr. Valeurs initiales techniques, pas décisions utilisateur. Paramètres snapshot à création ; journal configold/new, pas rétroactivité.
- Invité éditeur : droitedit explicite + autorisationadmin actuelle + nom déclaré obligatoire ; trace session aléatoire, pas preuve identité nominative. Emaildestinataire n’est jamais ACL.
- Mot de passe partage scrypt ; corps emails file chiffrés Fernet via clé dérivée SECRET_KEY, déchiffrés mémoire, effacés après remiseSMTP. Option lien+password mêmeemail autorisée avec information ; copies livrées non rappelables. ServeurSMTP capture local seulement.
- Archivage conserve accès/liens/contenus ; suppression cascade domaine, mailenattente et fichiersaudio, notifications retirées. Audio purge à échéance snapshot, transcriptions/rapports/chat conservés jusqu’à suppression explicite ; pas sauvegardeautomatique. CaptureSMTP est copie destinataire indépendante.
- Turbopack build CSS EPERM dans environnement ; webpack build réel réussi. Dev local utilise --webpack. Aucun déploiement ni push.

## Précision et design, jalon ~01:11

- L'utilisateur confirme que l'audio original de son essai est correct : défaut de reconnaissance constaté, pas capture corrompue. Le mode français explicite est disponible ; ne pas présenter cela seul comme une correction de précision. Retranscription volontaire conserve les versions précédentes. Aucun audio personnel utilisé pour benchmarks.
- Upgrade retenu pour évaluation : MLX Whisper large-v3-turbo sur Apple M5, licence MIT, conversion publique1.61GB avec SHA256 officiel vérifié au terme du téléchargement. Dépendances verrouillées, adaptateur local sans téléchargement implicite ; activation dépend des mesures réelles. Base reste actif jusqu'à cette validation. Moteur non reconnu/absent échoue clairement, pas de fournisseur externe de secours.
- Read.ai sert de référence visuelle à partir de3 captures fournies : navy/purple, header blanc, onglets, rapport ouvert et panneau source. Aucune donnée privée des captures reprise, aucune fonction fictive ajoutée. Build et recette navigateur12 étapes réelles verts sur refonte ; a11y labels améliorée après recette, build vert.
- Audit indépendant : blocage upload après échéance même avant purge ; quotas avant transaction de réservation des jobs pour conserver exclusion analyse/retranscription. Expiration audio contrôlée à accès/finalisation/transfert/retranscription, distincte suppression des autres contenus.
- Messages d'échec worker : seules ProcessingError contrôlées exposent leur texte ; erreurs validation/modèle génériques pour éviter fuite de sortie IA dans un partage restreint.

## Identité permanente des comptes ~01:22

Deux régressions réelles isolées ont prouvé fuite entre comptes et résurrection de JWT après delete/register avec IDSQLite réutilisé. Correction : User.account_uid UUIDparcréation, migrationAlembic0007 additive sansrebuild, jetons liés à UID et anciennes sessions refusées. Réunions owner_uid, notifications filtrées par réunion/UID, mail.owner_uid migrationdomaine004. Backfilllegacy explicite parchronologie prudente, jamaisIDseul pourmail. Migrationlocale testée/appliquée après backup et arrêtworker :13réunions/22mail liés, aucunorphelin/chronologieambiguë ; contenu utilisateur préservé. Backups privés dans.memora/backups exclusGit. ModèleDBnullable pourSQLiteADDCOLUMNnon destructif ; invariantUID assuré parORMUUIDdefault et refusJWTsansUID, uniqueindex.

## Choix ASR validé ~02:47 GMT

Whisper large-v3-turbo MLX retenu final+direct sur Apple Silicon, après SHA256 officiel et essais réels. Le premier MLX brut traduisait l’anglais et hallucinait sur bruit : non activé, corrigé par VAD Silero300ms/marge200ms et langue indépendante par portion vocale. Sept cas finaux inspectés : FRcomplexe17,5→2,5%WER normalisé, Python/EN0%, bilingue3,85%(accentMemora), silence/bruit0texte. Audio synthétique15min54,29s, phrase finale et deux langues présentes, pic2,83GiB. Limites portions très courtes/alternance sans pause/voix faible ; aucun benchmark naturel2h. Les critères techniques du benchmark ne sont pas des seuils imposés par utilisateur.

Inférences locales sérialisées par appel/lot pour limiter cumul mémoire ; ne contrôle pas les autres apps utilisant Ollama. Proxychat600000ms configurable1000–1800000, REST120000. Dépassement504 explicite, calcul backend éventuellement encore actif. Aucun fallback externe/simulé.

Nouvelle installation Apple Silicon native choisitMLX ; autres plateformes CPUbase explicite et précision inférieure documentée. Configuration existante conservée, installateur prépare le moteur réellement configuré, téléchargeur pinned/SHA/idempotent offline. Cette machine utilise maintenantMLX pourlesdeuxphases.

## Modèle final et reprise durable ~03:10 GMT

Gemma4:e4b existant remplace Qwen pour rapport/chat après reproduction d’une décision future reformulée comme fait accompli. Six rapports courts/3chats, long3lots/manque/injection et52contrôles intégrés avec six rapports relus ont justifié ce choix. Poids~6,1Gio, Apache2.0, RAM libre minimale19% observée sur un essai ; sérialisation locale maintenue. Pas de téléchargement Ollama ni garantie universelle ; classification discussion/action encore perfectible.

Migration006 stocke phase/source_version/result_report_id séparés de version initiale du job : publicationASR et continuation atomiques, rapport et accusé durable atomiques. Un crash ne doit ni perdre la continuation ni recréer source/rapport. Les traitements historiques sans checkpoint ne sont pas interprétés arbitrairement : état processing sans jobactif devient failed/relançable, contenu conservé, aucune inférence automatique. Migration avec sauvegarde appliquée sur main après0jobsactifs.

## Recherche précision supplémentaire — décisions08:58 GMT

Pas de correcteur LLM réécrivant la transcription : fluidité ne prouve pas fidélité audio. Rejet du lexique global après substitution systématique d'un nom voisin et perte de phrase bilingue. Température0seule/best_of5 n'apportent aucun changement sur62cas chacun. Whisperlarge-v3 complet rejeté comme remplacement global après traduction non demandée et régression bilingue ; routeFR explicite testée améliore propre mais régresse sous bruit, donc non activée.

ParakeetTDT0.6Bv3 évalué en laboratoire isolé pour architecture distincte et horodatages natifs, licenceCCBY4avec attribution (pasMIT), poids2.508GB distincts deTurbo/Ollama ; aucun téléchargement externe d'audio. Sa sortie ne fournit pas de langue/confiance exploitable : ne pas les inventer. Décision d'intégration en attente des comparaisons.

La référence personnelle fournie est reformulée : mesureWER invalide, ne pas publier de précision personnelle. Autorisation explicite limitée à une copie locale de l'enregistrement désigné ; original inchangé et détails exclus des notes/logs. Les preuves synthétiques sont distinctes.


##25/10 — choix final activé après mesures

- Français final : ParakeetTDT0.6Bv3 local, MLXAudio0.6.1, CC-BY4/attribution ; anglais/auto/direct restent WhisperTurbo. Route issuev2 puis validée réserve indépendantev3, pas simple choix du plus gros modèle. Lexique global/fullWhisperglobal/Qwenclassification rejetés sur régressions réelles. Les modèles de comparaison restent sur disque, aucun téléchargement additionnel nécessaire.
- Analyse multi-lots V12 : existence initiale d’une tâche séparée de son évolution temporelle ; confirmations/refus/citations ne valent pas annulation. IDs source contraints au lieu d’extraits recopiés. Veto conservateur et marquage À vérifier si suppression non étayée. Résumés chronologiques préservent historique ; pas promesse de réduction illimitée. Résidu doublon de décision assumé/documenté.
- Activation après sauvegarde privée/garde0jobs/aucunecapture récente ; redémarrage local, intégrité/comptages inchangés etHTTP200. Aucun retraitement automatique ni référence personnelle ajustée pour obtenir un score.
- Preuves séparées : recette55contrôles chargéeV11 sur parcours court/ASR ; backendfinal242tests et fusionréelle ciblée/fullV12. Ne pas attribuer rétroactivement55contrôles au codeV12 ni prétendre90% universel.


### 25 octobre — choix français et indicateurs de capture

Le mode français final revient à Whisper Turbo conditionné `fr` en tâche `transcribe`. Parakeet est plus précis sur la réserve synthétique testée, mais ne peut contraindre la langue ; le choix explicite utilisateur doit atteindre un paramètre de décodage réel. Full conditionné n’améliore pas le WER global et coûte davantage ; certains noms sont néanmoins mieux reconnus. Aucun correcteur/traducteur LLM silencieux ajouté, aucun audio personnel retraité automatiquement.

Visualisation de capture dérivée du flux MediaRecorder existant, sans deuxième acquisition microphone ni propriété des pistes ; nettoyage limité aux nœuds/contexte du visualiseur. Le niveau n’atteste pas la sauvegarde des fragments. Transcription bornée et sources du résumé/sujets repliables, citations essentielles conservées. Outils intervenants/lecture : surfaces neutres et disposition compacte adaptative, contrôles de sécurité inchangés.


### 25 octobre — capture en arrière-plan et veille

Le défilement de l’onde est un historique de pics réels ; l’affichage ne commande jamais la capture. Changer d’onglet déclenche un flush sans pause ni arrêt. Éviter toute promesse impossible d’enregistrement pendant suspension physique de la machine : Screen Wake Lock est limité aux pages visibles. Sur ce backend macOS local, une assertion caffeinate-i bornée120s, renouvelée30s, empêche uniquement la veille automatique ; cleanup et autorisation propriétaire/UID/loopback/capture assurés. Aucun réglageOS permanent, son silencieux ou restriction navigateur contournée. Tests des baux et assertions natifs séparés des mocks WakeLock/HTTP du harness ; micro et veille physiques non testés.

## Capture persistante et conversation

Le layout racine possède la session média via CaptureProvider ; CaptureSlot ne possède que son ancre DOM et les callbacks de page. Le portail expose les contrôles complets sur la réunion, la barre fixe ailleurs. Une autre réunion ne remplace pas une capture active. Déconnexion/expiration/changement de compte arrêtent les pistes ; une acquisition tardive est nettoyée. Le rechargement complet et la fermeture du navigateur restent des interruptions.

Chat déplacé en zone principale sur son onglet, lecteur conservé pour citations. Contexte conversationnel limité aux six derniers tours entiers/6000caractères, même réunion/acteur/version/droits ; omission annoncée. Les réponses précédentes ne constituent pas une preuve. Après inférence, accès/version sont revérifiés avant insertion. Pas de nouvelle dépendance, migration ou fournisseur.

Rendu optimisé Next16/PPR : CaptureProvider conserve les enfants sans conteneur DOM permanent ; un espace réservé est ajouté seulement pendant capture hors page. A/B production isolé : wrapper initial→React418 au rechargement réunion brouillon ; mêmescript avec enfants directs→0erreur ; retour au wrapper→418 reproduit. Le serveur dev n’exposait pas ce défaut. Aucun suppressHydrationWarning ni exception de test ajoutée.

Bandeaux : progression prioritaire sur rappel de rapportpérimé pendant traitement. Affichage fallback « Intervenant » remplace « Voix à vérifier » ; une absence de groupement acoustique n’est jamais convertie arbitrairement en numéro. Aucun changement transcriptionstockée ou déclenchement de diarisation sur anciens audios.

Chat : corriger le rendu des réponses historiques aussi, sans réécrire la base. Seuls groupes entièrement composés de marqueursuN entre parenthèses/crochets sont masqués ; identifiantsmétier et nombres restent intacts, citationsautorisées restent sousVoirlessources. Pas de correspondanceuN→timestamp inventée : les unitésinternes du modèle ne sont paslesIDssegmentspublics. Sourcesdédupliquées/bornées et questionrepère pendant défilement.
