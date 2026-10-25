# Audit UI du rapport — 25 octobre 2026

Recette réelle isolée : `scripts/memora-verify-isolated.py --ui-audit-only --asr-engine mlx-whisper --french-asr-engine mlx-whisper --timeout 2400`, Chromium1248 factice, DB/comptes/stockage/SMTP jetables. **11 contrôles UI réussis, 4 stages, 22.08s** (21.81s avant nettoyage). Aucune donnée démo/personnelle touchée. Les4portstest18080/13000/11025/18025 sont fermés après nettoyage ; aucune modification de service principal par cet agent.

Sourceproduit inchangée ; seul frontend/tests/memora-ui-audit.mjs étendu. LinttestPASS. Import audio synthétique réel→ASR→rapport local pour disposer d'un vrai rapport, puis statutactionconfirmé enregistré viaAPI et historique consulté. OriginalIA affiché séparément. Métadonnées responsable/échéance, cartespadding/radius, contrôlesduformulaire et absenceoverflow vérifiés sur desktop1440×1000/mobile390×844 et thèmesdata-themeclair/sombre.

Huitcaptures réelles : `agents/logs/isolated-report-design-actions-{desktop,mobile}-{light,dark}.png` et `isolated-report-design-review-{desktop,mobile}-{light,dark}.png`. Desktoplightcarte et mobiledarkformulaire inspectés visuellement : hiérarchie, footer/badge/date, champs lisibles et empilementmobile corrects. Autrescaptures disponibles pour comparaison.

Logs : report-design-ui-audit.log ; isolated-ui-audit.log ; isolated-summary.json passed/demo_data_touchedfalse ; report-design-test-lint.log. Premieréchec conservé dans report-design-first-failure.log : sélecteurgetByLabelexact d'untextarea prérempli, pasproduitfermé. ReproductionHTMLminimale : getByLabelexact0, ariaSnapshottextboxnomexactcorrect. Test corrigé engetByRoletextboxnomexact, sans changerlogiquedeconfirmation/history ni affaiblirpreuve.

Limites : auditvisueletinteractions ciblés, pasqualificationaccessibilitéexhaustive/Safari/iOS/microphysique. Le corpuscourt synthétique ne prouvepasqualitéIAuniverselle. Aucune sourceproduitmodifiée pour fairepasserletest. Fichiersgelés aprèshandoff ; ROOT gère activation/commit.
