# Ollama Setup for TheraSim

This guide covers a local Ollama server and fictional training data. TheraSim
does not bundle Ollama or model weights. The portable TheraSim package targets
Windows x64; only Windows 11 Pro x64 has been exercised for this audit.
Ollama installation instructions for macOS and Linux are provided below, but
TheraSim application support on those platforms is not verified.

## 1. What Ollama does

Ollama downloads and runs language models on your computer and exposes a local
HTTP API. TheraSim's default Ollama URL is
`http://127.0.0.1:11434/v1`. When local-only mode is on, remote model endpoints
are blocked. Do not enter real patient/client information, even when using a
local model.

## 2. Install and verify Ollama

### Windows

1. Download the Windows installer from [ollama.com/download/windows](https://ollama.com/download/windows)
   and complete its installer. Ollama normally runs from its tray application.
2. Open a new PowerShell window and run:

   ```powershell
   ollama --version
   ollama list
   ```

3. Check that the local service is responding:

   ```powershell
   Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version"
   Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags"
   ```

### macOS

Install Ollama from the official [Ollama download page](https://ollama.com/download),
open the application, then run `ollama --version` and `ollama list` in Terminal.
Check the local endpoint with `curl http://127.0.0.1:11434/api/version`.
Quit/reopen the Ollama application to stop/start its local service.

### Linux

Follow the official [Ollama Linux installation instructions](https://github.com/ollama/ollama/blob/main/docs/linux.md).
Then run `ollama --version` and `ollama list`. If installed as a systemd
service, check/manage it with `systemctl status ollama`,
`sudo systemctl start ollama`, and `sudo systemctl stop ollama`; otherwise
start/stop the user-owned service with `ollama serve` in a terminal.
Check `curl http://127.0.0.1:11434/api/version`.

The Windows CLI and endpoint checks above were verified on this workstation with
Ollama 0.34.4. The command syntax is provided by the installed CLI; other
versions may show different help text.

## 3. Download and run a model

Model acquisition generally needs internet access. TheraSim does not download
models automatically. Choose an exact Ollama tag, review its license and
resource requirements, and explicitly acquire it. For example:

```powershell
ollama pull qwen2.5:3b
ollama list
ollama run qwen2.5:3b
```

The installed `qwen2.5:3b` passed seven synthetic PatientAgent output checks
including three repetitions of two English/Persian cases on one Windows
workstation. Its license is
the Qwen Research License Agreement; review those terms before use. Its
EvaluatorAgent report passed four of six structured-output runs, while two
reports failed exact transcript-evidence validation. Two additional
structured smoke reports passed, but this is insufficient to recommend it
for evaluator use. The tested Gemma tag also failed evaluator validation.
These results are hardware- and tag-specific smoke evidence, not a global
model recommendation; see [the model evaluation record](LOCAL_AI_MODEL_EVALUATION.md).

At the interactive prompt, type a fictional test message; use `Ctrl+C` to
leave. Check running model and processor placement with:

```powershell
ollama ps
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
```

`ollama ps` reports whether model layers are on GPU or split between GPU and
CPU. GPU use depends on drivers, available memory, model, and context size; do
not assume the whole model must fit in VRAM. To stop or remove a model, first
confirm its exact tag with `ollama list`:

```powershell
ollama stop gemma-4-E2B:latest
ollama rm gemma-4-E2B:latest
```

`rm` removes local model files and can require downloading the model again.
Do not run it if you want to keep an offline copy. `ollama stop` only unloads
the running model.

## 4. Configure TheraSim

1. Start Ollama and make sure the chosen model appears in `ollama list`.
2. Start TheraSim and sign in to the local reviewer account.
3. Open **Settings**, choose **Ollama**, and set:
   - Host: `127.0.0.1`
   - Port: `11434`
   - Base URL path: `/v1`
   - Model: `qwen2.5:3b` (or an exact locally installed tag)
   - Optional patient/evaluator model overrides: leave blank to use the
     general model, or select exact installed tags for separate roles.
4. Keep **local-only mode** enabled for local inference.
5. Select **Test connection**. A successful test should show the provider
   connection and, if supported by that endpoint, the selected model.
6. Restart TheraSim after saving provider settings; simulation agents read
   their provider configuration at application startup.

The model workspace includes an **optional hardware assessment** button. It
reports local OS, CPU, memory, disk, detected NVIDIA GPU information, and
loopback Ollama version. It does not transmit hardware details, select models,
or download weights. NVIDIA detection depends on `nvidia-smi`; Intel/AMD GPU
details are not currently collected. Resource categories are estimates only.

The combined base URL is `http://127.0.0.1:11434/v1`. The Ollama native API
uses `/api`; the TheraSim provider client uses the OpenAI-compatible `/v1`
interface. A model listing can also be inspected with:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:11434/v1/models"
```

You can change host, port, path, and timeout in the Settings screen or through
the allow-listed per-user config file at
`%LOCALAPPDATA%\TheraSim\config.env`. The timeout setting is
`THERASIM_LLM_TIMEOUT` and must be from 1 to 600 seconds. A non-loopback HTTP
endpoint is rejected. Remote HTTPS endpoints require turning off local-only
mode and explicit confirmation; use them only when you understand where the
prompt text is sent.

## 5. Custom Ollama host or port

Ollama's CLI documents `OLLAMA_HOST` with the default `127.0.0.1:11434`. If
you intentionally run it on a different local port, close the existing
Ollama tray/server first, then in a PowerShell window run:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"
ollama serve
```

Keep that window open while the service is needed. Set TheraSim's host and port
to `127.0.0.1` and `11435`. Do not bind Ollama to `0.0.0.0` or open its port
to a LAN for ordinary local use. A port change applies only to the process
whose environment is set.

## 6. GPU use and memory

Use `ollama ps` to see the loaded model's processor placement and context.
Use `nvidia-smi` to inspect GPU memory. On the audit workstation (15.6 GiB
RAM, Core i7-12650H, RTX 3060 Laptop GPU with 6 GiB VRAM), the tested model
was reported as 100% GPU by `ollama ps`; after the short benchmark, system GPU
memory use was about 2.1 GiB. These are observations for that model and
context, not a hardware guarantee or minimum requirement.

For lower memory use, unload models you are not using, use a smaller quantized
model, close GPU-heavy applications, and avoid increasing the model's context
size unnecessarily. TheraSim currently does not expose a context-size control
in its provider settings. A larger context can materially change memory use.
Do not assume that choosing a Q4 model means all its memory use is exactly
one-quarter of its parameter count.

TheraSim itself does not require NVIDIA, CUDA, or a GPU to start. CPU inference
and acceleration are determined by Ollama, the installed model, the operating
system, and available resources. Confirm actual placement with `ollama ps`;
do not infer support from a model's parameter count alone.

## 7. Offline use

- Download Ollama and the chosen model while internet is available.
- Confirm the model is listed with `ollama list` and can answer locally.
- Once the weights are present, local inference itself does not need internet.
- Start the downloaded TheraSim portable package and Ollama while offline;
  keep the provider pointed at `127.0.0.1` and local-only mode enabled.
- This does not make initial installation/model acquisition offline, nor does
  it prove every operating-system task works offline.

To confirm which model endpoint TheraSim uses, inspect the Settings screen:
Ollama should be active and the base URL should be a loopback address. The
connection test and `ollama ps` should show the selected local model while a
request is running. The update check is user-initiated; it is not required for
ordinary local simulation. Do not select a cloud/remote model tag or remote
provider if you require local inference.

## 8. Common issues

- **Connection refused:** confirm Ollama is running, then check
  `http://127.0.0.1:11434/api/version`.
- **Wrong port:** compare the Ollama `OLLAMA_HOST` and TheraSim Settings. Test
  the exact `/v1/models` URL.
- **Model missing:** run `ollama list`; pull the exact model tag or correct the
  TheraSim model field.
- **Model available but chat fails:** update Ollama if the server does not
  support the OpenAI-compatible chat endpoints, and try the connection test
  again. Do not paste credentials into logs or support exports.
- **ACT evaluation is rejected:** the evaluator uses a strict report schema
  and exact transcript-evidence checks. Ollama structured output can improve
  shape compliance, but it does not guarantee valid evidence or correct
  ratings. The application rejects invalid reports; test the exact tag with
  repeated synthetic PatientAgent and EvaluatorAgent workflows before
  research use.
- **Slow or out of memory:** inspect `ollama ps`/`nvidia-smi`, stop unused
  models, and choose a smaller tag. TheraSim's request timeout defaults to 120
  seconds and is configurable from 1 to 600 seconds.
- **Empty answer:** some thinking-capable models can spend a small output
  budget on hidden reasoning. The built-in connection test requests a short
  visible answer; use a model/configuration that returns text through the
  supported chat API.
- **Local-only blocks the endpoint:** confirm the provider URL uses loopback.
  Do not disable local-only mode simply to bypass a typo.

For application-specific issues, see
[Troubleshooting](TROUBLESHOOTING.md) and
[Windows installation](../INSTALL_WINDOWS.md).
