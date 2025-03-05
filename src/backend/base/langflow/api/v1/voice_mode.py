import asyncio
import base64
import json
import os

# For sync queue and thread
import queue
import threading
import traceback
from datetime import datetime
from uuid import UUID, uuid4

import numpy as np
import webrtcvad
import websockets
from cryptography.fernet import InvalidToken
from elevenlabs.client import ElevenLabs
from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import select
from starlette.websockets import WebSocket, WebSocketDisconnect

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.chat import build_flow
from langflow.api.v1.schemas import InputValueRequest
from langflow.logging import logger
from langflow.services.auth.utils import get_current_user_by_jwt
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_variable_service, session_scope
from langflow.utils.voice_utils import (
    BYTES_PER_24K_FRAME,
    VAD_SAMPLE_RATE_16K,
    resample_24k_to_16k,
)

router = APIRouter(prefix="/voice", tags=["Voice"])

SILENCE_THRESHOLD = 0.5
PREFIX_PADDING_MS = 300
SILENCE_DURATION_MS = 500
SESSION_INSTRUCTIONS = (
    "Converse with the user to assist with their question. "
    "When appropriate, call the execute_flow function to assist with the user's question "
    "as the input parameter and use that to craft your responses. "
    "Always tell the user before you call a function to assist with their question. "
    "And let them know what it does."
)

use_elevenlabs = False
elevenlabs_voice = "JBFqnCBsd6RMkjVDRZzb"
elevenlabs_model = "eleven_multilingual_v2"
elevenlabs_client = None
elevenlabs_key = None

barge_in_enabled = False


async def safe_build_flow(*args, **kwargs):
    # Offload the potentially blocking build_flow call
    return await asyncio.to_thread(build_flow, *args, **kwargs)


async def get_flow_desc_from_db(flow_id: str) -> Flow:
    """Get flow from database."""
    async with session_scope() as session:
        stmt = select(Flow).where(Flow.id == UUID(flow_id))
        result = await session.exec(stmt)
        flow = result.scalar_one_or_none()
        if not flow:
            error_message = f"Flow with id {flow_id} not found"
            raise ValueError(error_message)
        return flow.description


def pcm16_to_float_array(pcm_data):
    values = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
    normalized = values / 32768.0  # Normalize to -1.0 to 1.0
    return normalized


async def text_chunker_with_timeout(chunks, timeout=0.3):
    """Async generator that takes an async iterable (of text pieces),
    accumulates them and yields chunks without breaking sentences.
    If no new text is received within 'timeout' seconds and there is
    buffered text, it flushes that text.
    """
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""
    ait = chunks.__aiter__()
    while True:
        try:
            text = await asyncio.wait_for(ait.__anext__(), timeout=timeout)
        except asyncio.TimeoutError:
            if buffer:
                yield buffer + " "
                buffer = ""
            continue
        except StopAsyncIteration:
            break
        if text is None:
            if buffer:
                yield buffer + " "
            break
        if buffer and buffer[-1] in splitters:
            yield buffer + " "
            buffer = text
        elif text and text[0] in splitters:
            yield buffer + text[0] + " "
            buffer = text[1:]
        else:
            buffer += text
    if buffer:
        yield buffer + " "


async def queue_generator(queue: asyncio.Queue):
    """Async generator that yields items from a queue."""
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


async def handle_function_call(
    websocket: WebSocket,
    openai_ws: websockets.WebSocketClientProtocol,
    function_call: dict,
    function_call_args: str,
    flow_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,
    session: DbSession,
):
    try:
        conversation_id = str(uuid4())
        args = json.loads(function_call_args) if function_call_args else {}
        input_request = InputValueRequest(
            input_value=args.get("input"), components=[], type="chat", session=conversation_id
        )
        response = await build_flow(
            flow_id=UUID(flow_id),
            inputs=input_request,
            background_tasks=background_tasks,
            current_user=current_user,
        )
        result = ""
        async for line in response.body_iterator:
            if not line:
                continue
            event_data = json.loads(line)
            await websocket.send_json({"type": "flow.build.progress", "data": event_data})
            if event_data.get("event") == "end_vertex":
                text_part = (
                    event_data.get("data", {})
                    .get("build_data", "")
                    .get("data", {})
                    .get("results", {})
                    .get("message", {})
                    .get("text", "")
                )
                result += text_part
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": str(result),
            },
        }
        await openai_ws.send(json.dumps(function_output))
        await openai_ws.send(json.dumps({"type": "response.create"}))
    except Exception as e:
        logger.error(f"Error executing flow: {e!s}")
        function_output = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": function_call.get("call_id"),
                "output": f"Error executing flow: {e!s}",
            },
        }
        await openai_ws.send(json.dumps(function_output))


