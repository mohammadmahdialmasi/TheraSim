# Run analytics

TheraSim's Run analytics are descriptive views over persisted records. The
selected simulation Run is the data scope. Counts and observations are fetched
from the Run analytics API; the frontend does not use mock or sample arrays.
The JSON download contains the API snapshot and may contain sensitive
operational identifiers.

## Competency observations

Observations are grouped by competency ID, rubric ID, rubric version ID, and
rubric content hash. Different rubric definitions are not combined. For each
selected group and completed-session range, the UI reports:

- **Evaluable observations:** observations whose rating code is not `NE`.
- **Not evaluable:** observations explicitly rated `NE`.
- **Missing observations:** completed sessions with no reportable observation
  for this competency and rubric group, with the API-provided reason.
- **Evidence coverage:** evaluable observations that have one or more
  transcript-message evidence references divided by the number of evaluable
  observations. This measures reference presence only, not whether evidence
  semantically supports a rating.
- **Confidence distribution:** persisted confidence labels. Confidence is not
  correctness or validity.
- **Human review outcomes:** appended review decisions attached to observations
  in the selected range. These are provenance counts, not consensus scores.
- **Raw rating-code change:** last numeric rating code minus first numeric
  rating code in the range. No values are averaged, and this calculation is
  not made when fewer than two numeric observations exist.

The SVG chart plots numeric raw rating codes against completed-session number
for one selected competency and exact rubric group. `NE` and missing
observations are not plotted or converted to zero. A line segment is drawn only
between consecutive session numbers, so gaps remain visible. Each point links
to the corresponding persisted evaluation record in the page.

The chart identifies the raw rating-code axis and scope, and provides an empty
state when no numeric observations are available. Loading and request-error
states are shown separately. It is an exploratory descriptive display, not a
validated longitudinal trend, competency measurement, or clinical outcome.
Evidence-reference presence, machine confidence, and human review decisions
must not be interpreted as proof of correctness.

## Other Run-level summaries

Session completion history, behavioral event counts, memory status counts,
character-state transition records, plan revisions, and evaluation status and
staleness are presented from persisted Run records. These summaries do not
infer treatment progress or patient improvement. The analytics response omits
transcript and case text, but identifiers and timestamps may still be
sensitive.

## Limitations

Analytics are bounded by the records that exist and the validation performed
when those records were created. They do not establish clinical validity,
psychometric validity, evaluator reliability, treatment effectiveness, or
simulated-client realism. Independent qualified expert review and empirical
validation remain necessary before making such claims. No cross-Run comparison,
compatible-rubric normalization, inferential statistics, or autonomous
treatment-plan adaptation is provided.
