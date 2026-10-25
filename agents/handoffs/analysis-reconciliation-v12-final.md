# V12 — livraison du correctif borné de réconciliation

Code libéré à ROOT : `backend/api/memora/ai.py`, tests `backend/test/test_memora_ai.py` et `test_memora_reconciliation.py`. SHA finaldf3afc645752ec5bebedf45eb195431a4bccb20adc85833743c35a206cb5585c. Aucun changement transcribe, moteur/config modèle, services, base ou données utilisateur. Singlebatch garde extractionV3 ; réconciliation multi-lots est modifiée. Aucun GPU encore occupé.

## Correction et diagnostic

V11 souffrait de deux causes distinctes prouvées dans ses bruts : citations recopiées mal (Alice vraie annulation veto à cause de phrase discontinue/capitalisation), et erreur sémantique vraie (Benoît/Fanny confirmation prise pour remplacement malgré citations exactes).

V12 sépare :
1. Existence initiale d'une action, une seule passe avant la hiérarchie. Micro-contexte original+speaker, enum explicit_assigned_work/proposal/state_or_cancellation/quoted_example/unclear. Propositions, états/constats et exemples retirés des actions, restent dans chronologie avec limitation. Incertain conservé À vérifier.
2. Plan temporel restreint aux actions/décisions/questions. Schéma par catégorie, work_to_do pour tâches, resolved uniquement questions. Résumés/topics ne sont jamais classifiés/supprimés ; copies chronologiques préfixées au timestamp source.
3. Toute suppression proposée est vérifiée indépendamment via event_type explicit_cancel/explicit_replace/explicit_answer/confirmation/proposal/rejection/quoted_instruction/unclear et same_object/adopted/current_at_end. Seuls changements explicites adoptés applicables au même objet peuvent supprimer. Confirmations/refus/propositions/citations imposent veto, original gardé À vérifier avec limitation.

Les preuves sont désormais des IDs source enum : le backend reprend les textes originaux, aucune copie libre d'extrait par LLM. Cela prouve l'origine, pas l'entailment sémantique à lui seul. Ordre de lecture original, pas tri IDs ; contexte borné sans troncature silencieuse. Erreur explicite si synthèses irréductibles ; pas promesse universelle2h.

## Tests CPU

`python3 scripts/memora-test.py test/test_memora_reconciliation.py test/test_memora_ai.py test/test_memora_asr_routing.py test/test_memora_asr_mlx.py -q` : **74PASS,0,41s**. Ruff check/format conforme. Tests de temporalité isolent éligibilité par mock et celle-ci possède ses propres sous-tests dédiés ; pas simulation de qualité IA. Cas : provenance/enums, source étrangère, ordre, budget, veto confirmation/proposition/refus/citation, action premièrepersonne, exclusionétats, ambiguïté conservée, singlebatch inchangé.

## Preuves réelles V12

`analysis-veto-plans-v12.json/log/.review.json`, snapshot `analysis-ai-v12.py` : cinq vrais appels reconcile production avec existence et vérificateurs ; maps réels préservésV10, pas cinq analyses complètesV12. Hashescorpus/baseline/code, bruts et tables inverse IDs sont enregistrés ; source figée pendant exécution.

- Proposition refusée23,784s : Élisejeudi/Nicolaslundi conservés, pasMaxime.
- Réaffectation33,667s : Benoît avantvendredi conservé, pasAriane,4900validé et questionrépondue retirée.
- Hostile refusé24,374s : Fanny avantmardi gardée, accord maintenu, pas instruction hostile exécutée. **Résidu** : ancienne décision maintenue À vérifier en doublon de la confirmation finale, limitation explicite.
- Annulation connue28,785s : actionsvides,4700final, pasconstatannulation commetâche.
- Indépendant14,478s : Mariam20janvier et Rayan28janvier distincts.

Total125,088s ; **5/5 critères factuels ciblés satisfaits**, avec résidu décrit ; pas score de précision générale ni réserve aveugle (cas déjà consultés après échecs).

`analysis-long-reassignment-v12.json/log/.review.json` : **un cas complet productionV12**,3maps + existence + plan + vérifications réels,94,688s. Action unique Benoît/avantvendredi avecsourcefact3 ; Arianeabsenteactive ;4900sourcesfact4+5 ; questionsvides. Résumés conservent4200initial et questioninitiale à leurs timestamps, puis réponse/correction. SourceSHAstable ; RAMlibresystème17–73% sur48samples2s (pas RSS deprocessus). Corpus synthétique uniquement, IDs opaques avecreverse. Pas de questionchat dans corpus, aucune inventée.

Tous échecs V4–V11 préservés ; ces résultats ne les transforment pas rétroactivement en succès. Les quatre courtsV10 réexécutés avantV12 avaient17/18précision,8/8rappel,1chat, identiquesV3 ; ils ne constituent pas un rerunV12. Recette API/browser/ASR complète de ROOT importeV11SHA327822… et doit rester attribuée à cette version, même si singlebatch/ASR sont inchangésV12. Le correctifV12 est prouvé par tests ciblés+casréels ci-dessus, pas nouvelle recette complète navigateur.

## Limites à livrer clairement

Pas90%global, pas étude voix réelle/naturelle2h ; classifications et décisions du modèle restent perfectibles. Un résultat À vérifier est incertain, jamais un fait confirmé. Dupliquats chronologiques/maintien possibles, signalés. Les synthèses très volumineuses peuvent échouer explicitement si le contexte ne permet pas réduction sans perte. Aucune activation main, migration/restart ou donnée privée manipulée par ce sous-agent.

Validation d'intégration communiquée par ROOT après ces contrôles : suite backend complète **242PASS,3ignorés** et Ruff global **62fichiers conformes**. Ce résultat provient de ROOT, pas d'une seconde exécution par ce sous-agent. Activation main/sauvegarde privée restent à sa charge après garde jobs/uploads. Aucun autre calcul IA demandé ni lancé.
