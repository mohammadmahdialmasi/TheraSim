# TheraSim bilingual terminology glossary

Use the English term and its Persian equivalent consistently in user-facing
copy. Preserve identifiers, model names, and API/database field names exactly
as they appear in code.

| English | فارسی | Usage note |
|---|---|---|
| Simulation | شبیه‌سازی | The application simulates practice conversations; it does not provide therapy. |
| Patient Agent | عامل مراجع شبیه‌سازی‌شده | A software agent representing a fictional client, not a real patient. |
| Patient / Client | مراجع | Prefer «مراجع» for the fictional person in a therapy context. |
| Therapist | درمانگر | Use consistently; do not alternate with «درمان‌گر». |
| Evaluator / Evaluator Agent | ارزیاب / عامل ارزیاب | The evaluator is experimental and requires human review. |
| Assessment / Evaluation | ارزیابی | Use for the act or report; do not imply validated measurement. |
| Session | جلسه | For a persisted interaction unit. |
| Transcript | رونوشت | The record of messages in a session. |
| Treatment Plan | طرح درمان | Use «طرح درمان» rather than alternating with «برنامهٔ درمان». |
| Psychological Flexibility | انعطاف‌پذیری روان‌شناختی | ACT process concept; not a validated score in TheraSim. |
| Experiential Avoidance | اجتناب تجربه‌ای | ACT process concept; do not equate it with every form of avoidance. |
| Cognitive Fusion | آمیختگی شناختی | ACT process concept. Use «گسلش شناختی» for *cognitive defusion*. |
| ACT | درمان مبتنی بر پذیرش و تعهد (ACT) | First mention may expand the Persian name; retain ACT thereafter. |
| Longitudinal Evaluation | ارزیابی طولی | Evaluation across multiple completed sessions; currently experimental. |
| Clinical Scenario | سناریوی بالینیِ داستانی | Use only for fictional educational scenarios; never imply real clinical records. |
| Rubric | معیارنامهٔ ارزیابی | Use in user-facing Persian text. Keep identifiers such as `ACT_RUBRIC_V0` unchanged. |
| Memory | حافظه | For the system capability or records; use «خاطره» only for an autobiographical content item. |
| Run | اجرای شبیه‌سازی | Keep run IDs and internal API fields unchanged. |
| Backend | بک‌اند | Acceptable technical loanword; use consistently instead of mixing with «Backend». |
| Provider endpoint | نشانی ارائه‌دهندهٔ مدل | The configured endpoint may be remote; do not imply it is always local. |

## Terms requiring domain review

- Persian translations of ACT process concepts vary across clinical and
  academic sources. The choices above are editorial conventions for this
  prototype, not claims that one translation is clinically authoritative.
- The UI currently uses provisional descriptive Persian labels for `psychological_workability`,
  `disclosure_integration`, and `clinical_responsiveness`. Their scope is rubric-
  specific and should be reviewed by a Persian-speaking ACT and psychometrics
  specialist before reuse as authoritative terminology.
- «سناریوی بالینیِ داستانی» is intentionally explicit because all project
  examples must remain synthetic.
- The project has not established a validated Persian assessment vocabulary.
  Review any future competency-dimension labels with a Persian-speaking ACT
  and psychometrics reviewer before presenting them as authoritative.
