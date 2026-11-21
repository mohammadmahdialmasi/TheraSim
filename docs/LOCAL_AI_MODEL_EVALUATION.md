# Local AI Model Evaluation

**Run date:** 2026-11-20
**Purpose:** small, reproducible engineering smoke test for local TheraSim
model use. This is not a clinical trial, clinical validation, psychometric
validation, or evidence of therapeutic effectiveness.

## Environment and candidate

| Item | Observed value |
|---|---|
| Ollama | `0.34.4` |
| Installed model tag tested | `gemma-4-E2B:latest` |
| Ollama model ID | `32632e5db6f6` |
| Architecture / parameter count | Gemma 4 / 4.6B |
| Quantization | `Q4_K_M` (`ollama show`) |
| Model context reported by metadata | 131,072 tokens |
| Runtime context reported by `ollama ps` | 65,536 tokens |
| Model size reported by `ollama list` | 3.4 GB |
| Active model placement | 100% GPU; `ollama ps` reported 1.7 GB loaded |
| Workstation RAM / CPU | 15.6 GiB / Intel Core i7-12650H (10 cores, 16 logical processors) |
| GPU | NVIDIA RTX 3060 Laptop GPU, 6,144 MiB VRAM |
| Total GPU memory used after short run | About 2.1 GiB (`nvidia-smi`; includes all GPU allocations) |

The host differs from the originally anticipated RTX 3080 Ti/8 GiB VRAM.
The installed model list also showed `gemma-4-E2B-it:latest` with the same
Ollama ID; it is an alias of the same installed model content, not an
independent candidate.

