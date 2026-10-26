# Séparation des intervenants — recherche du 26 octobre 2026

Statut : recherche suivie d'une implémentation locale `ecapa-segmented`, avec
validation ci-dessous. L'activation de cette installation est consignée dans la
mémoire locale. Les résultats publiés par un fournisseur ne sont pas des résultats
mesurés dans Memora.

## Solution sans compte retenue après comparaison

Le choix utilisateur exclut un compte Hugging Face obligatoire. Community-1 n'a
donc pas été téléchargé. Les essais NVIDIA natifs, sherpa/TitaNet, WeSpeaker et
ERes2Net restent des expériences isolées : un bon comptage cachait parfois des
confusions temporelles ou des fusions de voix. Ils ne remplacent pas le moteur actif.

Le mode **`ecapa-segmented`** conserve ECAPA lorsque les deux tailles de contexte
produisent un comptage cohérent. En cas de trop nombreux groupes ou d'estimations
contradictoires, il utilise une segmentation neuronale ONNX avant de calculer
les empreintes ECAPA. Des fenêtres de 10 secondes, décalées de 5 secondes,
détectent jusqu'à trois activités vocales locales ; les embeddings sont extraits
de la parole exclusive, sans chevauchement. Le regroupement global peut produire
jusqu'à huit intervenants. Deux seuils vérifient la stabilité du résultat ; un
résultat instable reste un échec vérifiable, jamais un comptage arbitrairement forcé.

Ce recours est explicite dans la configuration et dans les métadonnées
`strategy`/`engine`/`recovery_reason`. Les erreurs d'intégrité, les services absents
et les fichiers invalides ne déclenchent pas un remplacement silencieux.
La transcription, ses horodatages et ses identifiants restent inchangés. Les
segments couvrant plusieurs voix ou trop peu de parole peuvent rester sans nom.
La détection des activités simultanées ne sépare pas les pistes audio.

Le modèle de segmentation est la [distribution ONNX publique officielle de
sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/models.html),
convertie depuis segmentation-3.0 et accompagnée de sa licence MIT. Cette chaîne
ne dépend pas de la bibliothèque pyannote ni de sherpa-onnx à l'exécution :
ONNX Runtime et ECAPA sont déjà présents. Le script de préparation fixe le SHA256
de l'archive et des poids ; les licences et les sources sont conservées sur disque.

## Résultats et limites de la solution intégrée

Les 32 cas synthétiques de référence et de variantes de canal/volume sont comptés
correctement. Les 16 relances explicites avec un seul intervenant sont également
vérifiées. Sur une réserve supplémentaire de 12 cas figés : 10 comptages corrects,
une fausse séparation d'un monologue soumis à un changement de canal et au bruit,
et une abstention sur trois voix avec changement de canal et bruit. Le contrôle
strict `--include-holdout` reste donc **en échec**, sans suppression de ces cas ni
assouplissement de son assertion. Cela interdit une affirmation de résolution
universelle ou un score général de précision. Une validation locale autorisée
distincte est conservée exclusivement dans le dossier privé ; aucun score public
n'en est déduit.

Les références synthétiques définissent l'activité par énergie, et les pauses
remplies par la diarisation contribuent aux fausses alarmes du DER. Un nombre
exact d'intervenants ne suffit pas à prouver l'attribution correcte des passages.
Conserver la décomposition omissions/fausses alarmes/confusions et l'écoute humaine
pour les passages incertains. Ni les seuils ni le nombre de groupes ne permettent
d'identifier nominativement une personne.

Installation et utilisation : voir [le guide Memora](MEMORA.md#séparation-des-voix-sans-compte).
Les anciens résultats ne sont pas retraités automatiquement. Une nouvelle séparation
est publiée dans une nouvelle version, puis le rapport doit être régénéré.

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

## Reprise complète Core ML/VBx après double abstention

Un second contrôle a confirmé une limite du recours par segmentation seule :
le comptage peut encore varier selon le seuil de regroupement. La sélection ne
force aucun nombre pour masquer cette contradiction. Le compagnon distingue
maintenant cette incertitude acoustique (`speaker_count_uncertain`) d’une panne
HTTP du moteur ; le worker conserve un code stable et un message de reprise,
sans enregistrer l’exception du modèle ou le contenu audio.

Une option locale supplémentaire, `MEMORA_DIARIZATION_RECOVERY=community-coreml`,
active **uniquement après les deux abstentions acoustiques** le pipeline offline
FluidAudio Community-1 : segmentation, WeSpeaker, transformation PLDA et VBx.
Les succès ECAPA ou segmentation restent inchangés. Les erreurs d’intégrité,
fichiers invalides ou service indisponible ne déclenchent jamais ce recours.

Distribution examinée : [FluidAudio v0.17.7](https://github.com/FluidInference/FluidAudio/tree/v0.17.7),
commit `503b4bd1bbf7220882de39fe8ae6716aae4132da`, code Apache-2.0.
Les [conversions Core ML publiques](https://huggingface.co/FluidInference/speaker-diarization-coreml/tree/7eab74f3463c736418d0eb10296261ae581146c9)
sont accessibles sans compte ni jeton. Leur périmètre CC-BY-4.0 et les attributions
pyannote, WeSpeaker, BUT Speech@FIT et Fluid Inference sont conservés dans NOTICE.
Leur provenance historique est reconstruite, pas entièrement attestée ; les SHA
figent la distribution examinée, sans constituer une signature de l’auteur.
Seuls quatre bundles utilisés et les paramètres/licences nécessaires sont installés,
environ 21 Mo. Aucun checkpoint amont à accès restreint n’est téléchargé.

Le binaire est construit localement avec Swift 6.2+, sur Apple Silicon/macOS 15+.
Le manifeste de build écarte le composant TTS inutile sans changer les sources
Swift/C++ du SDK. Le chargement est direct depuis les bundles vérifiés ; le mode
hors ligne est forcé. Le traitement reste borné à deux heures/huit groupes, avec
suppression des fichiers PCM temporaires même après erreur. Le hash du binaire
contrôle l’intégrité locale, pas une signature ni une compilation reproductible
attestée. Le Docker applicatif appelle ce composant natif privé, comme les moteurs MLX.

Validation réelle du recours intégré : 32/32 comptages automatiques corrects sur
les corpus principaux et variantes ; 16/16 reprises à une voix connue correctes.
Sur les 12 cas de réserve déjà utilisés, 11 comptages corrects et une fausse
séparation d’un monologue avec changement de canal/bruit persistent. Soit 43/44
comptages automatiques corrects sur ce corpus précis, **pas un score de précision
d’attribution ni une généralisation**. Le benchmark strict reste en échec (code 1),
car ce dernier cas n’est pas retiré. Le nouveau recours remplace l’abstention
restante à trois voix sans modifier les succès antérieurs. Les métriques DER des
cas ECAPA réussis restent inchangées. Employé seul, FluidAudio fusionne certaines
voix sur d’autres cas synthétiques : il n’est donc pas choisi comme remplacement
global. Aucun seuil n’a été ajusté sur l’enregistrement privé autorisé.
