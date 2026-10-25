# Direction visuelle Memora

Inspiration demandée : Read.ai. Références publiques lues le 25 octobre 2026 :

- https://www.read.ai/meeting-reports
- https://support.read.ai/hc/en-us/articles/33462537362579-Using-Read-s-live-meeting-dashboard
- Capture officielle effectivement examinée : https://support.read.ai/hc/article_attachments/33723210637971

La capture publique présente des panneaux blancs bordés, des titres sur fond lilas, un flux de transcription horodaté et des commandes violettes. La page produit décrit un rapport structuré résumé/sujets/actions/transcription. Aucun compte Read connecté et aucun contenu privé de réunion utilisé. L’accès navigateur à une autre image du CDN officiel a été interdit ; cette seconde capture n’a pas été examinée.

Adaptation originale Memora : navigation latérale persistante sur ordinateur, bibliothèque de réunions en lignes à colonnes explicites, surface neutre claire avec variante sombre, accents indigo, rapport au centre, source audio et conversation IA dans un panneau latéral. Sur mobile : navigation compacte, lignes en cartes, chat ouvert par son onglet. Aucune métrique de sentiment, logo ou illustration Read réutilisé.

Modules : workspace-frame pour le cadre et les tokens visuels ; app.tsx conserve les parcours et permissions existants ; memora.module.css définit bibliothèque, rapports et panneaux. Les intitulés des actions existantes sont conservés. Modèles, API et dépendances n’ont pas été remplacés.

Validation de ce changement : TypeScript et lint seulement tant que l’instance utilisée sur le port 3000 reste active. Le build et la recette visuelle du nouveau rendu seront exécutés par l’agent principal après annonce du redémarrage. Les références ne constituent pas une preuve de vérification visuelle du rendu Memora modifié.

## Références fournies directement par l’utilisateur

Trois captures fournies ont ensuite été examinées visuellement. Seule leur structure a été utilisée : rail bleu nuit, navigation active violette, en-tête blanc avec titre/métadonnées/actions, onglets lilas soulignés, rapport ouvert avec sections séparées, panneau droit de lecture et repères. Aucun nom, email, texte de réunion, photo ou autre donnée privée de ces captures n’a été copié dans l’application ou dans les notes.

Cette référence remplace la première direction de rail clair. Les repères Memora proviennent uniquement des vrais sujets du rapport courant, associés aux segments autorisés ; aucune séquence ou métrique n’est fabriquée. Les fonctions commerciales, vidéo et coaching visibles dans la référence ne sont pas reproduites.

## Vérification obtenue après reconstruction

La recette navigateur synthétique complète a ensuite réussi sur le rendu reconstruit : import jusqu’au rapport, chat sourcé, correction et conservation des versions, partage invité mobile, révocation, archivage/restauration, capture Chromium à microphone synthétique, transcription live, pause, coupure réseau et reprise. Aucune exception JavaScript non gérée n’a été relevée. Les nouvelles captures desktop/mobile sous agents/logs ont été examinées visuellement. Cela valide le parcours du moteur actif lors de la recette, sans constituer une validation de la précision du futur moteur MLX ni du microphone physique/Safari/veille réelle.

Après cette recette, le champ de langue a été corrigé pour séparer son label et sa description d’aide (htmlFor/id/aria-describedby). TypeScript, lint et build production ont réussi sur cet ajustement ; aucun service n’a été redémarré par cet agent. Le script E2E conserve un sélecteur compatible avec les deux versions du label.
