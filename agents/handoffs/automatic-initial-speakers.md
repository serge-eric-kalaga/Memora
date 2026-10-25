# Identification des voix automatique au premier traitement final

Worker et tests libérés à ROOT, aucuncommit/main/service/data touché. Paramètre interne de création ajouté par ROOT dans routes.py : settings.auto_diarization_new_meetings, bool figé lors de création selon MEMORA_AUTO_DIARIZATION (défaut1). Aucun nouveau paramètreadmin, ni modificationstore/DEFAULTS, ni migration. Les snapshots existants sansflag restent exclus, y compris drafts existants. Live et retranscriptions existantes ne déclenchent pas cette étape automatiquement.

## Parcours durable

Uniquement premier pipeline sourcev0 avecflagTrue et parole reconnue :

1. ASRfinale publie transcriptionv1 intacte +checkpointjob phase `diarize_initial`, source_version1, même transaction.
2. Séparation locale sur copieaudio avec verrou lourd commun ai._lock, après ASRdéchargée. Identité vocale estimée par vrai moteur Resemblyzer existant, pas remplacement «inconnu→1». Métadonnées/incertitude/candidats conservés. Texte/IDs/timestamps vérifiés immuables ; provider reçoit copie pour détecter même une mutationinplace.
3. Succès : labels dans nouvelle transcriptionv2, éditionaudit automatic_speaker_separation/provenance/previous_version1 ; metadata meeting.diarization, automatic_diarization.statecompleted. Checkpointphase report/source2 atomique avec cette publication. Rapport utilise v2 donc nomsneutresestimés ; aucun ancienrapport écrasé.
4. Échec provider/nonpréparé/malformed/mutation : ASRv1 conservée, phase report/source1, automatic_diarization.statefailed +warninggénérique sans détailprivé ; rapport continue avec ASRv1 et avertissementlimitations. Nettoyage snapshot échoué ne perd pasASR, avertissement stockage.

Reprise phasepending rechargeASRv1 et refait seulement étapevoix, pas ASR. Reprise phase report aprèscommitlabels rechargev2 et ne refait niASR ni séparation. Aucuncheckpoint existantphase report n'est réinterprété rétroactivement comme pending. Correction/utilisateur/autrejob plus récent gagne : versions/active_job/owner tombstone revérifiés avant publication ; sortie tardive abandonnée.

Le modèle peut s'abstenir : groupes incertains ou segmentASR contenant deuxvoix restent nonattribués, pas de faux «Intervenant1». Les vrais groupes estimés donnent Intervenant1/2/SPEAKER_00/01, pas identitésnominales. WarningAI final générique adapté par ROOT pour ne plus déclarer systématiquement la fonction indisponible.

## Tests ciblés

`python3 scripts/memora-test.py test/test_memora_auto_speakers.py test/test_memora_worker_resume.py test/test_memora_worker_diarization.py test/test_memora_domain.py -q` : **56PASS2,50s** ; Ruffworker/nouveautest conforme.

Fichier dédié `backend/test/test_memora_auto_speakers.py` : nouveauxsnapshots v1/v2 et audio/texte immuables ; ancienssnapshots/retranscribe exclus ; échecs nonpréparé/provider/mutation/malformed failsoft ; crashpendantlabels pasdoubleASR ; crashaprèslabels pasdoubleASR/labels ; warningpersistantaprèscrashrapport ; correctionconcurrente protégée. Fournisseursmockés uniquement pour ces contratsdurables, pas preuve de qualité acoustique.

Aucune nouvelle inférenceGPU ou donnée personnelle sur ce jalon. Les vraies preuves de diarisationCPU synthétiques sont dans handoffs/diarization-local-v1.md ; nouvelle recetteintégréeCPU/API et frontend par ROOT/api_tests reste distincte. Ne pas appeler testscontrats une validationréelle de la chaînecourante.

## Limites inchangées

Pas de diarisationlive (labels instables entrefenêtres), résultatfinal seulement. Pas séparationoverlap/identitéhumaine/calibrationconfiance. Resemblyzer peut fusionner/fragmenter les voix ; correctionmanuelle disponible. Aucun traitementautomatique d'une réunionexistante ne doit être initié pour migration ou démonstration. Les reprises concernent seulement un jobinitial déjà autorisé et son checkpointdurable.

## Revue finale et gel

Warning de panne automatique attaché à `automatic_diarization.source_version`, repris dans un rapport seulement pour la même versioncourante. Après correctionhumaine ou séparationmanuelle créant une nouvelleversion, l'ancienwarning n'est plus injecté dans le nouveau rapport ; métadonnéehistorique peut rester pour traçabilité. Test ajouté : échecautoASRv1 puis correctionv2/réanalyse, warningabsent, aucuneASR/voixrépétée.

Commande ciblée ci-dessus : **57PASS2,86s**, Ruff conforme. SHA finalworker **3db159a9e69eaa78d8d7a795b7c9d007e9b385298ddff6825f13328ff879e558**. Cette note remplace le précédent compteur56/2,50s pour le gel ; aucun changement ultérieur ni activationmain par ce sous-agent.
