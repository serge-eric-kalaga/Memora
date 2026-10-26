# Séparation des intervenants — recherche du 26 octobre 2026

Statut : audit et recherche effectués ; aucun nouveau moteur activé. Les résultats
publiés par un fournisseur ne sont pas des résultats mesurés dans Memora.

## Diagnostic vérifié dans le code

`backend/api/memora/diarization.py` utilise actuellement ECAPA-TDNN pour extraire
des empreintes sur des fenêtres de 3,2 secondes, Silero pour détecter la parole et
un regroupement agglomératif au seuil de distance 0,55. Une seconde estimation sur
1,6 seconde peut refuser un comptage contradictoire. Cette chaîne ne détecte pas
les paroles simultanées. Une fenêtre peut contenir deux personnes et une même
personne peut changer de timbre ou de canal : ce sont des causes possibles de
fusion et de fragmentation, pas un diagnostic établi sur un nouvel audio privé.

`frontend/src/features/memora/speaker-label.ts` affiche « Intervenant » quand
l'attribution manque. Ce libellé ne signifie pas « un seul intervenant détecté ».
Une capture de transcription v0 ne suffit pas à établir si la séparation finale
a été exécutée. Le worker conserve les résultats et états d'échec séparément.

## Options examinées à partir des sources primaires

| Option | Apport | Conditions / limites | Décision |
| --- | --- | --- | --- |
| [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) | Segmentation apprise, empreintes, regroupement VBx/PLDA ; sortie exclusive utile pour raccorder les mots aux voix | CPU par défaut, traitement hors ligne après téléchargement ; poids CC-BY-4.0 ; accès soumis à acceptation des conditions Hugging Face | Candidat de référence pour une évaluation locale ; accès non préparé |
| [NVIDIA Nemotron-3-Diarization](https://huggingface.co/nvidia/Nemotron-3-Diarization) | Modèle neuronal de diarisation, jusqu'à huit voix, continuité entre fragments | Environ 100 millions de paramètres ; OpenMDW-1.1 ; la pile NeMo documente principalement Linux/NVIDIA | Candidat alternatif, sans présumer ses performances sur Mac |
| [NeMo-Speech.cpp officiel](https://github.com/NVIDIA/NeMo-Speech.cpp) | Exécution native des modèles de diarisation NVIDIA | Runtime Apache-2.0 ; [compilation CPU et Metal documentée](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/build.md) ; licence des poids distincte | Voie Mac à tester avant d'envisager une grosse installation NeMo Python |
| [sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html) | Segmentation neuronale ONNX et extraction d'empreintes, exécution locale | Vérifier séparément provenance et licences des poids convertis ; modèle Reverb annoncé non commercial | Alternative légère, pas sélectionnée ni téléchargée |

Le [code officiel pyannote](https://github.com/pyannote/pyannote-audio/blob/develop/src/pyannote/audio/pipelines/speaker_diarization.py)
confirme que la différence n'est pas uniquement un autre encodeur vocal : la
segmentation par voix et la reconstruction temporelle font partie de la chaîne.
L'API exclusive facilite l'affectation au texte ; elle ne prouve pas qu'une parole
simultanée ne s'est pas produite. Conserver aussi les tours originaux avec chevauchement.

## Mesure locale reproduite

Le lanceur de benchmark importait le module sans son contexte de package et
échouait sur les imports relatifs du pont natif. Correction limitée à ce lanceur :
import du package Memora sans charger la configuration de l'application ni sa base.

Commande exécutée sur les audios synthétiques existants :

```sh
MEMORA_DIARIZATION_ENGINE=ecapa-tdnn backend/.venv/bin/python \
  scripts/memora-benchmark-diarization.py --run \
  --cases two-fr three-voices overlap \
  --output .memora/qa/diarization/research-20261026.json
```

| Cas | Voix attendues / comptées | DER | Temps de calcul |
| --- | --- | --- | --- |
| Deux voix françaises | 2 / 2 | 2,17 % | 2,986 s |
| Trois voix | 3 / 3 | 3,72 % | 1,244 s |
| Chevauchement | 2 / 2 | 6,41 % | 1,039 s |

DER calculé par trames de 20 ms, permutation optimale, sans tolérance de bord et
chevauchement inclus ; référence d'activité issue de l'énergie des pistes TTS.
Corpus court, déjà connu : il ne valide ni les voix humaines proches, ni les
monologues avec changement de canal, ni une précision générale de 90 %.
Un bon score sur ces cas n'invalide pas les défauts signalés par l'utilisateur.

## Intégration et critères d'acceptation proposés

1. Évaluer un moteur complet dans un environnement isolé, révision et empreintes
   des poids épinglées, inférence sans réseau et sans télémétrie. Ne pas accepter
   automatiquement les conditions de partage de coordonnées d'un compte tiers.
2. Conserver le pont natif authentifié et la tâche durable existants. L'échec du
   nouveau moteur doit rester visible ; aucun retour silencieux à un comptage fictif.
3. Aligner les tours sur les mots horodatés ; lorsqu'un passage contient plusieurs
   voix, éviter d'attribuer toute la phrase arbitrairement à une seule personne.
4. Numéroter les groupes par première apparition, conserver provenance et historique.
   Ne jamais renommer une attribution manquante « Intervenant 1 » pour masquer l'échec.
5. Évaluer sur une réserve synthétique indépendante : monologues, voix proches,
   changements de canal/volume, réponses courtes, interruptions, bruit, chevauchements,
   français/anglais et longues réunions. Rapporter DER pondéré, erreur de comptage,
   durée sans attribution, fragmentation et temps de calcul. Séparer les résultats
   selon le scénario ; comparer aussi le pipeline complet, pas seulement l'encodeur.
6. Vérifier la reprise après panne, les corrections pendant le calcul et la nouvelle
   version publiée sans écraser les corrections ou rapports historiques.

Contraintes locales constatées : seulement 5,4 Gio libres pendant l'audit ; lecture
de la RAM via sysctl refusée dans le sandbox. Aucun téléchargement lourd, installation,
redémarrage, retraitement de réunion personnelle ou changement de moteur effectué.
La correction de la diarisation en conditions réelles reste à valider.
