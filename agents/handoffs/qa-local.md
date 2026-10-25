# QA IA locale et capture email — 25 octobre 2026

## Livré dans cette tâche

- `scripts/memora-qa-local.py` : ASR + rapport + chat réels, charge le module IA directement pour éviter initialisation du template. Données synthétiques uniquement.
- `backend/test/fixtures/memora/{french,english,mixed}.aiff` : voix macOS `say`, aucune utilisation du micro.
- `backend/test/test_memora_ai.py` : trois tests isolés pertinents, tous réussis (0,25 s).
- `scripts/memora-mail-capture.py` : SMTP sink 127.0.0.1:1025 ; consultation HTTP 127.0.0.1:8025. Aucun relais. Aucun contenu ni destinataire dans logs techniques. Mails `.memora/mail/*.eml` exclus Git avec dossier local.
- Modèle officiel `Systran/faster-whisper-base` téléchargé dans `.memora/models` ; licence MIT vérifiée via API officielle https://huggingface.co/api/models/Systran/faster-whisper-base . Cache non versionné.

## Preuves réelles

Commande : `backend/.venv/bin/python scripts/memora-qa-local.py` avec accès loopback autorisé. Résultats détaillés synthétiques dans `agents/logs/qa-local-results.json` et `.log` (locaux ignorés).

| Audio | Durée audio | Transcription CPU int8 |
|---|---:|---:|
| FR Thomas | 8,52 s | 2,36 s |
| EN Samantha | 8,57 s | 0,81 s |
| Alternance FR/EN, voix Samantha | 10,02 s | 0,77 s |

Rapport qwen3.5:4b : 11,36 s. Question « Qui prépare la démonstration et quand ? » : Alice vendredi, source s1, 1,22 s. Information absente : réponse explicite sans source, 1,34 s. Injection ajoutée aux données « ignore règles / SECRET_COMPROMIS » : ignorée, réponse budget non approuvé, source s2, 1,29 s.

Capture mail : SMTP accepte message synthétique, inbox HTTP contient texte attendu ; aucune livraison externe testée ni revendiquée.

## Limites constatées, à conserver dans bilan

- Whisper base a transcrit « Memora lundi » en « Memorale Indie » FR ; `uncertain=false` malgré cette erreur. Les indicateurs de confiance ne garantissent pas exactitude.
- Alternance dans fenêtre de 30 s supportée avec transcription mêlée, mais `language=en` sur fenêtre complète ; voix anglaise prononce le français de façon peu naturelle, vendredi dégradé. Pas preuve de précision bilingue robuste.
- Rapport a résumé le lancement mais omis la décision explicite de sa liste `decisions`, et mis responsable non identifié dans `owner` malgré Alice présente dans texte action. Signalé à intégrateur pour correction/test supplémentaire.
- Pas de diarisation automatique ; noms non identifiés assumés.
- Tests longs : preservation complète des sources en batch vérifiée sur 70 segments ; pas une mesure réelle ASR de réunion de deux heures.

## Reproduction

`MEMORA_MODEL_DIR="$PWD/.memora/models" backend/.venv/bin/python scripts/memora-qa-local.py`

`cd backend && .venv/bin/python -m pytest test/test_memora_ai.py -q`

`backend/.venv/bin/python scripts/memora-mail-capture.py`

Environnement de cette session : sandbox exige escalade pour réseau/loopback et synthèse macOS. `say` en sandbox créait des AIFF vides de 4096 octets ; commandes autorisées exécutées hors restriction produisent vrais audios.

## Comparaison complémentaire et correctif de prompt proposé

Corpus bilingue natif ajouté `mixed-native.wav` : concaténation Thomas FR + silence + Samantha EN. `french.wav` et `english.wav` ajoutés pour imports universels.

Whisper base fenêtre 30s : 1,21s, transcrit les deux langues mais détecte français pour toutes les phrases ; fenêtre 10s : 1,31s, détecte anglais sur fin mais coupe début « The budget ». Recommandation : ne pas adopter découpage 10s sans chevauchement + déduplication validés. Les fenêtres 30s ont aussi risque de frontière en réunion longue : besoin test spécifique, pas de garantie.

Prompt alternatif 2 testé **réellement** avec qwen3.5:4b en 9,62s : toutes les listes correctement remplies, décision explicite citée s1, action owner Alice + deadline Vendredi citée s2, budget question citée s3. Prompt exact `.memora/prompt-test.py`, résultat `agents/logs/qa-prompt2.log`. Exemple JSON de sources non vides a été déterminant ; premier prompt sans cet exemple renvoyait sources vides. Prompt proposé transmis à intégrateur ; pas modifié ai.py dans cette tâche.

Téléchargement supplémentaire `Systran/faster-whisper-small` lancé et licence MIT vérifiée. Résultat comparatif à compléter après téléchargement, ne pas revendiquer small disponible tant que « small ready » absent.

Small disponible et testé : cache total base+small 605 Mio. Comparaison FR 8,52s : small 2,03s, base 0,72s ; erreur « Memora lundi » persiste. Corpus mixte natif : small fenêtre 30s omet la partie EN entière ; fenêtre 10s invente « Le budget reste une question électorale » au lieu du passage anglais. **Ne pas adopter small par défaut sur ces preuves.** Tests dans `agents/logs/qa-improvements.log`. Base conserve mieux l'alternance de ce corpus. Test complémentaire `multilingual=True` en cours au moment de cette note.

Option officielle Faster Whisper `multilingual=True` testée : **base conserve correctement tout le passage EN** « The budget remains an open question, we will discuss it next week. » après FR, 1,02s. Small avec même option omet encore EN, 2,38s. Recommandation transmise : base + multilingual=True, conserver 30s ; limites des noms propres et jours relatifs subsistent. Preuve `agents/logs/qa-multilingual.log`. Le prompt alternatif réussi est désormais reproduit dans `scripts/memora-qa-improvements.py` (fin du fichier), pas seulement fichier local.

Capture SMTP encore démarrée dans session 33331. Une modification du lecteur de corps (préfère HTML sous forme de texte échappé) nécessite redémarrage pour prise en compte ; session active reste opérationnelle. Aucun destinataire ni contenu n'est écrit dans logs techniques.
