from __future__ import annotations

from typing import Any, Dict, Literal, Optional, TypedDict, Union


# ---------- Client -> Server ----------


class AuthMessage(TypedDict):
    type: Literal["auth"]
    access_token: str


class SessionInitMessage(TypedDict):
    type: Literal["session_init"]
    org_id: str
    team_id: Optional[str]
    coach_id: Optional[str]
    evaluation_flow: Literal["create_evaluation"]
    locale: str


class InputAudioChunkMessage(TypedDict):
    type: Literal["input_audio_chunk"]
    data: str  # base64 PCM16LE
    sample_rate_hz: int
    channels: int
    format: Literal["pcm16le"]
    seq: Optional[int]
    timestamp_ms: Optional[int]


class InputTextMessage(TypedDict):
    type: Literal["input_text"]
    text: str


class ClientEventMessage(TypedDict):
    type: Literal["client_event"]
    name: Literal["end_of_utterance"]


class SessionControlMessage(TypedDict):
    type: Literal["session_control"]
    action: Literal["reset"]


class PingMessage(TypedDict):
    type: Literal["ping"]
    id: str


ClientMessage = Union[
    AuthMessage,
    SessionInitMessage,
    InputAudioChunkMessage,
    InputTextMessage,
    ClientEventMessage,
    SessionControlMessage,
    PingMessage,
]


# ---------- Server -> Client ----------


class AuthOkMessage(TypedDict):
    type: Literal["auth_ok"]
    session_id: str


class AuthErrorMessage(TypedDict):
    type: Literal["auth_error"]
    message: str


class PartialTranscriptMessage(TypedDict):
    type: Literal["partial_transcript"]
    text: str


class FinalTranscriptMessage(TypedDict):
    type: Literal["final_transcript"]
    text: str


class AgentMessage(TypedDict):
    type: Literal["agent_message"]
    text: str


class AgentAudioChunkMessage(TypedDict):
    type: Literal["agent_audio_chunk"]
    data: str  # base64 PCM16LE
    sample_rate_hz: int
    channels: int
    format: Literal["pcm16le"]
    seq: Optional[int]


class StateUpdateMessage(TypedDict):
    type: Literal["state_update"]
    summary: Dict[str, Any]


class ToolCallMessage(TypedDict):
    type: Literal["tool_call"]
    name: str
    args: Dict[str, Any]


class ToolResultMessage(TypedDict):
    type: Literal["tool_result"]
    name: str
    result: Dict[str, Any]


class ErrorMessage(TypedDict):
    type: Literal["error"]
    code: str
    message: str


class PongMessage(TypedDict):
    type: Literal["pong"]
    id: str


ServerMessage = Union[
    AuthOkMessage,
    AuthErrorMessage,
    PartialTranscriptMessage,
    FinalTranscriptMessage,
    AgentMessage,
    AgentAudioChunkMessage,
    StateUpdateMessage,
    ToolCallMessage,
    ToolResultMessage,
    ErrorMessage,
    PongMessage,
]


def make_state_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    pending = state.get("pending", {})
    flags = state.get("flags", {})
    return {
        "missing_fields": pending.get("missing_fields", []),
        "ambiguous_fields": pending.get("ambiguous_fields", []),
        "ready_for_confirmation": flags.get("ready_for_confirmation", False),
    }
