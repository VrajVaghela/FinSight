# app/api/voice.py
import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, Response
from app.core.voice_handler import VoiceHandler
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service, verify_ws_token

router = APIRouter()

@router.websocket("/ws/voice")
async def voice_websocket(
    ws: WebSocket,
    project_id: str = Query(...),
    token: str = Query(...),
    chat_svc: ChatService = Depends(get_chat_service)
):
    user_id = await verify_ws_token(token)
    if not user_id:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()
    voice = VoiceHandler()
    audio_buffer = bytearray()
    
    try:
        project_uuid = uuid.UUID(project_id)
        while True:
            data = await ws.receive()
            
            if "bytes" in data:
                audio_buffer.extend(data["bytes"])
                if voice.detect_silence(audio_buffer):
                    # Transcribe
                    text = await voice.transcribe(bytes(audio_buffer))
                    audio_buffer.clear()
                    await ws.send_json({"type": "transcript", "text": text})
                    
                    # Process through chat pipeline
                    final_response_text = ""
                    async for event in chat_svc.process_chat(
                        project_id=project_uuid,
                        message=text,
                        user_id=user_id,
                        voice=True
                    ):
                        # Send text events as standard SSE strings to websocket client
                        await ws.send_text(event)
                        
                        # Accumulate text from 'chunk' events for TTS synthesis
                        if event.startswith("data: "):
                            try:
                                payload = json.loads(event.replace("data: ", "", 1))
                                if "delta" in payload:
                                    final_response_text += payload["delta"]
                            except json.JSONDecodeError:
                                pass
                    
                    # Generate TTS audio once full response is gathered
                    if final_response_text.strip():
                        tts_audio = await voice.synthesize(final_response_text)
                        await ws.send_bytes(tts_audio)
                    
            elif "text" in data:
                msg = json.loads(data["text"])
                if msg.get("interrupted"):
                    # Barge-in logic (Task 5.3)
                    audio_buffer.clear()
                    await ws.send_json({"type": "status", "message": "Interrupted"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS Error: {e}")
        await ws.close()

@router.post("/api/tts")
async def text_to_speech(
    text: str,
    voice: VoiceHandler = Depends(lambda: VoiceHandler())
):
    audio_content = await voice.synthesize(text)
    return Response(content=audio_content, media_type="audio/wav")
