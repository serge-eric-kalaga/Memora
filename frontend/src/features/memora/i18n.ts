"use client";
import { useCallback } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
const english: Record<string, string> = {
  "Les étiquettes distinguent des groupes de voix, pas des identités. Les paroles simultanées ne sont pas séparées.": "Labels distinguish voice groups, not identities. Overlapping speech is not separated.",
  "Les voix proches, passages courts et bruits peuvent entraîner fusion ou fragmentation ; vérification humaine nécessaire.": "Similar voices, short passages and noise can merge or fragment groups; human review is required.",
  "Modifier les contenus autorisés": "Edit permitted content",
  "Terminez l’enregistrement ou interrompez le transfert avant de supprimer la réunion.":
    "Finish recording or pause the upload before deleting the meeting.",
  "Réunion supprimée sur le serveur. Le stockage local du navigateur n’a pas pu être nettoyé ; effacez les données locales de cette application.":
    "Meeting deleted on the server. Browser storage could not be cleared; remove this application’s local browser data.",
  "Interrompre le transfert": "Pause upload",
  "Transfert interrompu. Les fragments sauvegardés sont conservés. Sélectionnez le même fichier pour reprendre et terminer l’import.":
    "Upload interrupted. Saved chunks are preserved. Select the same file to resume and finish the import.",
  "Formats proposés : MP3, WAV, M4A, MP4, OGG, WebM, FLAC et AAC. Le contenu réel est vérifié avant traitement.":
    "Supported formats: MP3, WAV, M4A, MP4, OGG, WebM, FLAC and AAC. Actual content is validated before processing.",
  "Tous les liens configurés, y compris les liens expirés ou révoqués.":
    "All configured links, including expired or revoked links.",
  "Liens de partage :": "Share links:",
  français: "French",
  anglais: "English",
  "Langue non déterminée": "Language not determined",
  "Le moteur ne fournit pas de langue détectée ni de fiabilité chiffrée. Vérifiez les passages importants avec l’audio.":
    "The engine does not provide a detected language or quantified confidence. Check important passages against the audio.",
  "Langue de la portion audio :": "Audio portion language:",
  "Langue estimée pour cette portion de parole. Les changements sans pause peuvent ne pas être détectés ; fiabilité non chiffrée.":
    "Estimated language for this speech portion. Changes without a pause may not be detected; confidence is not quantified.",
  "Langue dominante :": "Dominant language:",
  "Langue choisie :": "Selected language:",
  "Langue détectée au début de l’audio ; elle peut varier dans ce passage.":
    "Language detected at the start of the audio; this passage may use another language.",
  "Langue sélectionnée pour la transcription, sans détection propre à ce passage.":
    "Language selected for transcription, without detection specific to this passage.",
  "Repères de la réunion": "Meeting chapters",
  "Choisissez Français ou English pour un audio monolingue, Automatique pour une alternance de langues.":
    "Choose French or English for single-language audio, Automatic for mixed languages.",
  "Navigation de l’espace": "Workspace navigation",
  "Mon espace": "My workspace",
  "Réunions & connaissance": "Meetings & knowledge",
  BIBLIOTHÈQUE: "LIBRARY",
  "Des échanges aux idées claires.": "From conversations to clarity.",
  "Vos rapports, vos décisions et leurs sources réunis dans un seul espace.":
    "Your reports, decisions and their sources together in one workspace.",
  "IA locale": "Local AI",
  "Votre mémoire vous appartient": "Your memory belongs to you",
  Réunion: "Meeting",
  "Date de création": "Creation date",
  Durée: "Duration",
  État: "Status",
  "réunions dans cette vue": "meetings in this view",
  "Retrouvez une décision, une action ou le passage qui vous manque.":
    "Find a decision, an action item or the passage you need.",
  "Quelles actions restent à faire ?": "Which action items remain?",
  "Langue de l’audio": "Audio language",
  "Automatique · français / anglais": "Automatic · French / English",
  "Retranscrire l’audio": "Transcribe audio again",
  "Choisissez la langue parlée et réécoutez les passages difficiles avant de relancer.":
    "Choose the spoken language and replay difficult passages before retrying.",
  "Retranscrire l’audio crée une nouvelle version de transcription et relance l’analyse. Les corrections courantes ne seront plus la version active ; elles resteront consultables dans l’historique, comme les anciens rapports. Continuer ?":
    "Transcribing again creates a new transcript version and restarts analysis. Current corrections will no longer be the active version; they remain available in history, along with previous reports. Continue?",
  "Fichier sélectionné": "Selected file",
  Mo: "MB",
  "Version de la transcription": "Transcript version",
  "Version historique en lecture seule. Les corrections s’effectuent uniquement sur la transcription courante.":
    "Read-only historical version. Corrections are only available for the current transcript.",
  "Chargement de la transcription historique…":
    "Loading historical transcript…",
  "Définir une expiration": "Set an expiration",
  "Ce lien restera actif jusqu’à sa révocation ou la suppression de la réunion.":
    "This link will remain active until it is revoked or the meeting is deleted.",
  "Rapport historique — source": "Historical report — source",
  "Transcription actuelle": "Current transcript",
  "Les repères audio sont conservés ; le texte affiché peut avoir été corrigé depuis cette analyse.":
    "Audio timestamps are preserved; displayed text may have been corrected since this analysis.",
  "Ancienne source": "Previous source",
  "Réponse conservée dans son contexte original ; citations désactivées après correction de la transcription.":
    "Answer preserved in its original context; citations disabled after transcript correction.",
  Résumé: "Summary",
  "Audio importé": "Imported audio",
  "Enregistrement direct": "Live recording",
  "Réunion du": "Meeting date",
  "Date de réunion non renseignée": "Meeting date not specified",
  "Importé le": "Imported on",
  "Créée le": "Created on",
  "Enregistrer le titre": "Save title",
  "Modifier le titre": "Edit title",
  "Cette réunion est archivée. Ses liens de partage restent actifs jusqu’à leur expiration ou révocation.":
    "This meeting is archived. Its share links remain active until expiration or revocation.",
  "Vérifiez le compte rendu et les passages sources : la transcription automatique peut contenir des erreurs, même sans signal d’incertitude.":
    "Verify the report and source passages: automatic transcription may contain errors even without an uncertainty flag.",
  "La limite de durée approche : moins d’une minute restante.":
    "The duration limit is approaching: less than one minute remaining.",
  "Le microphone a été déconnecté ou son autorisation retirée. Finalisez les fragments sauvegardés ; créez ensuite une autre réunion pour enregistrer à nouveau.":
    "The microphone was disconnected or its permission revoked. Finalize saved chunks, then create another meeting to record again.",
  "L’application est en arrière-plan. La veille, le verrouillage ou le navigateur peuvent interrompre le microphone ; vérifiez l’enregistrement au retour.":
    "The app is in the background. Sleep, screen locking or the browser may interrupt the microphone; check the recording when you return.",
  "La veille, le verrouillage ou le changement d’onglet peuvent suspendre l’enregistrement selon le navigateur. Gardez cette page active et vérifiez les fragments sauvegardés.":
    "Sleep, screen locking or switching tabs may suspend recording depending on your browser. Keep this page active and check saved chunks.",
  Provisoire: "Provisional",
  "Ces passages provisoires seront remplacés par la transcription finale après l’arrêt.":
    "These provisional passages will be replaced by the final transcript after recording stops.",
  "Ces paramètres s’appliquent aux nouvelles réunions. Les réunions existantes conservent leurs limites et échéances de rétention initiales ; aucune purge rétroactive n’est lancée ici.":
    "These settings apply to new meetings. Existing meetings retain their original limits and retention deadlines; this does not trigger a retroactive purge.",
  "Retrouvez vos réunions et leur mémoire en vous connectant.":
    "Sign in to access your meetings and their shared memory.",
  "Chargement de votre espace…": "Loading your workspace…",
  "Le service de connexion est indisponible.":
    "The sign-in service is unavailable.",
  "Réessayer la connexion": "Retry connection",
  "Vos réunions, en clair.": "Your meetings, made clear.",
  "Enregistrez, transcrivez et retrouvez chaque décision grâce à une IA locale.":
    "Record, transcribe and find every decision with local AI.",
  "Se connecter": "Sign in",
  "Créer un compte": "Create an account",
  "Espace réunions": "Meeting workspace",
  Réunions: "Meetings",
  Paramètres: "Settings",
  Fermer: "Close",
  "Nouvelle réunion": "New meeting",
  "VOTRE MÉMOIRE COLLECTIVE": "YOUR SHARED MEMORY",
  "Mes réunions": "My meetings",
  "Moins de notes. Plus de présence. Aucune décision oubliée.":
    "Fewer notes. More presence. Every decision remembered.",
  "Suivi des emails": "Email status",
  Notifications: "Notifications",
  "Aucune notification pour le moment.": "No notifications yet.",
  "Votre rapport est disponible": "Your report is ready",
  "Rapports disponibles": "Reports ready",
  "En préparation": "Processing",
  Terminées: "Completed",
  Toutes: "All",
  Archives: "Archived",
  "Rechercher une réunion": "Search meetings",
  "Rechercher une réunion…": "Search meetings…",
  "Chargement des réunions…": "Loading meetings…",
  "Aucune réunion trouvée": "No meetings found",
  "Vos archives sont vides": "Your archive is empty",
  "Une réunion à retenir ?": "A meeting worth remembering?",
  "Enregistrez une conversation ou importez un fichier audio pour commencer.":
    "Record a conversation or import an audio file to get started.",
  "Titre de la réunion": "Meeting title",
  "Ex. Point équipe du lundi": "E.g. Monday team meeting",
  "L’enregistrement ne commence qu’après votre action explicite. Informez les participants avant de commencer.":
    "Recording starts only after your explicit action. Inform participants before you begin.",
  Enregistrer: "Record",
  "Importer un audio": "Import audio",
  "Audio indisponible": "Audio unavailable",
  "Ouverture de la réunion…": "Opening meeting…",
  "← Toutes les réunions": "← All meetings",
  "ESPACE RÉUNION": "MEETING WORKSPACE",
  Partager: "Share",
  Archiver: "Archive",
  Restaurer: "Restore",
  "… Vous pouvez quitter cette page. Une notification vous avertira à la fin.":
    "… You can leave this page. We will notify you when it is ready.",
  "Régénérer le rapport": "Regenerate report",
  "Lancer / reprendre l’analyse": "Start / retry analysis",
  "La transcription a été corrigée. Le rapport est à actualiser ; le chat utilise la transcription courante.":
    "The transcript has changed. The report needs updating; chat uses the current transcript.",
  Rapport: "Report",
  "Chat IA": "AI chat",
  "Compte rendu": "Meeting report",
  "Version du rapport": "Report version",
  Version: "Version",
  "Votre compte rendu se prépare ici": "Your report will appear here",
  "Ajoutez un audio puis lancez l’analyse. Aucun résultat n’est inventé en attendant.":
    "Add audio and start analysis. No results are fabricated while you wait.",
  Corriger: "Edit",
  "Votre nom (éditeur invité)": "Your name (guest editor)",
  "Les corrections créent une nouvelle version. Les anciennes analyses sont conservées.":
    "Corrections create a new version. Previous analyses are preserved.",
  "Intervenant ·": "Speaker ·",
  "Enregistrer les corrections": "Save corrections",
  Annuler: "Cancel",
  "Intervenant non identifié": "Unidentified speaker",
  "Passage incertain": "Uncertain passage",
  "Les passages apparaîtront après transcription.":
    "Passages will appear after transcription.",
  "SOURCE ORIGINALE": "ORIGINAL SOURCE",
  "Audio de la réunion": "Meeting audio",
  Télécharger: "Download",
  "L’audio sera disponible après sauvegarde.":
    "Audio will be available after saving.",
  "L’audio n’est pas inclus dans ce partage.":
    "Audio is not included in this share.",
  "Traitement IA local. Vérifiez les passages incertains et les décisions importantes.":
    "Local AI processing. Verify uncertain passages and important decisions.",
  "Supprimer définitivement cette réunion et ses fichiers ?":
    "Permanently delete this meeting and its files?",
  "Supprimer définitivement": "Delete permanently",
  "Sujets abordés": "Topics discussed",
  Décisions: "Decisions",
  "Actions à suivre": "Action items",
  "Questions ouvertes": "Open questions",
  "Responsable :": "Owner:",
  "Échéance :": "Due date:",
  "Aucun élément établi dans la transcription.":
    "No item established in the transcript.",
  "Interrogez votre réunion": "Ask your meeting",
  "Des réponses fondées sur la transcription, avec accès aux passages sources.":
    "Answers grounded in the transcript, with access to source passages.",
  "Votre question": "Your question",
  "Quelles décisions avons-nous prises ?": "What decisions did we make?",
  "Recherche dans la réunion…": "Searching the meeting…",
  "Poser la question": "Ask question",
  "Durée maximale atteinte. Finalisez l’audio sauvegardé pour lancer l’analyse.":
    "Maximum duration reached. Finalize the saved audio to start analysis.",
  "Microphone indisponible. Utilisez HTTPS ou localhost, ou importez un fichier audio.":
    "Microphone unavailable. Use HTTPS or localhost, or import an audio file.",
  "Un enregistrement existe déjà. Finalisez-le avant de créer une nouvelle réunion pour enregistrer à nouveau.":
    "A recording already exists. Finalize it, then create a new meeting to record again.",
  "L’enregistrement a été interrompu. Les fragments sauvegardés peuvent être repris.":
    "Recording was interrupted. Saved chunks can be recovered.",
  "Format non pris en charge : MP3, WAV, M4A, MP4, OGG, WebM, FLAC ou AAC attendu.":
    "Unsupported format: expected MP3, WAV, M4A, MP4, OGG, WebM, FLAC or AAC.",
  "Ce fichier dépasse la limite d’import configurée.":
    "This file exceeds the configured upload limit.",
  "IMPORT AUDIO": "AUDIO IMPORT",
  "ENREGISTREMENT AUDIO": "AUDIO RECORDING",
  "Vous êtes à l’écoute.": "You are listening.",
  "Prenez votre temps.": "Take your time.",
  "Chaque échange compte.": "Every conversation matters.",
  "Informez les participants. Le microphone est activé uniquement lorsque vous cliquez sur Enregistrer. Durée maximale :":
    "Inform participants. The microphone activates only when you click Record. Maximum duration:",
  "min ; import :": "min; upload:",
  "Mo.": "MB.",
  "% importés": "% uploaded",
  Reprendre: "Resume",
  "Terminer et analyser": "Finish and analyze",
  "Reprendre avec le même fichier": "Resume with the same file",
  "Choisir un fichier audio": "Choose audio file",
  "Reprendre la sauvegarde": "Retry saving",
  "Finaliser l’audio sauvegardé": "Finalize saved audio",
  "Sauvegarde et préparation de l’analyse…": "Saving and preparing analysis…",
  "Transcription en direct": "Live transcription",
  "La transcription apparaîtra progressivement après traitement des fragments.":
    "Transcription will appear progressively as chunks are processed.",
  "Partager cette réunion": "Share this meeting",
  "Toute personne disposant du lien et, s’il est défini, du mot de passe peut accéder aux contenus autorisés. Les adresses email ne constituent pas une liste de contrôle d’accès.":
    "Anyone with the link and password, if set, can access the permitted content. Email recipients are not an access control list.",
  "Mot de passe (facultatif)": "Password (optional)",
  "Au moins 8 caractères": "At least 8 characters",
  "Expiration dans (jours)": "Expires in (days)",
  "Contenus et droits invités": "Guest content and permissions",
  "Consulter le rapport": "View report",
  "Consulter la transcription": "View transcript",
  "Écouter / télécharger l’audio": "Play / download audio",
  "Interroger le chat IA": "Ask AI chat",
  "Corriger la transcription": "Edit transcript",
  "Créer le lien": "Create link",
  "Lien de partage": "Share link",
  "Lien copié. Transmettez le mot de passe séparément.":
    "Link copied. Send the password separately.",
  "Copie impossible. Sélectionnez et copiez le lien manuellement.":
    "Copy failed. Select and copy the link manually.",
  "Copier le lien": "Copy link",
  "Destinataires email (séparés par virgules)":
    "Email recipients (comma separated)",
  "Résumé inclus dans l’email (aperçu modifiable)":
    "Email summary (editable preview)",
  "Inclure le mot de passe dans le même email":
    "Include the password in the same email",
  "Le destinataire pourra retransmettre le lien et le mot de passe. Vous pouvez aussi transmettre le mot de passe séparément.":
    "Recipients can forward the link and password. You can also send the password separately.",
  "Mot de passe du lien sélectionné": "Selected link password",
  "Invitation mise en file. Consultez le suivi des emails pour confirmer la remise au serveur local de capture.":
    "Invitation queued. Check email status to confirm delivery to the local capture server.",
  "Envoyer le résumé et le lien": "Send summary and link",
  "Liens existants": "Existing links",
  Protégé: "Protected",
  Ouvert: "Open",
  Révoqué: "Revoked",
  "Sans expiration": "No expiration",
  Sélectionner: "Select",
  Révoquer: "Revoke",
  "Réunion partagée": "Shared meeting",
  "Vérification du lien…": "Checking link…",
  "Si ce lien est protégé, saisissez le mot de passe transmis par l’organisateur. Un lien expiré ou révoqué ne permet plus l’accès.":
    "If protected, enter the password provided by the organizer. Expired or revoked links no longer grant access.",
  "Mot de passe du partage": "Share password",
  "Accéder à la réunion": "Open meeting",
  "Durée maximale d’une réunion (minutes)":
    "Maximum meeting duration (minutes)",
  "Taille maximale d’import (Mo)": "Maximum upload size (MB)",
  "Conservation des fichiers audio (jours)": "Audio retention (days)",
  "VOTRE ESPACE": "YOUR WORKSPACE",
  "Paramètres de l’application": "Application settings",
  "Des limites explicites, adaptées aux ressources disponibles.":
    "Explicit limits, adapted to available resources.",
  "Paramètres sauvegardés.": "Settings saved.",
  "Enregistrement et conservation": "Recording and retention",
  "La modification est soumise aux droits administratifs contrôlés par le serveur.":
    "Changes require administrator permissions checked by the server.",
  "Autoriser l’organisateur à accorder la correction aux invités":
    "Allow organizers to grant transcript editing to guests",
  "Les droits de chaque lien restent configurables lors du partage. L’archivage conserve la réunion ; la suppression retire ses données et révoque ses accès.":
    "Each share link has configurable permissions. Archiving preserves the meeting; deletion removes its data and revokes access.",
  "Langue des rapports": "Report language",
  Français: "French",
  "Notification email à la disponibilité du rapport":
    "Email notification when the report is ready",
  "Sauvegarde…": "Saving…",
  "Enregistrer les paramètres": "Save settings",
  "En environnement local, les messages sont capturés sans envoi externe. « Remis » confirme la réception SMTP de capture, sans preuve de délivrabilité en production.":
    "In the local environment, messages are captured without external delivery. Delivered confirms receipt by the SMTP capture server, not production deliverability.",
  "Ouvrir la boîte de capture locale ↗": "Open local email inbox ↗",
  "Aucun email demandé.": "No email requested.",
  "Remis au serveur": "Delivered to server",
  "En attente": "Queued",
  "En cours": "In progress",
  Échec: "Failed",
  Réessayer: "Retry",
  Brouillon: "Draft",
  Enregistrement: "Recording",
  "En pause": "Paused",
  Interrompue: "Interrupted",
  "Analyse en cours": "Analyzing",
  Terminée: "Completed",
  "À reprendre": "Retry needed",
  Courante: "Current",
  Historique: "History",
  " · Courante": " · Current",
  " · Historique": " · History",
};
export function useMemoraText() {
  const { language } = useI18n();
  return useCallback(
    (text: string) => (language === "en" ? english[text] || text : text),
    [language],
  );
}
export const translatedTexts = english;
