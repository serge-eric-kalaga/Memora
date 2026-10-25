# Groupes vocaux automatiques — preuve réelle isolée

Réserve synthétique existante `.memora/qa/diarization-reserve/references.json`, cas reserve-two-return40,1665s, six prises Daniel/Karen avec retours nonalternés. Aucun audio personnel, modèle nouveau ou téléchargement.

Module Resemblyzer/Silero réel CPU :2groupes, sixsegments étiquetés1/2/2/1/1/2 ; id/text/start/end identiques aux références. Coût2,021s. Preuves `agents/logs/auto-speakers-cpu.json` et `.log` (avertissement pkg_resources existant et télémétrieORT nonpersistée). Script reproductible `backend/.venv/bin/python scripts/memora-qa-auto-speakers.py --cpu-only`. Base/stockage TemporaryDirectory supprimés automatiquement, aucune API/service principal.

Pipeline réel ASR→labels→rapport préparé dans même script sans --cpu-only ; attend créneau GPU exclusif frontend/root. Pas encore exécuté à cette étape. Résultat CPU seul ne prouve pas attribution des segments ASR réels ni rapport final.

## Pipeline réel terminé

Après autorisation GPU exclusive ROOT : `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 backend/.venv/bin/python scripts/memora-qa-auto-speakers.py` hors sandbox pour MLX/loopbackOllama. Sortie0 ; durée18,036s pour pipeline. Audio40,1665s de la même réserve, langueEN explicite, Whisperlarge-v3-turbo local et Gemma4:e4b existants ; aucun mock des trois traitements. Worker réel a créé ASRv1 sixsegments tous « Intervenant non identifié », puis labelsautomatiquesv2 sixsegments1/2/2/1/1/2,2groupes, rapportuniquev2 et étatready. Comparaison id/text/start/end strictement égale v1/v2. AppelCPU direct préalable1,624s confirmait les mêmes six labels sur segments référence.

Résultats `agents/logs/auto-speakers-pipeline.json/.log`. Aucun email (settings false), serveur lancé, donnée principale ou envmain lu. Domaine/base/audio copiés uniquement TemporaryDirectory, supprimé à sortie normale du bloc. GPU libéré et ROOT/frontend informés immédiatement. Preuve fonctionnelle sur ce petit exempleTTS connu, pas garantie nombrelocuteurs/conversationnaturelle ni évaluation sémantique du rapport.
