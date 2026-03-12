from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.genai import types

from app.adk.agent import build_root_agent
from app.adk.runner import LiveSessionHandle, start_live_session
from app.adk.tools import build_tools
from app.config import settings
from app.integrations.ankor_api import AnkorApiClient
from app.session_state import SessionState, new_session_state


logger = logging.getLogger("ankor_voice_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger.setLevel(logging.INFO)
logging.getLogger("ankor_voice_agent.integrations.ankor_api").setLevel(logging.INFO)

app = FastAPI()
_WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/ui/assets", StaticFiles(directory=_WEB_DIR), name="ui-assets")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "model": settings.live_model}


@app.get("/")
def ui_root() -> FileResponse:
    return FileResponse(_WEB_DIR / "index.html")


@app.get("/ui")
def ui_page() -> FileResponse:
    return FileResponse(_WEB_DIR / "index.html")


def _state_summary(state: SessionState) -> Dict[str, Any]:
    return {
        "missing_fields": state.missing_fields,
        "ambiguous_fields": state.ambiguous_fields,
        "ready_for_confirmation": state.ready_for_confirmation,
    }


@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    session_id = str(uuid4())
    access_token: Optional[str] = None
    state: Optional[SessionState] = None
    live_session: Optional[LiveSessionHandle] = None
    manual_activity_active = False

    async def send_message(message: Dict[str, Any]) -> None:
        await websocket.send_json(message)

    async def stop_live_session() -> None:
        nonlocal live_session, manual_activity_active
        if live_session:
            await live_session.close()
        live_session = None
        manual_activity_active = False

    try:
        async with AnkorApiClient(
            base_url=settings.ankor_api_base_url,
            timeout_s=settings.http_timeout_s,
        ) as client:
            while True:
                payload = await websocket.receive_json()
                msg_type = payload.get("type")
                if not isinstance(msg_type, str):
                    await send_message(
                        {
                            "type": "error",
                            "code": "invalid_message",
                            "message": "Missing or invalid message type",
                        }
                    )
                    continue

                if msg_type == "ping":
                    await send_message({"type": "pong", "id": payload.get("id", "")})
                    continue

                if msg_type == "auth":
                    token = payload.get("access_token")
                    if not token or not isinstance(token, str):
                        await send_message(
                            {
                                "type": "auth_error",
                                "message": "Missing access token",
                            }
                        )
                        await websocket.close(code=1008)
                        break
                    access_token = token
                    await send_message({"type": "auth_ok", "session_id": session_id})
                    continue

                if msg_type == "session_init":
                    if not access_token:
                        await send_message(
                            {
                                "type": "auth_error",
                                "message": "Authenticate before session_init",
                            }
                        )
                        await websocket.close(code=1008)
                        break

                    org_id = payload.get("org_id")
                    if not org_id or not isinstance(org_id, str):
                        await send_message(
                            {
                                "type": "error",
                                "code": "invalid_session_init",
                                "message": "org_id is required",
                            }
                        )
                        continue

                    state = new_session_state(
                        session_id=session_id,
                        access_token=access_token,
                        org_id=org_id,
                        team_id=payload.get("team_id"),
                        coach_id=payload.get("coach_id"),
                    )

                    tools = build_tools(client, state)
                    agent = build_root_agent(tools)

                    await send_message(
                        {
                            "type": "state_update",
                            "summary": _state_summary(state),
                        }
                    )

                    await stop_live_session()
                    live_session = await start_live_session(
                        state, agent, send_message
                    )
                    continue

                if msg_type == "session_control":
                    action = payload.get("action")
                    if action != "reset":
                        await send_message(
                            {
                                "type": "error",
                                "code": "invalid_control",
                                "message": "Unsupported session_control action",
                            }
                        )
                        continue
                    if not state or not access_token:
                        await send_message(
                            {
                                "type": "error",
                                "code": "no_session",
                                "message": "Session not initialized",
                            }
                        )
                        continue
                    session_id = str(uuid4())
                    state = new_session_state(
                        session_id=session_id,
                        access_token=access_token,
                        org_id=state.org_id,
                        team_id=state.team_id,
                        coach_id=state.coach_id,
                    )
                    tools = build_tools(client, state)
                    agent = build_root_agent(tools)
                    await stop_live_session()
                    live_session = await start_live_session(
                        state, agent, send_message
                    )
                    await send_message(
                        {
                            "type": "state_update",
                            "summary": _state_summary(state),
                        }
                    )
                    await send_message(
                        {"type": "auth_ok", "session_id": session_id}
                    )
                    continue

                if msg_type in {"input_audio_chunk", "input_text", "client_event"}:
                    if not state:
                        await send_message(
                            {
                                "type": "error",
                                "code": "no_session",
                                "message": "Send session_init before streaming input",
                            }
                        )
                        continue
                    if not live_session:
                        await send_message(
                            {
                                "type": "error",
                                "code": "no_live_session",
                                "message": "Live session not started",
                            }
                        )
                        continue

                    if msg_type == "input_audio_chunk":
                        data = payload.get("data")
                        sample_rate_hz = payload.get("sample_rate_hz")
                        channels = payload.get("channels")
                        audio_format = payload.get("format")
                        if (
                            not isinstance(data, str)
                            or sample_rate_hz != 16000
                            or channels != 1
                            or audio_format != "pcm16le"
                        ):
                            await send_message(
                                {
                                    "type": "error",
                                    "code": "invalid_audio",
                                    "message": "Audio must be PCM16LE mono at 16kHz",
                                }
                            )
                            continue

                        try:
                            audio_bytes = base64.b64decode(data, validate=True)
                        except ValueError:
                            await send_message(
                                {
                                    "type": "error",
                                    "code": "invalid_audio",
                                    "message": "Audio payload is not valid base64",
                                }
                            )
                            continue

                        if settings.manual_activity_signals and not manual_activity_active:
                            live_session.queue.send_activity_start()
                            manual_activity_active = True

                        blob = types.Blob(
                            data=audio_bytes,
                            mime_type="audio/pcm;rate=16000",
                        )
                        live_session.queue.send_realtime(blob)
                        continue

                    if msg_type == "input_text":
                        text = payload.get("text")
                        if not isinstance(text, str) or not text.strip():
                            await send_message(
                                {
                                    "type": "error",
                                    "code": "invalid_text",
                                    "message": "input_text requires non-empty text",
                                }
                            )
                            continue
                        content = types.Content(
                            role="user", parts=[types.Part(text=text)]
                        )
                        live_session.queue.send_content(content)
                        continue

                    if msg_type == "client_event":
                        if payload.get("name") == "end_of_utterance":
                            if settings.manual_activity_signals and manual_activity_active:
                                live_session.queue.send_activity_end()
                                manual_activity_active = False
                    continue

                await send_message(
                    {
                        "type": "error",
                        "code": "unknown_type",
                        "message": f"Unknown message type: {msg_type}",
                    }
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
    finally:
        await stop_live_session()
