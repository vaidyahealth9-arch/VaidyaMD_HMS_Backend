"""
VaidyaMD HMS — CRM Whisper Transcription Service
Asynchronous, self-hosted Speech-to-Text using Faster-Whisper (CTranslate2).
Designed for background non-blocking execution.
"""

import os
import asyncio
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.modules.crm.model import CallLog

logger = logging.getLogger(__name__)

# Global model cache to avoid reloading weights per audio file
_whisper_model_instance = None
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")


def get_whisper_model():
    """Lazily loads Faster-Whisper model into memory once."""
    global _whisper_model_instance
    if _whisper_model_instance is None:
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model '{WHISPER_MODEL_SIZE}' on {WHISPER_DEVICE} ({WHISPER_COMPUTE_TYPE})...")
            _whisper_model_instance = WhisperModel(
                WHISPER_MODEL_SIZE,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE
            )
            logger.info("Faster-whisper model successfully loaded.")
        except ImportError:
            logger.warning("faster-whisper package not installed. Background STT will run in fallback simulation mode.")
            _whisper_model_instance = False
        except Exception as e:
            logger.error(f"Failed to initialize faster-whisper: {e}")
            _whisper_model_instance = False
    return _whisper_model_instance


async def process_call_audio_transcription(call_log_id: UUID, audio_file_path: str):
    """
    Background worker function:
    1. Checks if audio exists
    2. Runs Faster-Whisper speech-to-text
    3. Saves final transcript back to the DB CallLog record
    """
    logger.info(f"Starting background speech-to-text for call {call_log_id} (File: {audio_file_path})")
    
    if not os.path.exists(audio_file_path):
        logger.error(f"Audio file not found at path: {audio_file_path}")
        async with AsyncSessionLocal() as session:
            stmt = select(CallLog).where(CallLog.id == call_log_id)
            result = await session.execute(stmt)
            call_log = result.scalar_one_or_none()
            if call_log:
                call_log.transcript_status = "failed"
                await session.commit()
        return

    # Update status to processing
    async with AsyncSessionLocal() as session:
        stmt = select(CallLog).where(CallLog.id == call_log_id)
        result = await session.execute(stmt)
        call_log = result.scalar_one_or_none()
        if call_log:
            call_log.transcript_status = "processing"
            await session.commit()

    model = get_whisper_model()
    transcript_text = ""
    status_result = "completed"

    if model:
        try:
            # Run faster-whisper transcription off-thread to avoid blocking event loop
            def _do_transcribe():
                segments, info = model.transcribe(audio_file_path, beam_size=5)
                text = " ".join([seg.text.strip() for seg in segments])
                return text, info.language, info.language_probability

            transcript_text, detected_lang, prob = await asyncio.to_thread(_do_transcribe)
            logger.info(f"Transcription finished for {call_log_id}. Detected language: {detected_lang} ({prob:.2f})")
        except Exception as e:
            logger.error(f"Error during audio transcription for call {call_log_id}: {e}")
            status_result = "failed"
            transcript_text = f"[Transcription failed: {str(e)}]"
    else:
        # Fallback notice when faster-whisper library is not yet installed in container
        transcript_text = "[Notice: faster-whisper model awaiting installation or device init. Recording saved.]"
        status_result = "skipped"

    # Persist transcript in database
    async with AsyncSessionLocal() as session:
        stmt = select(CallLog).where(CallLog.id == call_log_id)
        result = await session.execute(stmt)
        call_log = result.scalar_one_or_none()
        if call_log:
            call_log.transcript_text = transcript_text
            call_log.transcript_status = status_result
            call_log.whisper_model_used = f"faster-whisper-{WHISPER_MODEL_SIZE}" if model else "none"
            await session.commit()
            logger.info(f"Transcript updated for call {call_log_id}.")
