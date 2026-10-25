# V5 plan de statuts — prêt, GPU non utilisé

Après échec réelV4 (rapportcopié nonréconcilié), approche report à sortie étroite. ai.pyhelpers/reconcile/report et tests uniquement modifiés ; fonctiontranscribe etfactoryROOT conservées. N’annonce pas résolutionréelle tantplansNN puisfull2casnonvalidés.

Modèle interne StatusPlan : uneaffectation parIDcandidat avecenumcurrent/superseded/cancelled/not_action/unresolved, référencesoriginales etjustificationcourte. Couvertureexacte exhaustive/doublons/IDsinconnus invalidenttoutplan. Superseded/cancelled requièrent preuveexplicitementultérieure enpositionlecture, pas enID/datelexicale. Current/not_action/unresolved doivent citer sourcepropre. not_action seulementpourcatégorieactions ; sourcesétrangères/structureinvalide→ProcessingErrorfixe.

Les textesLITTÉRAUXréférencés sont fournis à côtédescandidats etsource_order(position,start,end,speaker,text_ref). Unechaîneexactementidentique peut êtrestockéeunefois literal_texts maischaqueID/positionresteprésent ; aucunrésumé/coupe/nonréférencement detextepourfairetenircontexte. Budget14000chars inchangé ; tailleirréductible→erreurclaire, ycompris quandlesfaitsuniques nepeuventpasêtrecondenséssansperte. Ceplanafiltredesitemsmaisneréécritpaslesfaits pourréduiretaille, doncun trèsgrandensemblecourant peutéchouerexplicitement ; limiteacceptéeROOT plutôtque résultatfaux/tronqué.

Application déterministe : currentcopiéexactement ; superseded/cancelled retirésdescategoriesactives etgardésdanssummary avecpréfixeHistorique—remplacé/annulé etunionrefsancienne+preuveultérieure. Tracehistoriqueexacte dédupliquée siidentique. not_actionretiré desactions sans inventerautretravail. unresolvedconservéavecÀvérifier etpreuves. Si summarycourantvide,copieexactedeclaimsrestantsdansautreslistes, jamais générationplaceholder ; historiqueajoutéensuite, videsansfaitéchoue. Aucune substitutionlexicale métier/SECRET/nom/montant/jour.

Chatgarde réductionchronologiqueV4 réellePASS, avec texteslittéraux complets maintenant ; IDsinline interditsparprompt sansregexcontenu, artefactpasdéclaréréparé. Singlebatchreport/chatinchangés. AnciennespreuvesV3/V4restentliéesàleursha, paspreuveautomatiqueduV5.

Testsmeaningful54PASSen0.39s : suiteAI+nouveauréconciliation+ASRroutingROOT+MLX. Nouveauxguardsplandisposition/proprepreuve/ordreultérieur, coverageexhaustive, fallbacksummaryexacte/histoire, deduplittéralpréserveidentités, faitsindépendantsconservés. Deuxancienstestschatontétéchangésversfixturescourtesavecfrontièredebatchforcée : ilsvisentprovenance/réponsesanssources, pasle volumetexte ; lecontexteoversizedestréellementtestéparguarddédiés. RuffPASS.

Probe2plansseuls préparé sansGPU : scripts/memora-qa-reconciliation-plan.py --run. Reconstituepartsdepuisvraiextractionbaselinecross-batchV1etcorpusfigé, vérifieaucunitemperdu ; provenancebaselinehash/corpusha/aisha. Lesappelsmapnesontpasrejoués, àannoncer**plan-only**, pasfreshE2E. Payloadsmesurés12512chars/20candidats et11204chars/14candidats sous14000. Defaultdryrunnechargepasmodèle. Sortieuniqueanalysis-plan-v5.json refuseécraser.

AprèscréneauROOT etpreuveplanbonne, full2casfreshavec --outputanalysis-cross-batch-v5.json, puisnouvelongholdoutindépendant figéavantoutput. Aucuneinférence faitepourleV5parcetagentàcetétat. OwnershipAIenattentevalidation/intégrationROOT.

## Probe V5 et préparation V6

Le premier plan réel V5 a été rejeté par la garde de catégorie : `not_action` appliqué hors `actions`. Le processus a terminé avec code1 ; second cas non exécuté. Preuve conservée dans `agents/logs/analysis-plan-v5.log`. Lacune : le brut du plan était seulement en mémoire et n'a pas été enregistré avant le rejet ; aucune attribution plus précise du candidat n'est donc prouvée.

V6 contraint maintenant le schéma de génération avec deux branches anyOf : IDs des candidats actions autorisent not_action ; IDs des autres listes l'interdisent. Cardinalité exacte ; garde locale et provenance ultérieure inchangées. Aucune conversion implicite de statut. Le probe persiste désormais chaque réponse brute synthétique avant validation et enregistre l'erreur éventuelle, puis poursuit le second cas. Pas de nouvelle inférence avant créneau ROOT. 55 tests AI/reconciliation/ASR ciblés réussis en0,65s ; Ruff check/format conformes. Il reste à vérifier que le moteur JSON local accepte effectivement ce schéma et classe les faits correctement.
