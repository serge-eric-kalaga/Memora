# Analyse : permission de reprise ASR

Contournement confirmé sur base et stockage jetables synthétiques : réunion en échec, version0, durée1s, invité edit+transcript mais audio=false, option admin allow_guest_edit=true. Avant correction POST analyze renvoyait200 et créait un pipeline qui aurait lu l’audio. Audio expiré ou absent sans segments renvoyait également200.

Correction bornée routes.analyze : après les retours idempotents existants, vérifier la transcription de la version courante. Si vide, le pipeline doit refaire ASR : droit audio requis403, rétention dépassée410, fichier absent404. Avec segments, régénération autorisée même sans droit audio et après expiration/suppression du fichier. Aucun changement worker ni données/services principaux.

Tests : reproduction rouge effective des trois scénarios avant correctif (200 au lieu403/410/404). Après correctif `python3 scripts/memora-test.py test/test_memora_domain.py -q` :32PASS en2.16s. Inclut absence de job après refus, régénération invitée sans audio avec segments/audio expiré et supprimé, même job retourné sur répétition, demandes déjà connues retournées sans nouveau besoin de fichier. Ruff format/check PASS. Les bases/comptes/services réels n’ont pas été utilisés.
