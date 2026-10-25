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

## V1.1 — confiance et correction (livrée localement)

1. Contrôle micro explicitement activé, choix entrée/niveau/extrait et nettoyage vérifiés.
2. Lecture synchronisée, boucle/raccourcis et comparaison corrections, historique intact.
3. Revue humaine versionnée décisions/actions et renommage intervenant global, permissions/versions vérifiées.
4. Diarisation locale réelle évaluée synthétique ; intégration volontaire seulement après preuve, blocages/modèles documentés.
5. Tests backend/frontend, recette navigateur isolée, activation locale prudente et commits sans coauteur.

FinV1.1 : les cinq jalons ci-dessus sont intégrés/vérifiés ; détails testing/state. Activation007 préserve les sources et0jobs/HTTP200, commitlocal sanscoauteur autorisé. Limitesvoixnaturelles/overlap/production maintenues.


## Correctifs après V1.1

1. Transcription bornée et citations essentielles : implémentés, preuve layout4vues obtenue.
2. Choix FR : diagnostic synthétique et comparaison26inférences Full terminés ; route conditionnée Turbo retenue, testsprépa/routagePASS.
3. Signal capture : WebAudio existant, aucun nouveau getUserMedia,8contrôlesmontésPASS ; recette Recorder isolée PASS.
4. Outils intervenants/lecture : refonte neutre et responsive, buildPASS, validation visuelle4vues WorkspaceFrame PASS.
5. Fin : recette isolée, garde traitements/capture avant redémarrage, activer config locale, vérifier intégrité/services et commit sans coauteur.

Clôture : activation locale effectuée après garde0jobs/aucun audio récent ; empreintes domaine inchangées, intégritéOK et4HTTP200. Aucun audio personnel retraité. Commit local sans coauteur, aucun push.

## Capture persistante et chat — clôturés localement

1. Sessionmédia portée par layout, barre responsive et contrôle des changements de compte : terminé.
2. Chat principal inspiréRead.ai, historique/sources/suivis et isolementbackend : terminé.
3.315testsbackend,17contrôlescomposants montés et recette réelle22browser+13UI : PASS.
4. Deux défautsproduit observés corrigés (modalcréation retenue, wrapperDOM/PPR), rerun complet sansexception.
5. Activationlocale avec garde et empreintesdomaine inchangées, documentationmiseàjour, commitlocal autorisé sanscoauteur ; aucunpush.

## Reprisevoix dans analyse — livrée

Analyse reprendcheckpointvoix écheccourant accessibleavantnouveaurapport ; nombreconnuoptionnel, versionshumaines/anciennesprotégées.8testsrégression,323backendet17UIfinalPASS ; routeauthstub/moteurslocauxsynthétiquesvalidés21,699s,22browserréelsavantultimesajustementsUI/éligibilité. ContratOpenAPI/SDKàjour, activationlocalepréserveempreintesdomaine. Voirstate/testing pourphasesdepreuve.
