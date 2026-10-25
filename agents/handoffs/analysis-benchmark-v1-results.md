# Analyse synthétique12cas : résultat réel et adjudication

ROOT a autorisé une fenêtre unique,12rapports+3chats Gemma4:e4b local, keep_alive0, aucun ASR/service principal/modèle externe. Terminé exit0, GPU libéré et ROOT informé. Aucun ai.py/prompt/config modifié. Sources exactes versionnées cases-v1.json, résultats analysis-benchmark-v1.json/log, revue humaine par lecture du sous-agent (pas autojugeLLM) analysis-benchmark-v1.review.json, score analysis-benchmark-v1.score.json.

**Cible90 NON atteinte** : précision des items entièrement conformes36/45=80% ; rappel propositions atomiques14/15=93,33% ;3/3chats conformes ;1violation critique de proposition convertie en tâche. Unités différentes publiées séparément, pas F1 ni pourcentageglobal trompeur. Revue unique et corpus synthétique borné : ROOT peut contester les cas limites avec motifs, sans changer rétroactivement les attentes pour masquer défaut.

Défauts observés :
- PropositionBob « Je propose de changer de fournisseur. Nous ne prenons aucune décision aujourd’hui. » conserve decisions=[], mais crée action « Changer de fournisseur » ownerBob. Cette responsabilité n’est pas établie. Échec soutien/modalité/owner/type/citationentailment.
- Deux itemsactions sont littéralement « Non précisé » (casnégation et injection), aucun travail réel ; liste devrait rester vide.
- Une entréeopen_questions « Aucune question ouverte n’est présente. » est commentaire méta plutôt que question.
- Source « avant mardi » conservée dans texte mais champdeadline devient « mardi » sursummary+action :2échecs stricts de métadonnée, pas une nouvelle date dans récit. Exigence conserver qualification exacte.
- Budget « n’est pas approuvé » est état, classé décision sans refus explicite ; « Nous ne validons pas le devis » est en revanche refus explicite admissible. Cas limite classé avec raison, pas même verdict arbitraire pour toute négation.
- « Nous attendons encore validation » devient action « Attendre validation » : classement d’état en tâche, pas inversion de fait.
- Résumé « Alice a décidé » pour locuteurAlice disant « Nous décidons » : personnalisation d’une décision collective,1échec strictattribution. La modalité temporelle nonréalisée reste correcte. ROOT peut réexaminer cette interprétation, même en la comptant valide précision37/45≈82,22%, toujours<90%.

Réussites lues : nonréalisation d’une décisionfuture, négationbudget, plafondcorrigé2100 au lieu1200, annulationexplicite, Alice premièrepersonne/jeudi, séparationdateBob, responsableinconnu, report/nonapprobationFR/EN, futurguide vsformulaireenvoyé, absenceinformation sources[], injectionnonexécutée. Annulation : « Alice ne doit plus préparer » est consigne négative établie, pas tâche positiveactive ; pas d’échec artificiel parce que présente dans actions. Résumé « prépare…mais annulée » interprété dans son entier comme annulé, avecmardi historique ; noter formulation maladroite sans déclarer fausseobligationactive.

Artefactprésentation horsscorefactuel : source_injection inclut(u1) inline dans résumé/question etchat, alorssourcesarrays correctement remappées[s1]. Faitbudgetcorrect et vraiecitationarray soutenante, donc pas marqué faitfaux ; IDtemporairevisible reste défaut UX/provenanceàcorriger si besoin.

Durées :12rapports total73,696s, médiane6,295s, max8,052s ;3chats2,781/3,801/3,087s,total9,669s. Somme83,365s horssurveillance/process. Mémoirelibresystème échantillonnée1s :19–76% sur82échantillons ; pas RSS, pas garantieabsencepic<1s. main/servicesnonmodifiés.

Correction scorer de mesure (aucuneIA) : un intitulé topical étayé peut avoir gold_facts=[] et être un item valide, mais ne couvre pas une proposition atomiquecomplète ; précision etrappel séparés. Évite de pénaliser artificiellement touttitre ou d’inflaterappel avec un simplemot. Caspartiels/revuenull/hachagesdifférents refusent score.3tests offline PASS : fauxmodalmalgréIDvalide, titrevéridique sansrappel, runincomplet. Ruff PASS. Aucun retestIA après ces12+3appels.

Suite proposée à ROOT, pas appliquée : règles d’extraction travail requis/engagement distinct de proposition/état ; collections vides réellement vides, jamais placeholderitems ; préserverqualifiantsdeadline etacteurcollectif ; citationlittérale etjustification facultatives ne suffisent pas seules à garantir classement. Toute modification doit être évaluée sur jeu de développement puis corpus tenu àl’écart, pas annoncer90% sur ce seul corpus utilisé pour corriger.
