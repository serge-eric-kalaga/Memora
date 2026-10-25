# Aperçu live après silence

Reproduction isolée : ASR simulé renvoyant[] après un aperçu synthétique déjà présent. Avant correction, worker.process effaçait live_segments (1FAIL/1PASS, premier aperçu vide déjà correct).

Correction worker.process limitée au chemin live : résultat vide retourne sans remplacer l’aperçu existant. Aucun changement pipeline final, version persistée, état recording/paused/interrupted ni marques provisoires. Premier aperçu vide demeure vide ; snapshot temporaire est toujours supprimé.

Validation : `python3 scripts/memora-test.py test/test_memora_worker_live.py test/test_memora_worker_maintenance.py -q` :5PASS en0.26s ; Ruff format/check PASS. Tests avec stockageSQLite jetable et ASR mock ; aucune inférence réelle ni données/services utilisateur.