# --- Synchronous text chunker using a standard queue ---
def sync_text_chunker(sync_queue_obj: queue.Queue, timeout: float = 0.3):
    """Synchronous generator that reads text pieces from a sync queue,
    accumulates them and yields complete chunks.
    """
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""
    while True:
        try:
            text = sync_queue_obj.get(timeout=timeout)
        except queue.Empty:
            if buffer:
                yield buffer + " "
                buffer = ""
            continue
        if text is None:
            if buffer:
                yield buffer + " "
            break
        if buffer and buffer[-1] in splitters:
            yield buffer + " "
            buffer = text
        elif text and text[0] in splitters:
            yield buffer + text[0] + " "
            buffer = text[1:]
        else:
            buffer += text
    if buffer:
        yield buffer + " "


@router.websocket("/ws/flow_as_tool/{flow_id}")
async def flow_as_tool_websocket(
    client_websocket: WebSocket,
    flow_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
):
    """WebSocket endpoint registering the flow as a tool for real-time interaction."""
    current_user = await get_current_user_by_jwt(client_websocket.cookies.get("access_token_lf"), session)
    await client_websocket.accept()

    variable_service = get_variable_service()
    try:
        openai_key = await variable_service.get_variable(
            user_id=current_user.id, name="OPENAI_API_KEY", field="openai_api_key", session=session
        )
    except (InvalidToken, ValueError):
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key == "dummy":
            await client_websocket.send_json(
                {
                    "type": "error",
                    "code": "api_key_missing",
                    "key_name": "OPENAI_API_KEY",
                    "message": "OpenAI API key not found. Please set your API key as an env var or a global variable.",
                }
            )
            return
    except Exception as e:
        logger.error("exception")
        print(e)
        print(traceback.format_exc())

    try:
        flow_description = await get_flow_desc_from_db(flow_id)
        flow_tool = {
            "name": "execute_flow",
            "type": "function",
            "description": flow_description or "Execute the flow with the given input",
            "parameters": {
                "type": "object",
                "properties": {"input": {"type": "string", "description": "The input to send to the flow"}},
                "required": ["input"],
            },
        }
    except Exception as e:
        await client_websocket.send_json({"error": f"Failed to load flow: {e!s}"})
        logger.error(e)
        return

    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    async with websockets.connect(url, extra_headers=headers) as openai_ws:
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": SESSION_INSTRUCTIONS,
                "voice": "echo",
                "temperature": 0.8,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": SILENCE_THRESHOLD,
                    "prefix_padding_ms": PREFIX_PADDING_MS,
                    "silence_duration_ms": SILENCE_DURATION_MS,
                },
                "input_audio_transcription": {"model": "whisper-1"},
                "tools": [flow_tool],
                "tool_choice": "auto",
            },
        }
        await openai_ws.send(json.dumps(session_update))

        # Setup for VAD processing.
        vad_queue = asyncio.Queue()
        vad_audio_buffer = bytearray()
        bot_speaking_flag = [False]
        vad = webrtcvad.Vad(mode=3)

        async def process_vad_audio() -> None:
            nonlocal vad_audio_buffer
            last_speech_time = datetime.now()
            while True:
                base64_data = await vad_queue.get()
                raw_chunk_24k = base64.b64decode(base64_data)
                vad_audio_buffer.extend(raw_chunk_24k)
                has_speech = False
                while len(vad_audio_buffer) >= BYTES_PER_24K_FRAME:
                    frame_24k = vad_audio_buffer[:BYTES_PER_24K_FRAME]
                    del vad_audio_buffer[:BYTES_PER_24K_FRAME]
                    try:
                        frame_16k = resample_24k_to_16k(frame_24k)
                        is_speech = vad.is_speech(frame_16k, VAD_SAMPLE_RATE_16K)
                        if is_speech:
                            has_speech = True
                            logger.trace("!", end="")
                            if bot_speaking_flag[0]:
                                print("\nBarge-in detected!", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                await openai_ws.send(json.dumps({"type": "response.cancel"}))
                                print("bot speaking false")
                                bot_speaking_flag[0] = False
                    except Exception as e:
                        logger.error(f"[ERROR] VAD processing failed: {e}")
                        continue
                if has_speech:
                    last_speech_time = datetime.now()
                    logger.trace(".", end="")
                else:
                    time_since_speech = (datetime.now() - last_speech_time).total_seconds()
                    if time_since_speech >= 1.0:
                        logger.trace("_", end="")

        shared_state = {"last_event_type": None, "event_count": 0}

        def log_event(event_type: str, direction: str) -> None:
            if event_type != shared_state["last_event_type"]:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n  {timestamp} --  {direction} {event_type} ", end="", flush=True)
                shared_state["last_event_type"] = event_type
                shared_state["event_count"] = 0
            shared_state["event_count"] += 1

        # --- Spawn a text delta queue and task for TTS ---
        text_delta_queue = asyncio.Queue()
        text_delta_task = None  # Will hold our background task.

        async def process_text_deltas(async_q: asyncio.Queue):
            """Transfer text deltas from the async queue to a synchronous queue,
            then run the ElevenLabs TTS call (which expects a sync generator) in a separate thread.
            """
            sync_q = queue.Queue()

            async def transfer_text_deltas():
                while True:
                    item = await async_q.get()
                    sync_q.put(item)
                    if item is None:
                        break

            # Schedule the transfer task in the main event loop.
            asyncio.create_task(transfer_text_deltas())

            # Create the synchronous generator from the sync queue.
            sync_gen = sync_text_chunker(sync_q, timeout=0.3)
            elevenlabs_client = await get_or_create_elevenlabs_client()
            if elevenlabs_client is None:
                return
            # Capture the current event loop to schedule send operations.
            main_loop = asyncio.get_running_loop()

            def tts_thread():
                # Create a new event loop for this thread.
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)

                async def run_tts():
                    try:
                        audio_stream = elevenlabs_client.generate(
                            voice=elevenlabs_voice,
                            output_format="pcm_24000",
                            text=sync_gen,  # synchronous generator expected by ElevenLabs
                            model=elevenlabs_model,
                            voice_settings=None,
                            stream=True,
                        )
                        for chunk in audio_stream:
                            base64_audio = base64.b64encode(chunk).decode("utf-8")
                            # Schedule sending the audio chunk in the main event loop.
                            asyncio.run_coroutine_threadsafe(
                                client_websocket.send_json({"type": "response.audio.delta", "delta": base64_audio}),
                                main_loop,
                            ).result()
                    except Exception as e:
                        print(e)
                        print(traceback.format_exc())

                new_loop.run_until_complete(run_tts())
                new_loop.close()

            threading.Thread(target=tts_thread, daemon=True).start()

        async def forward_to_openai() -> None:
            global use_elevenlabs, elevenlabs_voice
            try:
                while True:
                    message_text = await client_websocket.receive_text()
                    msg = json.loads(message_text)
                    event_type = msg.get("type")
                    log_event(event_type, "↑")
                    if msg.get("type") == "input_audio_buffer.append":
                        logger.trace(f"buffer_id {msg.get('buffer_id', '')}")
                        base64_data = msg.get("audio", "")
                        if not base64_data:
                            continue
                        await openai_ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64_data}))
                        await vad_queue.put(base64_data)
                    if msg.get("type") == "elevenlabs.config":
                        logger.info(f"elevenlabs.config {msg}")
                        use_elevenlabs = msg["enabled"]
                        elevenlabs_voice = msg["voice_id"]
                        modalities = ["text", "audio"]
                        if use_elevenlabs:
                            modalities = ["text"]
                        session_update = {
                            "type": "session.update",
                            "session": {
                                "modalities": ["text"],
                                "instructions": SESSION_INSTRUCTIONS,
                                "voice": "echo",
                                "temperature": 0.8,
                                "input_audio_format": "pcm16",
                                "output_audio_format": "pcm16",
                                "turn_detection": {
                                    "type": "server_vad",
                                    "threshold": SILENCE_THRESHOLD,
                                    "prefix_padding_ms": PREFIX_PADDING_MS,
                                    "silence_duration_ms": SILENCE_DURATION_MS,
                                },
                                "input_audio_transcription": {"model": "whisper-1"},
                                "tools": [flow_tool],
                                "tool_choice": "auto",
                            },
                        }
                        await openai_ws.send(json.dumps(session_update))
                    else:
                        await openai_ws.send(message_text)
            except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
                pass

        async def forward_to_client() -> None:
            global elevenlabs_client, elevenlabs_key
            nonlocal bot_speaking_flag, text_delta_queue, text_delta_task
            function_call = None
            function_call_args = ""
            try:
                while True:
                    data = await openai_ws.recv()
                    event = json.loads(data)
                    event_type = event.get("type")

                    # forward all openai events to the client
                    await client_websocket.send_text(data)

                    if event_type == "response.text.delta":
                        delta = event.get("delta", "")
                        await text_delta_queue.put(delta)
                        if text_delta_task is None:
                            text_delta_task = asyncio.create_task(process_text_deltas(text_delta_queue))
                    elif event_type == "response.text.done":
                        await text_delta_queue.put(None)
                        text_delta_task = None
                        print(f"\n      bot response: {event.get('text')}")
                    elif event_type == "response.output_item.added":
                        print("Bot speaking = True")
                        bot_speaking_flag[0] = True
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            function_call = item
                            function_call_args = ""
                    elif event_type == "response.output_item.done":
                        print("Bot speaking = False")
                        bot_speaking_flag[0] = False
                    elif event_type == "response.function_call_arguments.delta":
                        function_call_args += event.get("delta", "")
                    elif event_type == "response.function_call_arguments.done":
                        if function_call:
                            asyncio.create_task(
                                handle_function_call(
                                    client_websocket,
                                    openai_ws,
                                    function_call,
                                    function_call_args,
                                    flow_id,
                                    background_tasks,
                                    current_user,
                                    session,
                                )
                            )
                            function_call = None
                            function_call_args = ""
                    elif event_type == "response.audio.delta":
                        # Audio deltas from OpenAI are not forwarded if ElevenLabs is used.
                        audio_delta = event.get("delta", "")
                    elif event_type == "error":
                        print(event)
                    else:
                        await client_websocket.send_text(data)
                    log_event(event_type, "↓")
            except (WebSocketDisconnect, websockets.ConnectionClosedOK, websockets.ConnectionClosedError) as e:
                print(f"Websocket exception: {e}")

        async def elevenlabs_generate_and_send_audio(elevenlabs_client, text):
            loop = asyncio.get_running_loop()
            try:
                # Offload the blocking TTS generation to a background thread.
                await asyncio.to_thread(_blocking_tts, elevenlabs_client, text, client_websocket, loop)
            except Exception as e:
                print(e)
                print(traceback.format_exc())

        def _blocking_tts(elevenlabs_client, text, client_websocket, loop):
            try:
                audio_stream = elevenlabs_client.generate(
                    voice=elevenlabs_voice,
                    output_format="pcm_24000",
                    text=text,
                    model=elevenlabs_model,
                    voice_settings=None,
                    stream=True,
                )
                for chunk in audio_stream:
                    base64_audio = base64.b64encode(chunk).decode("utf-8")
                    # Use asyncio.run_coroutine_threadsafe to send the audio chunk back to the client.
                    future = asyncio.run_coroutine_threadsafe(
                        client_websocket.send_json({"type": "response.audio.delta", "delta": base64_audio}), loop
                    )
                    # Optionally, wait for the send to complete.
                    future.result()
            except Exception as e:
                print(e)
                print(traceback.format_exc())

        async def get_or_create_elevenlabs_client():
            global elevenlabs_key, elevenlabs_client
            if elevenlabs_client is None:
                if elevenlabs_key is None:
                    try:
                        elevenlabs_key = await variable_service.get_variable(
                            user_id=current_user.id,
                            name="ELEVENLABS_API_KEY",
                            field="elevenlabs_api_key",
                            session=session,
                        )
                    except (InvalidToken, ValueError):
                        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
                        if not elevenlabs_key:
                            await client_websocket.send_json(
                                {
                                    "type": "error",
                                    "code": "api_key_missing",
                                    "key_name": "ELEVENLABS_API_KEY",
                                    "message": "ELEVENLABS API key not found. Please set your API key as an env var or a global variable.",
                                }
                            )
                            return None
                    except Exception as e:
                        logger.error("exception")
                        print(e)
                        print(traceback.format_exc())
                elevenlabs_client = ElevenLabs(api_key=elevenlabs_key)
            return elevenlabs_client

        if barge_in_enabled:
            asyncio.create_task(process_vad_audio())

        await asyncio.gather(
            forward_to_openai(),
            forward_to_client(),
        )


