from __future__ import annotations

import asyncio
import contextlib
import base64
import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.config import settings
from app.session_state import SessionState
from app.ws_protocol import ServerMessage


SendMessage = Callable[[ServerMessage], Awaitable[None]]

logger = logging.getLogger("ankor_voice_agent")

_session_service = InMemorySessionService()


@dataclass
class LiveSessionHandle:
    queue: LiveRequestQueue
    task: asyncio.Task

    async def close(self) -> None:
        self.queue.close()
        if not self.task.done():
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task


def _build_run_config() -> RunConfig:
    realtime_input_config = None
    if settings.manual_activity_signals:
        realtime_input_config = types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
        )

    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=[types.Modality.AUDIO],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=realtime_input_config,
    )


def _parse_sample_rate(mime_type: Optional[str], default_rate: int = 16000) -> int:
    if not mime_type:
        return default_rate
    match = re.search(r"rate=(\d+)", mime_type)
    if not match:
        return default_rate
    try:
        return int(match.group(1))
    except ValueError:
        return default_rate


async def _emit_event_messages(event: Event, send_message: SendMessage) -> None:
    if event.error_code or event.error_message:
        await send_message(
            {
                "type": "error",
                "code": event.error_code or "model_error",
                "message": event.error_message or "Unknown model error",
            }
        )

    if event.input_transcription and event.input_transcription.text:
        finished = getattr(event.input_transcription, "finished", False)
        await send_message(
            {
                "type": "final_transcript" if finished else "partial_transcript",
                "text": event.input_transcription.text,
            }
        )

    if event.output_transcription and event.output_transcription.text:
        finished = getattr(event.output_transcription, "finished", True)
        if finished:
            await send_message(
                {"type": "agent_message", "text": event.output_transcription.text}
            )

    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.inline_data and part.inline_data.data:
                if part.inline_data.mime_type and part.inline_data.mime_type.startswith(
                    "audio/"
                ):
                    data_b64 = base64.b64encode(part.inline_data.data).decode("ascii")
                    sample_rate_hz = _parse_sample_rate(part.inline_data.mime_type)
                    await send_message(
                        {
                            "type": "agent_audio_chunk",
                            "data": data_b64,
                            "sample_rate_hz": sample_rate_hz,
                            "channels": 1,
                            "format": "pcm16le",
                            "seq": None,
                        }
                    )
            elif part.text:
                await send_message({"type": "agent_message", "text": part.text})

    if settings.expose_tool_events:
        for call in event.get_function_calls() or []:
            await send_message(
                {
                    "type": "tool_call",
                    "name": call.name,
                    "args": call.args,
                }
            )
        for response in event.get_function_responses() or []:
            await send_message(
                {
                    "type": "tool_result",
                    "name": response.name,
                    "result": response.response,
                }
            )


async def _consume_events(
    runner: Runner,
    user_id: str,
    session_id: str,
    queue: LiveRequestQueue,
    run_config: RunConfig,
    send_message: SendMessage,
) -> None:
    try:
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=queue,
            run_config=run_config,
        ):
            await _emit_event_messages(event, send_message)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Live session error: %s", exc)
        await send_message(
            {
                "type": "error",
                "code": "live_session_error",
                "message": "Live session failed",
            }
        )


async def start_live_session(
    state: SessionState,
    agent: Any,
    send_message: SendMessage,
) -> LiveSessionHandle:
    runner = Runner(
        app_name=settings.app_name,
        agent=agent,
        session_service=_session_service,
        auto_create_session=True,
    )
    user_id = state.coach_id or state.org_id or state.session_id
    session_id = state.session_id
    run_config = _build_run_config()
    queue = LiveRequestQueue()
    task = asyncio.create_task(
        _consume_events(runner, user_id, session_id, queue, run_config, send_message)
    )
    return LiveSessionHandle(queue=queue, task=task)