The current Ollama library lists the canonical `gemma4:e2b` variant as
Q4_K_M, about 4.6 GB for that quantized model package, and publishes an
Apache-2.0 license on its model page. That canonical tag was **not** installed
or tested here. `ollama show --license` returned no license text for the
locally installed legacy-named tag, so verify the exact tag's terms before
redistribution. TheraSim does not redistribute or bundle model weights.
References: [Ollama Gemma 4 model page](https://ollama.com/library/gemma4:e2b)
and [Gemma 4 Apache 2.0 license](https://gemma.ai/resources/apache-2/).

## Reproducible methodology

The prompt-only smoke tool makes short requests. For the actual application
workflows, run the new benchmark from the repository root with a local Ollama
server and the selected model already installed:

```powershell
ollama --version
ollama list
.\.venv\Scripts\python.exe scripts\benchmark_agent_workflows.py `
  --model qwen2.5:3b --repeats 3 `
  --output local-model-benchmark.json
```

The actual-workflow benchmark calls the application's `PatientAgent` and
`EvaluatorAgent`, uses synthetic English and Persian cases, and runs each
case sequentially for the requested repeat count. It rejects non-loopback
endpoints, does not download model weights, does not persist transcripts, and
does not include generated response text in its report. The output includes
hardware inventory and should be reviewed before sharing. The separate
`scripts/benchmark_ollama.py` script remains a smaller prompt-only smoke tool;
it must not be used as evidence of full agent compatibility.

The prompt-only tool uses four synthetic, deterministic (`temperature=0`)
prompts and disables optional thinking for this short-response comparison:

1. English fictional-client persona response.
2. Persian fictional-client persona response.
3. English follow-up that checks a detail from the preceding turn.
4. JSON object with an exact two-field schema.

It records wall-clock latency, prompt/generation token counts, text output,
and structural JSON validity. Review linguistic quality and persona
consistency manually; the script does not claim to score subjective qualities
automatically. Tests were run with the model already loaded, so timings are
warm-request latencies, not first-load times. The request prompts are
synthetic and are not written to a database.

## Measured smoke results

| Case | Latency | Prompt / generated tokens | Observation |
|---|---:|---:|---|
| English persona | 0.979 s | 87 / 66 | Stayed in the invented help-avoidance role and did not give advice in this sample. |
| Persian persona | 0.301 s | 103 / 29 | Returned a short Persian answer; one pronoun/person mismatch was observed, so Persian output needs review. |
| English context follow-up | 0.112 s | 93 / 9 | Recalled the earlier fear as “not good enough”; limited to one short turn. |
| Structured JSON | 0.371 s | 71 / 35 | JSON parsed and contained the required keys and value types. |

Four-case total: 1.763 seconds and 139 generated tokens. These small warm
requests do not estimate long-session latency or sustained throughput. A
separate real TheraSim `PatientAgent` call with a synthetic Persian context
returned schema-valid output in 4.397 seconds.

### Actual TheraSim agent workflow

The role-specific OpenAI-compatible client now sends Ollama's strict
`response_format: json_schema` request for evaluator reports. It requires all
schema fields, constrains competency IDs to the loaded rubric, and fixes the
array length to the rubric size. The application's independent Pydantic,
rubric-ID, therapist-speaker, message-ID, and exact-quote checks still run
after generation. Invalid output is rejected; it is not repaired, stored, or
presented as a valid evaluation. Other provider adapters do not receive this
Ollama-specific capability because they have not been verified with this
contract.

Results on the single workstation described above:

| Model/tag | PatientAgent | EvaluatorAgent | Interpretation |
|---|---|---|---|
| `gemma-4-E2B:latest` | 1/1 smoke passed, 10.62 s | 0/3 accepted; unconstrained report had invalid array-field types, and a production structured-output report failed evidence-speaker/source validation in 41.52 s | Not evaluator-compatible. Structurally guided output still violated transcript grounding. |
| `qwen2.5:3b` | 7/7 synthetic PatientAgent calls passed, including English and Persian cases repeated three times; mean 3.03 s across seven calls | 4/6 reports accepted across two synthetic cases repeated three times; mean 42.14 s. Two additional structured contract smokes passed; one unconstrained report failed. | Not recommended for evaluator use: two repeated-run outputs failed exact transcript-quote validation, and rating accuracy was not independently judged. |
| `Qwen3.5:9b` | 0/1; no valid visible response after 119 s | 0/1; timed out after 600 s | Not suitable on this tested configuration. |

In the repeated Qwen2.5:3b benchmark, invalid evidence was rejected and never
stored. Four accepted reports had all ten rubric competency IDs and passed
the complete schema and exact-quote checks. Two reports failed exact
transcript evidence validation. Two separate structured smoke reports also
passed; one contained 20 exact therapist-message evidence references. These
checks do not show that the competency ratings were substantively correct,
consistent, or suitable for research conclusions. No independent human
scoring comparison was run.

The initial evaluator failure had two distinguishable causes. The application
did not previously pass a provider structured-output request, while the
unconstrained model outputs contained contract defects (wrong field types,
omitted fields, or invalid evidence references). Adding strict schema
generation materially improved the Qwen2.5:3b result, but did not make every
model comply. No evidence indicates that the Pydantic schema or evidence
validator should be weakened; those checks correctly rejected invalid output.
The earlier `TypeError` observed during one probe came from the probe's attempt
to serialize a Python `set` after `evaluate()` had succeeded, not from
TheraSim's evaluator.

Machine-readable per-tag data, quantization, licenses, hardware, and role
results are in [`config/model-compatibility.json`](../config/model-compatibility.json).

## Suitability and decision

- **Instruction following / persona:** encouraging in the one short English
  sample; not measured across a sample set.
- **English:** one short prompt was coherent and stayed in persona.
- **Persian:** one short prompt was understandable but contained a
  first-/third-person agreement issue. A bilingual reviewer must inspect
  generated language.
- **Context retention:** one short follow-up retained an earlier concern.
  Longitudinal context retention was not tested.
- **Structured output:** one two-key JSON response passed a strict shape check.
  This does not measure reliability across repeated evaluator reports.
- **Emotional/interpersonal response:** one sample expressed plausible
  reluctance; no calibrated naturalness scale was used.
- **Evaluation response consistency:** no model is recommended. In three
  repetitions of each synthetic scenario, `qwen2.5:3b` passed four of six
  complete structural/evidence contracts; two outputs failed exact-quote
  validation. `gemma-4-E2B:latest` and `Qwen3.5:9b` failed actual evaluation runs.
- **Speed and resources:** the four short prompts returned in 0.112–0.979 s
  while the model was already loaded and GPU-resident. This is not a cold
  start or sustained-load result.
- **Offline:** the endpoint used in testing was loopback and model weights were
  already present. The host was not disconnected from the internet during
  testing, so full network-disconnected behavior was not verified.

**Simulated-client guidance:** `qwen2.5:3b` and `gemma-4-E2B:latest` each
passed one real synthetic PatientAgent schema smoke test on this workstation.
Treat these as test candidates, not global recommendations. Qwen's exposed
license is a research license; review it before use. The exact license for the
legacy Gemma tag could not be retrieved from the installed metadata.

**Evaluator guidance:** no model is recommended. Qwen2.5:3b passed four of
six structured reports across two synthetic cases repeated three times, but
two reports failed exact quote validation and no rating accuracy comparison
was performed. Two additional structured smoke reports passed, but this does
not establish repeatable reliability. The application allows
separate patient/evaluator model IDs and falls back to one shared model when
role-specific fields are blank. This changes configuration only and does not
keep two models loaded simultaneously; the provider controls model residency.

## Limitations

- Only three distinct model contents were tested. Alias tags with identical
  Ollama IDs are not independent candidates.
- Real PatientAgent and EvaluatorAgent runs used synthetic scenarios. The
  repeated evaluator benchmark is still small (two cases, three repetitions
  each) and is not sufficient for a reliability recommendation.
- Only one Windows x64 workstation was tested; CPU-only, integrated-graphics,
  other GPU tiers, other operating systems, and clean machines were not.
- The test does not measure behavior over realistic long therapy sessions,
  safety performance, transcript-grounding across many competencies, or
  evaluation reproducibility.
- Prompt-level tests do not establish clinical or psychometric validity.
- Model availability, exact tags, licenses, and quantization can change.
- A model's output must be reviewed. Do not use it to diagnose, treat, certify
  competence, or make decisions about real people.
