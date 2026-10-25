# Isolation des incarnations de comptes

Défauts reproduits sur SQLite auth et domaine temporaires, avec vrais JWT et routes réelles : supprimer le plus grand User.id puis recréer un autre utilisateur réutilisait l'ID et exposait les réunions précédentes ; recréer le même username rendait aussi son ancien JWT valide. Aucun compte courant consulté/modifié pour cette reproduction.

Correctif auth : `User.account_uid` UUID32 généré pour chaque création ; login fournit l'UID du compte effectivement authentifié ; validation JWT exige cette incarnation. Les anciens jetons sans claim sont invalidés intentionnellement et nécessitent reconnexion. Helper interne create_token complète l'UID courant si omis pour compatibilité ; ce helper ne remplace pas le login.

Migration auth0007 : ADD COLUMN nullable + UUID aléatoire par ancienne ligne + index unique nommé. Nullable est intentionnel pour SQLite sans reconstruction et cohérence ORM/Alembic ; le modèle génère l'UID et le contrôle JWT refuse une incarnation absente. Test migration vérifie conservation lignes/rootpage, unicité/stabilité UUID et `alembic check` sans diff sur schéma complet0006→0007. SQL hors ligne rendu sur SQLite ; fonctions UUID dialectales pour PostgreSQL/MySQL non exécutées dans ces tests. Downgrade0007 explicitement refusé pour éviter réouverture de la faille.

Domaine : root intègre l'accès par owner_uid. `store.init` ajoute mail.owner_uid de manière additive (migration004) ; queue_mail prend owner_uid facultatif pour compatibilité, le rapport passe owner_uid de réunion. Un mail sans UID ne doit pas devenir visible par simple égalité d'ID entier.

## Procédure à relire avant application aux données existantes

Aucune migration/backfill de la base courante n'a été appliquée par cet agent. Arrêter les services et conserver une sauvegarde auth+domaine cohérente ; charger explicitement la configuration locale correcte sans afficher ses secrets.

1. Depuis `backend/` : `.venv/bin/python -m scripts.migrate` (migrations et contrôle ORM existants), ou `.venv/bin/alembic upgrade head` puis `.venv/bin/alembic check` si procédure adaptée et relue.
2. Initialiser la migration domaine004 par procédure normale, worker arrêté pendant revue de liaison.
3. Depuis racine : `backend/.venv/bin/python scripts/memora-bind-owners.py --dry-run` (mode par défaut, aucun enregistrement écrit).
4. Vérifier les compteurs anonymes, puis même commande `--apply` uniquement après revue.
5. Redémarrer puis reconnecter les comptes, anciens JWT rejetés intentionnellement.

Backfill : n'utilise jamais l'entier propriétaire seul. Le compte courant doit avoir un UID et être créé avant la réunion ; une réunion dans la même seconde que date_creation SQL est considérée ambiguë et reste sans liaison. Les comptes absents, dates manquantes et réunions antérieures au compte restent non liés. Les réunions déjà liées ne sont pas réattribuées. Le mail ne peut être lié que via `invite:<meeting>:…` ou `report:<report_id>` et la liaison de sa réunion ; un mail sans réunion prouvée reste NULL. Test dry-run vérifie strictement aucune modification, apply puis réexécution stable.

Tests ciblés : `backend/.venv/bin/python -m pytest backend/test/test_alembic.py backend/test/test_memora_account_lifecycle.py backend/test/test_memora_owner_binding.py -q` → **7 passed,0,96s**. Ruff sur tous fichiers modifiés réussi. Première passe full isolée : `agents/logs/account-incarnation-tests.log`,140passed/3failed/3skipped ; échec SQL offline corrigé ensuite et deux tests queue_mail sans UID à adapter par intégrateur. Ce log n'est pas une réussite complète finale. L'ancienne sélection `account-auth-tests.log` utilisait un schéma de test non migré et a échoué ; conserver comme diagnostic, pas preuve verte.

## Contrôle CI corrigé après intégration

La migration0007 conserve son `downgrade` refusé et expose `irreversible_security=True`. `backend/scripts/check_migrations.py` inspecte le head : si cette frontière est le head, il teste réellement le roundtrip de son prédécesseur0006 AVANT d'installer0007 et de lancer `alembic check`. Si un futur head est réversible, il teste normalement ce head. Le message nomme explicitement la révision testée ; aucun downgrade de0007 n'est annoncé.

`backend/.venv/bin/python -m pytest backend/test/test_migration_check.py -q` : **2 passed,0,41s**, contrôle positif réel sur SQLite jetable + rejet de champ ORM sans migration. Exécution CLI réelle `cd backend && .venv/bin/python -m scripts.check_migrations` sous configuration synthétique et base temporaire : **exit0**, aucune différence ORM, `head0007_account_uid` / `roundtrip0006_access_status`, données conservées. Preuve : `agents/logs/migration-ci-check.log`. Ruff format/check réussis sur les trois fichiers modifiés. Aucune base courante touchée.

## Suppression de compte et liens invités

Défaut supplémentaire reproduit : après suppression HTTP du compte, lien invité et fichier audio restaient200/200 malgré isolation des nouveaux comptes. Correctif : migration domaine005 et tombstone irréversible d'incarnation ; la suppression valide d'abord cette barrière dans une transaction propre puis supprime fichiers et données dans une seconde transaction. Toute purge repose sur owner_uid, jamais sur l'entier réutilisable. Une réunion héritée sans liaison UID sûre refuse aussi l'accès invité.

Le hook s'exécute avant suppression SQL du compte. Si suppression de fichiers échoue, l'API renvoie503 : compte conservé, accès Memora bloqué durablement, IDs de réunions conservés par rollback pour réessayer DELETE. Les fichiers déjà retirés pendant une tentative partielle ne peuvent pas être restaurés. La tentative suivante reprend sans effacer le tombstone ; une réinscription reçoit un autre UUID. Si suppression auth SQL échoue après purge, le compte peut subsister avec ses données Memora déjà supprimées ; la suppression du compte doit être réessayée. Aucune transaction distribuée n'est revendiquée.

Création vérifie le tombstone sous BEGIN IMMEDIATE après validation/quota, pour refuser une requête déjà authentifiée avant la suppression. Worker ne publie ni rapport ni mail pour l'UID bloqué ; l'envoi SMTP local et son changement d'état sont verrouillés avec la vérification du tombstone, sans prétendre rappeler un email déjà accepté avant la barrière.

Preuves ciblées :41tests domaine/lifecycle/audit réussis3,42s ; scénario IOerror conserve compte et références, invité/audio404, création par session encore valide403, aucun appel SMTP, retry purge dossier/mail/notifications. Quatre variantes HTTP/SQL direct + même/autre username vérifient que l'isolation des incarnations demeure indépendante du hook. Ruff réussi. Log complet de relance : `agents/logs/account-cleanup-tests.log` (attendre résultat final avant déclaration de succès).

Résultat relance complète cleanup : **148passed,3skipped,1warning17,67s**, `agents/logs/account-cleanup-tests.log`. Après cette passe, ajout de la fermeture des accès invité/propriétaire pour réunion héritée sans owner_uid et de son test : lifecycle+audit **13passed1,75s**, Ruff réussi. Le prochain total complet devrait augmenter d'un test ; ne pas présenter cette prévision comme résultat exécuté.
