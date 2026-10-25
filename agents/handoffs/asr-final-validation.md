# Validation ASR locale — 25 octobre 2026

Poids `mlx-community/whisper-large-v3-turbo`, révision a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb,1 613 977 612octets. SHA256 officiel intégral vérifié ; mode offline `memora-download-mlx.py --check-only` réussit. Aucun audio utilisateur utilisé. Conversion et modèle original MIT ; VAD Silero MIT via les assets ONNX déjà inclus dans Faster Whisper, pas de téléchargement supplémentaire.

## Choix fondé sur les essais

Le premier essai MLX brut a révélé deux défauts : traduction indue du morceau anglais et « Thank you » inventé sur bruit blanc. Il n’a pas été activé. Adaptateur corrigé : détection de parole Silero (pause300ms, marge200ms), inférence indépendante de chaque portion, coordonnées audio originales conservées. Modèle gardé pendant les portions d’un appel, puis libéré ; garde commune aux inférences applicatives évite cumul MLX/Ollama. Auto = langue dominante de chaque portion, confiance non chiffrée, pas attribution par mot garantie.

## Sept cas vérifiés ensemble

Commande : `/usr/bin/time -l backend/.venv/bin/python scripts/memora-benchmark-mlx.py`.
Preuves : `agents/logs/benchmark-mlx-final.log`, `benchmark-mlx-final-auto.json` (copie préservée avant choix forcé FR). Les segments portent bien `speech_region_detection` ; le commentaire générique language_limit de cette exécution était encore ancien, corrigé depuis dans le script. Les mesures et segments restent ceux du fichier brut, sans modification.

| Cas synthétique | Base WER normalisé | MLX VAD WER normalisé | Temps MLX observé |
|---|---:|---:|---:|
| Phrase Python |0%|0%|1,9089s|
| Même phrase +10s silence |0%|0%|0,7906s|
| Français chiffres/négations/noms |17,5%|2,5%|0,9914s|
| Français puis anglais |7,69%|3,85%|1,4635s|
| Anglais |0%|0%|0,8289s|
| Silence |aucun texte|aucun texte|0,018s|
| Bruit blanc faible |aucun texte|aucun texte|0,0332s|

Normalisation numérique explicitement limitée dans le script ; accents conservés. Le2,5% français restant correspond à « M. » plutôt que « Monsieur », et le3,85% mixte à « Mémora » au lieu de « Memora ». Les nombres2400/24000, négations, Ouagadougou, Aïcha et Traoré sont conservés dans cet exemple. Ne pas transformer ces chiffres en garantie sur la voix d’un utilisateur ou un corpus naturel général.

Critères techniques examinés : Python/anglais exacts, aucun ajout dans silence/bruit/queue silencieuse, deux langues conservées sans traduction, WER français normalisé inférieur5%. Ce sont des critères de cette évaluation technique, pas des exigences chiffrées imposées par l’utilisateur. La seule commande réussie n’a pas suffi : les textes et assertions ont été inspectés.

Choix explicite Français : `--engine mlx --language fr --cases python french-realistic`, Python0%, français2,5%, temps1,2785s et0,7049s, `benchmark-mlx-final-forced-fr.json` et log associé. La différence de chiffres écrits en lettres/chiffres n’est pas confondue avec une erreur sémantique.

Pic mémoire processus du benchmark court :2 927 282 816octets (environ2,73GiB), relevé `/usr/bin/time -l`. Timing inclut décodage, VAD, chargement et libération ; premier appel plus froid, pas comparaison de kernels purs. Les performances peuvent changer avec l’activité de la machine.

## Long audio et activation

**PASS réel** :900secondes synthétiques,50cycles FR/EN,105segments. Temps54,2905s (RTF0,0603), début retrouvé, phrase finale retrouvée près de la fin et dernier horodatage899,84s. Deux langues conservées,1segment signalé incertain. Pic mémoire processus3 041 790 688octets (~2,83GiB). `agents/logs/benchmark-long.json` et `benchmark-long.log`. Les marqueurs ne prouvent pas chaque mot de chaque cycle ; il ne s’agit pas d’une réunion naturelle de deux heures.

Décision après inspection des textes/acceptations et couverture longue : MLX pour final et direct sur cette machine. Configuration privée mise à jour sans remplacer les autres variables ; services redémarrés après vérification0jobsactifs. Aucun contenu utilisateur retranscrit automatiquement. Recette complète isolée sur ce moteur ensuite en cours au moment de cette note.

Limites : segments vocaux très courts et alternance sans pause restent difficiles ; VAD peut manquer de la voix faible. Aucun test naturel2h, microphone physique, Safari/iOS ou diarisation automatique. L’audio de l’utilisateur ne sera pas remplacé automatiquement ; la retranscription volontaire conserve ses anciennes versions.
