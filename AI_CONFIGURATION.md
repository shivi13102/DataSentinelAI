# Local AI Configuration

## Current provider and model

The reasoning implementation uses the local Ollama HTTP API. The default
model is **`gemma3:1b`**. There is no OpenAI, Anthropic, or other hosted LLM
provider in the current reasoning path. LangGraph is an in-process Python
library and does not itself require an external service.

Configuration is read from environment variables at Python process startup:

| Variable | Default | Meaning |
|---|---|---|
| `DATASENTINEL_AI_PROVIDER` | `ollama` | Must be `ollama` for the supported local provider. |
| `DATASENTINEL_AI_MODEL` | `gemma3:1b` | Exact installed Ollama model tag. |
| `DATASENTINEL_OLLAMA_URL` | `http://127.0.0.1:11434` | Local Ollama base URL. |
| `DATASENTINEL_AI_TIMEOUT_SECONDS` | `45` | Bounded reasoning request timeout; invalid non-integer settings fail at startup. |

Set values before starting Uvicorn, for example:

```powershell
$env:DATASENTINEL_AI_PROVIDER = 'ollama'
$env:DATASENTINEL_AI_MODEL = 'gemma3:1b'
$env:DATASENTINEL_OLLAMA_URL = 'http://127.0.0.1:11434'
$env:DATASENTINEL_AI_TIMEOUT_SECONDS = '45'
```

The application does not automatically download models. Install/pull the
model manually while internet is available:

```powershell
ollama pull gemma3:1b
ollama list
```

Start the Ollama desktop application or run `ollama serve` in a separate
terminal if the service is not already active.

## Verify actual inference

With the backend running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/ai
```

`AVAILABLE` means the API reached Ollama, found the configured model tag, and
received a completed non-empty inference response. Other statuses are
`MODEL_NOT_INSTALLED`, `OLLAMA_UNAVAILABLE`, `INFERENCE_FAILED`, or
`NOT_CONFIGURED`. The endpoint runs a real inference and may take up to 30
seconds; use it for preflight/manual checks rather than polling it frequently.
It returns status and timing, not generated test text or secrets.

The root `/api/health` endpoint only reports configuration and API status; it
does not claim the model is available.

## Failure behavior and troubleshooting

- If Ollama is unavailable or model inference times out/fails, deterministic
  analysis and the protection gate continue. The AI error is displayed without
  fabricated explanation.
- Check service reachability with `Invoke-WebRequest
  http://127.0.0.1:11434/api/tags`.
- If the configured model is missing, compare the exact configured value with
  the output of `ollama list`; install it manually if appropriate.
- If inference is slow, use a smaller locally supported model or adjust the
  timeout deliberately. The configured timeout remains bounded.
- Keep uploaded CSV data on the laptop. The AI request sends measured finding
  evidence to the configured Ollama URL. Pointing that URL at a remote server
  will send that evidence outside the machine.

