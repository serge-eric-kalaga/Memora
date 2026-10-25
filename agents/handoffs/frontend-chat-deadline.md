# Délai du proxy chat — 25 octobre 2026

Variable serveur : `MEMORA_CHAT_TIMEOUT_MS` (millisecondes). Défaut : 600000 (10 minutes). Valeurs finies bornées à 1000–1800000 (1 seconde–30 minutes), parties décimales tronquées. Valeur absente, vide ou non numérique : défaut 600000.

S’applique uniquement à `POST /mapi/meetings/{id}/chat`. Les autres opérations conservent leur délai 120000 ms. Configuration lue côté serveur à chaque requête ; aucun secret ni détail du modèle n’est exposé. Ajuster le délai ne constitue pas une promesse de latence ni une capacité illimitée.

À dépassement : réponse 504 explicite, réunion conservée ; le message informe que le traitement serveur peut encore se terminer et invite à consulter l’historique avant de réessayer. Aucune troncature des sources, réponse simulée ou fournisseur de remplacement ajouté. Une requête abandonnée côté proxy ne prétend pas annuler le calcul backend.

Preuves :
- `frontend/tests/memora-proxy-timeout.test.mjs` : 2 tests PASS (défauts, bornes, configuration invalide et séparation REST/chat).
- `frontend/tests/memora-proxy-timeout-integration.mjs` : vrai frontend Next reconstruit + backend HTTP synthétique sur ports loopback éphémères ; chat normal 200 complet, backend retardé 1600 ms avec configuration 1000 ms → 504 explicite, REST retardé 1150 ms → 200 malgré configuration chat 1000 ms. Trois jalons PASS.
- Logs : `agents/logs/frontend-proxy-timeout-unit.log`, `frontend-proxy-timeout-integration.log`, `frontend-proxy-lint.log` ; TypeScript, lint global et build production également réussis.

Les deux serveurs de test et la copie temporaire ont été arrêtés/supprimés. Aucun service utilisateur sur le port 3000, backend utilisateur ou fichier IA n’a été redémarré/modifié. Le bundle est prêt pour le prochain redémarrage contrôlé par l’agent principal.
