# Audit fonctionnel frontend — 25 octobre 2026

Références relues : instructions frontend/AGENTS.md, agents/requirements.md, PDF pages 2, 5, 6 et 9 (extraction compacte pour export, reprise, transcription et permissions). Le PDF §1.3 place explicitement l’export bureautique hors exigences validées : aucun export PDF/Word n’a été inventé. Le téléchargement audio utilise la permission audio et un MIME conservé ; les ressources restent autorisées côté backend.

## Défauts corrigés

- Import partiel : suppression des finalisations manuelles propres à la capture. L’import se finalise uniquement après transfert de toutes les tranches du fichier sélectionné. Une resélection complète reprend par rejeu idempotent ; elle peut retransférer des tranches déjà confirmées.
- Interruption explicite du transfert : AbortController, conservation des fragments locaux, aucune analyse lancée après interruption ; navigation hors du composant annule aussi les requêtes d’import. L’état interrompu attend la fin de l’opération locale en cours.
- Resélection du même fichier : valeur de l’input remise à zéro après sélection pour déclencher le prochain changement.
- Régénération : accessible à l’invité disposant effectivement du droit edit, pas réservée arbitrairement aux comptes ; les invités en lecture seule ne voient pas cette action. Le serveur reste l’autorité.
- Révocation/expiration : une réponse 401/403/404 confirmée au polling partagé retire la vue en mémoire et arrête le lecteur ; cela ne prétend pas rappeler les copies déjà téléchargées.
- Suppression : navigation seulement après succès serveur ; purge des fragments IndexedDB de la réunion. Une suppression concurrente avec capture/transfert/sauvegarde actif est empêchée et expliquée pour éviter un fragment orphelin ajouté après purge.
- Accès direct à une réunion : hydratation AuthGate stabilisée même si la session devient disponible avant l’hydratation du segment principal.
- Formats proposés annoncés avant transfert et décompte des liens configurés dans le bandeau propriétaire (incluant honnêtement les liens expirés/révoqués).

## Preuve ciblée

frontend/tests/memora-import-recovery.mjs : sept jalons PASS, APIs entièrement synthétiques interceptées. Test exécuté sur une copie standalone éphémère en 127.0.0.1:3002, BACKEND_URL pointant un port injoignable ; aucun backend, compte ni microphone réel utilisés. Le serveur éphémère et sa copie ont été retirés après le test.

Vérifie interruption sans finalisation, impossibilité de supprimer pendant transfert, resélection complète en trois tranches avec finalisation unique, régénération invitée autorisée/lecture seule interdite, révocation sans rechargement, suppression échouée sans navigation et purge locale après suppression réussie. Aucune exception JavaScript sur la dernière exécution, y compris accès direct hydraté.

Log : agents/logs/frontend-import-recovery-tests.log. Lint, TypeScript et build production réussis après les corrections. L’application utilisateur sur le port 3000 n’a pas été redémarrée par cet audit ; ces derniers correctifs requièrent son prochain redémarrage contrôlé.

## Limites non masquées

Ce test de contrat UI ne valide pas le backend, la précision ASR, le modèle d’analyse ou les vrais emails. La recette réelle complète antérieure conserve ses propres preuves. Veille/verrouillage/microphone physique/Safari/iOS, diarisation automatique et précision de tous les formats annoncés restent des limites décrites dans la matrice centrale. Les coupures inconnues ne sont pas transformées en plages temporelles précises inventées. Les choix auto/fr/en et les badges de langue respectent la portée déclarée par le fournisseur ; la détection initiale dominante n’est pas présentée comme une détection de chaque segment.
