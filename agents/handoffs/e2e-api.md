# Recette API réelle synthétique

Réunion synthétique conservée pour démonstration : `2b96a7fd23ea495f9c36843ccbeeb4ce`. Durée totale : 49.79s.

Exécution : `backend/.venv/bin/python scripts/memora-e2e-api.py` sur 127.0.0.1:8080 avec compte local `.memora/demo.json` (aucun secret affiché).

- VALIDÉ : Compte synthétique connecté
- VALIDÉ : Création réunion persistée
- VALIDÉ : Fragment idempotent sans duplication
- VALIDÉ : Import fragmenté et reprise persistés
- VALIDÉ : Finalisation idempotente
- VALIDÉ : Transcription et rapport réels prêts
- VALIDÉ : Toutes références rapport appartiennent à réunion
- VALIDÉ : Chat réel Alice et sources vérifiables
- VALIDÉ : Information absente sans fausse citation
- VALIDÉ : Audio téléchargé identique à upload
- VALIDÉ : Correction version 2 et résultat périmé signalé
- VALIDÉ : Ancien rapport conservé avant régénération
- VALIDÉ : Régénération réelle historique deux rapports
- VALIDÉ : Accès invité ouvert sans compte
- VALIDÉ : Modification invitée interdite côté backend
- VALIDÉ : Partage limité masque transcription et audio
- VALIDÉ : Partage protégé refuse faux mot de passe et accepte correct
- VALIDÉ : Expiration réellement appliquée
- VALIDÉ : Invitation deux destinataires mise en file capture locale
- VALIDÉ : Deux emails reçus localement avec résumé et bouton accès
- VALIDÉ : Notification disponibilité dans application
- VALIDÉ : Révocation retire accès réunion et fichier audio
- VALIDÉ : Archivage distinct suppression
- VALIDÉ : Restauration archive conserve réunion

Portée : API + persistance + Whisper/Ollama réels + capture SMTP locale. Aucun test microphone physique ni délivrabilité email externe. Navigateur géré par intégrateur.
