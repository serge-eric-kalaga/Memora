# Capture persistante — harness navigateur isolé

Nouveau `frontend/tests/memora-persistent-capture-browser.mjs`, aucun codeproduit modifié. Compile et monte vrais CaptureProvider/CaptureSlot/CaptureRuntime/MicrophoneCheck/RecordingSignal/useRecordingContinuity/storage IndexedDB en Chromium1248. Remplace uniquement useSession/useI18n/NextLink/API pour tests bornés ; navigation signifie démontage/remontage des vues React via route locale, PAS vraie navigationNext. Contrat API stub enregistre taillesblobs/requêtes ; vraiMediaRecorder/vraisfragmentsOPUS/WebM et vraiIndexedDB. Autorisation Chromium microphonevirtuel `--use-fake-device-for-media-stream` ; aucun microphone physique/audio privé. Origine memora.test interceptée en mémoire, aucun serveur principal.

Huit contrôles PASS log `agents/logs/persistent-capture-browser.log` :

- dashboard/profil/paramètres/autreréunion pendantcapture : un seul getUserMedia, zérostop, tracklive.
- barre pause/reprise/retour : aucune réacquisition.
- vrai fragmentcodec nonvide après timeslice10s : IndexedDB→stubtransportconfirmé.
- finalisation barre : flushfragments et pistesstoppées ; APIanalyse stub, paspreuve rapportIA.
- logout arrête captureactive.
- navigation pendantprétestmicro arrête sespistes et retour ne bloque pas boutonEnregistrer.
- getUserMedia résoluaprèslogout : toutespistesstoppées, aucun recorder.start supplémentaire.
- zéro exceptionJavaScript.

Touscontextes Chromium fermés et répertoirebundletemporaire supprimé finally ; aucune base/stockageappprincipal/service/GPU utilisé. Agentfrontend ajoute séparément vraie navigationNext et upload/rapport dans recetteisolée avec backendmodèles réels aprèsbuildROOT ; ne pas confondre ces deux niveaux de preuve.

## Renforcement événements de session

Après correctifsROOT provider : stubauth exporte sessionChannel/sessionSource canoniques. Harness relancé10contrôles PASS, incluant nouvel événementwindow session-expired et BroadcastChannel login provenant autreonglet alors que usernamecache reste identique : toutespistesended dans lesdeuxcas. Fluxnormal,logout etraceacquisitiontardive restentverts. NouveauwrapperthèmeWorkspaceFrame compilé sans modificationproduit. Même logpersistent-capture-browser.log désormais10PASS, exit0, zéroexceptionJS ; preuveAPI/Next reste séparée.
