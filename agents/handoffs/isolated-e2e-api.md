# Recette API réelle synthétique

Réunion synthétique temporaire et supprimée après recette : `9d844cdb81f54563a3640354759a8472`. Durée totale : 70.36s.

Exécution : `backend/.venv/bin/python scripts/memora-e2e-api.py` sur http://127.0.0.1:18080 ; compte jetable isolé (aucun secret affiché).

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
- VALIDÉ : Compte jetable autorisé à administrer la recette isolée
- VALIDÉ : Configuration administrative valide réellement sauvegardée
- VALIDÉ : Nouveaux paramètres appliqués aux réunions futures sans rétroactivité
- VALIDÉ : Invité explicitement autorisé corrige réellement une transcription
- VALIDÉ : Désactivation administrative retire les droits d’un ancien lien invité
- VALIDÉ : Retranscription réelle dédupliquée par identifiant de requête
- VALIDÉ : Nouvelle ASR et nouveau rapport prêts avec toutes les versions antérieures conservées
- VALIDÉ : Rejeu après retranscription terminée ne crée aucune nouvelle version
- VALIDÉ : Configuration administrative initiale restaurée après recette
- VALIDÉ : Route française réelle : transcription et rapport prêts sans langue détectée inventée
- VALIDÉ : Correction de la nouvelle ASR persistée sans422, ancien rapport conservé et périmé

Portée : API + persistance + Whisper/Ollama réels + capture SMTP locale. Aucun test microphone physique ni délivrabilité email externe. Navigateur géré par intégrateur.
