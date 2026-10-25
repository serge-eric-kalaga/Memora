# Probe officiel fragment192 — terminé

Révision : `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`. Poids complets attendus : 1613977612 octets. Seul fragment écrit : `.memora/models/mlx-large-v3-turbo/.parts/00192`, plage globale débutant à 1610612736, **3364876 octets**. Publication atomique après réception complète ; aucune écriture d'un autre fragment ni de config, processus principal inchangé.

| Sousplage | Octets | Temps mural requête | Débit MiB/s |
|---|---:|---:|---:|
| offset 0 | 1048576 | 47.3497s | 0.0211 |
| offset 1048576 | 1048576 | 78.5367s | 0.0127 |
| offset 2097152 | 1048576 | 121.5052s | 0.0082 |
| offset 3145728 | 219148 | 14.2479s | 0.0147 |

Total requêtes : 261.6395s ; temps total avec métadonnées : 263.2505s. Débit agrégé requêtes : 0.0123MiB/s, soit 12.56KiB/s. Aucun échec réseau ni erreur de taille/range rencontré.

Chaque réponse206 et ContentRange exact vérifiés, taille cumulée finale vérifiée. SHA256 diagnostic de ce fragment : `21227ee6f76df17b6df9b52e3c4ec0c9ac7c2396d51560443f9515aef417152c` ; seule la vérification SHA256 officielle globale après assemblage établira l'intégrité complète du modèle.

Aucune URL signée, aucun header ni secret enregistré. Détails locaux : `agents/logs/mlx-tail-probe.json` et `.log`. Pas de comparaison contrôlée8MiB : trafic parallèle et variations réseau empêchent d'attribuer ces temps à la seule taille de plage. Aucun gain1MiB démontré ; décision intégrateur conservée8MiB/8flux. Octets désormais réutilisables par downloader principal qui ignore les fragments complets.

Probe terminé, aucun autre téléchargement ni inférence lancé.