@router.websocket("/ws/{flow_id}")
async def flow_audio_websocket(
    client_websocket: WebSocket,
    flow_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
):
    """WebSocket endpoint for streaming events to flow components."""
    current_user = await get_current_user_by_jwt(client_websocket.cookies.get("access_token_lf"), session)
    await client_websocket.accept()
    websocket_session_id = str(uuid4())
    try:
        stmt = select(Flow).where(Flow.id == UUID(flow_id))
        result = await session.exec(stmt)
        flow = result.scalar_one_or_none()
        if not flow:
            error_message = f"Flow with id {flow_id} not found"
            raise ValueError(error_message)
        chat_input_id = None
        for node in flow.data.get("nodes", []):
            if node.get("data", {}).get("type") == "ChatInput":
                chat_input_id = node.get("id")
                logger.debug(f"Found ChatInput component with ID: {chat_input_id}")
                break
        if not chat_input_id:
            await client_websocket.close(code=4004, reason="No ChatInput component found in flow")
            return
        event_queue = asyncio.Queue()

        async def process_events():
            last_result_time = datetime.now()
            while True:
                try:
                    event = await event_queue.get()
                    if event is None:
                        break
                    input_request = InputValueRequest(
                        input_value=json.dumps(event),
                        components=[chat_input_id],
                        type="any",
                        session=websocket_session_id,
                    )
                    try:
                        response = await safe_build_flow(
                            flow_id=UUID(flow_id),
                            inputs=input_request,
                            background_tasks=background_tasks,
                            current_user=current_user,
                        )
                        result = ""
                        async for line in response.body_iterator:
                            if not line:
                                continue
                            event_data = json.loads(line)
                            if event_data.get("event") == "end_vertex":
                                text_part = (
                                    event_data.get("data", {})
                                    .get("build_data", "")
                                    .get("data", {})
                                    .get("results", {})
                                    .get("message", {})
                                    .get("transcript", {})
                                    .get("raw", {})
                                    .get("text", "")
                                )
                                result += text_part
                        print(f"result {result}")
                        current_time = datetime.now()
                        duration = (current_time - last_result_time).total_seconds()
                        print(f"Time since last result: {duration:.2f}s")
                        print(f"queue length {event_queue.qsize()}")
                        last_result_time = current_time
                    except Exception as e:
                        logger.error(f"Error processing event through flow: {e!s}")
                        try:
                            await client_websocket.send_json(
                                {"type": "error", "message": f"Flow processing error: {e!s}"}
                            )
                        except WebSocketDisconnect:
                            break
                except Exception as e:
                    logger.error(f"Error input request: {e!s}")
                finally:
                    event_queue.task_done()

        process_task = asyncio.create_task(process_events())
        try:
            while True:
                message = await client_websocket.receive_json()
                event_type = message.get("type")
                if event_type == "end_stream":
                    logger.debug("Client requested end of stream")
                    break
                logger.trace(f"Received event type: {event_type}")
                await event_queue.put(message)
        except WebSocketDisconnect:
            logger.debug("Client disconnected")
        except Exception as e:
            logger.error(f"Error receiving message: {e!s}")
            try:
                await client_websocket.send_json({"type": "error", "message": str(e)})
            except WebSocketDisconnect:
                pass
    except Exception as e:
        logger.error(f"WebSocket error: {e!s}")
        logger.error(traceback.format_exc())
    finally:
        if "process_task" in locals():
            await event_queue.put(None)
            await process_task
        try:
            await client_websocket.close()
        except:
            pass
        logger.debug(f"WebSocket connection closed for flow {flow_id}")
