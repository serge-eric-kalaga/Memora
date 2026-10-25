# Jalons et critères de fin

| Jalon | État et critère vérifié |
|---|---|
| Audit PDF/template et configuration | Terminé :16pages lues, socle réutilisé, références en lecture seule, exigences et hypothèses dans requirements/decisions. |
| Parcours vertical réel | Terminé sur données synthétiques : compte→réunion→audio→ASRMLX→rapportGemma→chat sourcé→partage invité. |
| Capture/import et versions | Implémentés et testés : pause/reprise, IndexedDB, interruption réseau, fragments idempotents, corrections/historiques, régénération. |
| Permissions et cycle de vie | Implémentés et testés : liens/password/expiration/révocation, droits backend, notification/captureSMTP, archive/suppression/rétention/config. |
| Qualité ASR et génération | Benchmarks réels terminés,7cas FR/EN/mixte et15min synthétiques ; inspection humaine de6rapports Gemma. Limites dans testing.md, pas de garantie sur réunion naturelle. |
| Durabilité après crash | Terminé :006 intégré/migré,177tests backend PASS ;4SIGKILL réels/6contrôles et dernière recette52/52post006 PASS. |
| Livraison locale et continuité | Services démarrés et HTTP200 ; documentation et mémoire disponibles. Nettoyage terminé et services principaux recontrôlés ; bilan local, sans prétention production. |

Ordre de reprise et action courante : memory/state.md. Les critères de recette détaillés sont dans requirements.md ; commandes et résultats dans testing.md. Aucun jalon déclaré terminé sur simple scaffolding.

## Jalon supplémentaire : précision mesurée — livré localement

1. Recherche primaire et essais comparés terminés ; méthodes rejetées et raisons conservées.
2. Route française Parakeet sélectionnée après v2 puis validée sur réserve indépendante v3 ; anglais/auto/direct conservés sur Turbo. Tests95s et deux chaînes ASR→rapport réels.
3. Extraction courte améliorée ; cohérence multi-lots V12 vérifiée sur cinq plans réels et un cas complet après échecs conservés. Limite de duplication À vérifier persistante.
4. Dépendances verrouillées, backend242PASS, préparation48PASS, frontend lint/types/build ; recette isolée55/55 V11, vérifications V12 distinctes.
5. Activation locale après garde jobs/capture, sauvegarde privée et contrôle de préservation ; quatre services HTTP200. Aucune réunion personnelle retraitée.

Le seuil général90% n’est pas acquis : résultats synthétiques bornés, noms/bruit encore difficiles, référence personnelle reformulée non scorable. Prochaine action : essai volontaire dans l’application puis revue des passages importants. Détails dans state/testing/requirements et handoffs référencés.
