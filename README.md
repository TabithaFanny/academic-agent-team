# Academic Agent Team (MVP Scaffold)

This repository is a runnable MVP scaffold aligned with PRD v1.5 sections 7.6-7.10.

## Quick Start

```bash
cd academic-agent-team
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

paper-team start --mock --topic "测试课题" --journal "中文核心" --no-interactive
```

The command above will create:

- `session_store/sessions.db`
- `session_store/logs/<session_id>.log`
- `output/<session_id>/` (stage payload json + paper markdown)

## Commands

- `paper-team start --mock ...`: run the full mock pipeline and persist artifacts.
- `paper-team debug <session_id>`: print session summary and recent log events.

## Tests

```bash
pytest tests/ -p no:cacheprovider
```

## Current Scope

- PRD 7.6 interface contract validator (5 stage payloads)
- PRD 7.7 model registry + base client + fallback chain (mock-first)
- PRD 7.8 SQLite schema + persistence helpers
- PRD 7.9 JSONL session logger
- PRD 7.10 mock mode runnable pipeline
