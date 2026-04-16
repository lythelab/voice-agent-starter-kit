# Voice Agent Starter Kit

<p align="center">
	<img width="100" height="100" alt="image" src="https://github.com/user-attachments/assets/ab1c911c-2476-41f2-8d20-e8b53aa26dfe" />
</p>


<p align="center">
	Open-source starter kit for building real-time voice agents with FastAPI, WebSocket streaming, and pluggable ASR/LLM/TTS providers.
</p>

## What This Project Is

This repository provides a working end-to-end voice interaction loop:

1. Browser captures microphone audio.
2. Backend transcribes speech (ASR).
3. LLM generates streaming response text.
4. TTS synthesizes response audio chunks.
5. Client plays streamed assistant audio with latency telemetry.

It is designed as a practical foundation you can adapt for product prototypes and production pilots.

## Features

- FastAPI backend with health and token endpoints
- Real-time WebSocket audio pipeline
- Streaming assistant text and audio chunk responses
- Client-side voice activity detection (VAD)
- Conversation memory support in the pipeline
- Optional tool-call support in LLM adapter
- In-memory latency metrics and summary endpoint
- Web demo UI in static/index.html

## Repository Structure

```text
main.py                  # Root launcher that imports app.main
app/
	main.py                  # FastAPI app and websocket route
	config.py                # Environment-driven settings
	telemetry.py             # Latency metric store
	pipeline/
		service.py             # ASR -> LLM -> TTS orchestration
		adapters.py            # Provider integrations
		conversation.py        # Conversation state manager
		tools.py               # Tool registry for model calls
	transport/
		daily.py               # Daily.co token + transport helpers
static/
	index.html               # Main browser demo
	index_ws.html            # Alternate/demo websocket page
requirements.txt
Dockerfile
docker-compose.yml
```

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/lythelab/voice-agent-starter-kit
cd voice-agent-starter-kit
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a local .env file from .env.example and fill in your keys:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

- DAILY_API_KEY
- DAILY_DOMAIN
- DAILY_ROOM_NAME
- DEEPGRAM_API_KEY
- GROQ_API_KEY
- GROQ_MODEL
- CARTESIA_API_KEY
- CARTESIA_VOICE_ID

### 3. Run the app

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 in your browser.

## Docker Deployment

### Build and run with Docker

1. Ensure `.env` exists at the repository root (see Configure environment above).
2. Build the image:

```bash
docker build -t voice-agent-starter-kit:latest .
```

3. Run the container:

```bash
docker run --rm -p 8000:8000 --env-file .env voice-agent-starter-kit:latest
```

Open http://127.0.0.1:8000.

### Run with Docker Compose

```bash
docker compose up --build -d
```

To stop:

```bash
docker compose down
```

The service listens on container port 8000 and is mapped to host port 8000.

## API and Transport

- GET /health
- GET /api/latency/summary
- POST /api/transport/token
- WS /ws/audio-pipeline

The websocket emits event types such as:

- ready
- processing
- transcript
- assistant_text_delta
- assistant_audio_chunk
- pipeline_result
- info
- error

## Environment Variables

See .env.example for the full list. Key ones include:

- APP_HOST, APP_PORT
- SYSTEM_PROMPT
- CARTESIA_* output settings
- TTS_FILLER_PROBABILITY
- ENABLE_PREFILL_AUDIO_FILLER

## Security Notes

- Never commit .env or any file containing API keys.
- Rotate provider keys immediately if they were ever committed.
- Use HTTPS in non-local environments for microphone permissions.

## Development Notes

- Keep latency-sensitive calls asynchronous.
- Preserve streaming behavior in websocket events to avoid UI regressions.
- If you add a new provider, implement it behind adapters.py interfaces.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
