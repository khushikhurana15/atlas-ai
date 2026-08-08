"""
This file defines what the bot does when a user sends
something on Telegram - text, voice, images, or PDFs all end up
going through the same core logic (process_message).
"""

import asyncio
import re
from telegram import Update
from telegram.ext import ContextTypes
from app.ai.orchestrator import get_ai_reply
from app.ai.transcription import transcribe_audio
from app.ai.vision import analyze_image
from app.tools.pdf_tool import extract_pdf_text
from app.db.database import get_db_session
from app.db.models import User, Conversation

REPLY_TIMEOUT_SECONDS = 50
DOWNLOAD_TIMEOUT_SECONDS = 25


def _fix_markdown_for_telegram(text: str) -> str:
    """
    Two things the model does that break Telegram's legacy Markdown
    parser, fixed here regardless of what the prompt says:

    1. **bold** instead of *bold* - Telegram's legacy mode only
       understands single-asterisk bold.
    2. "* " as a bullet marker at the start of a line - this adds an
       extra, unpaired asterisk. Combined with any **bold** elsewhere
       in the same message, the total asterisk count becomes odd,
       which makes Telegram reject the WHOLE message's Markdown
       (BadRequest: can't find end of entity) - not just fail to
       render, but throw, which was silently falling back to sending
       the raw unsanitized text instead.
    """
    # Bullet markers first (order matters - do this before touching **).
    text = re.sub(r"(?m)^\*(?=\s)", "-", text)
    # **bold** -> *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    return text


def get_or_create_user(db, telegram_id: str) -> User:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user is None:
        user = User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db_session()
    get_or_create_user(db, str(update.effective_user.id))
    db.close()

    welcome_message = (
        "Hey! I'm Atlas, your financial assistant. 📊\n\n"
        "Talk to me with text, voice, images, or PDFs - like 'tell me about "
        "Apple's stock' or upload an annual report. I'll remember our past "
        "conversations too. Feel free to reply in English, Hindi, or "
        "Hinglish - I'll follow along.\n\n"
        "By the way - what best describes you (investor, analyst, founder, "
        "student...) and which stocks/sectors do you follow? That'll help "
        "me give you more relevant updates. Or just jump straight into a "
        "question, no pressure!"
    )
    await update.message.reply_text(welcome_message)


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str):
    db = get_db_session()
    telegram_id = str(update.effective_user.id)

    try:
        user = get_or_create_user(db, telegram_id)

        db.add(Conversation(user_id=user.id, role="user", content=user_message))
        db.commit()

        await update.message.chat.send_action(action="typing")

        recent_messages = (
            db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.id.desc())
            .limit(10)
            .all()
        )
        recent_messages.reverse()
        conversation_history = [{"role": m.role, "content": m.content} for m in recent_messages]
        user_profile = {"role": user.role, "interests": user.interests}

        try:
            reply, profile_updates = await asyncio.wait_for(
                asyncio.to_thread(get_ai_reply, conversation_history, user_profile),
                timeout=REPLY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            reply, profile_updates = ("Sorry, that's taking too long right now. Please try again.", {})
        except Exception as e:
            print(f"Unexpected error in get_ai_reply: {e}")
            reply, profile_updates = ("Sorry, something went wrong. Please try again.", {})

        if profile_updates:
            if "role" in profile_updates:
                user.role = profile_updates["role"]
            if "interests" in profile_updates:
                user.interests = profile_updates["interests"]
            db.commit()

        db.add(Conversation(user_id=user.id, role="assistant", content=reply))
        db.commit()

        try:
            safe_reply = _fix_markdown_for_telegram(reply)
            await update.message.reply_text(safe_reply, parse_mode="Markdown")
        except Exception:
            # Markdown parsing failed for some other reason - send as
            # plain text, but strip asterisks entirely so we never show
            # raw ** or * characters to the user.
            plain_reply = safe_reply.replace("*", "")
            await update.message.reply_text(plain_reply)
    finally:
        db.close()


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_message(update, context, update.message.text)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")

    try:
        voice = update.message.voice
        tg_file = await asyncio.wait_for(
            context.bot.get_file(voice.file_id), timeout=DOWNLOAD_TIMEOUT_SECONDS
        )
        audio_bytes = bytes(await asyncio.wait_for(
            tg_file.download_as_bytearray(), timeout=DOWNLOAD_TIMEOUT_SECONDS
        ))

        transcribed_text = await asyncio.wait_for(
            asyncio.to_thread(transcribe_audio, audio_bytes), timeout=30
        )
    except Exception as e:
        print(f"Voice transcription failed: {e}")
        await update.message.reply_text(
            "Sorry, voice message samajh nahi paya. Text mein try kar sakte ho?"
        )
        return

    await process_message(update, context, transcribed_text)


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")

    try:
        photo = update.message.photo[-1]
        tg_file = await asyncio.wait_for(
            context.bot.get_file(photo.file_id), timeout=DOWNLOAD_TIMEOUT_SECONDS
        )
        image_bytes = bytes(await asyncio.wait_for(
            tg_file.download_as_bytearray(), timeout=DOWNLOAD_TIMEOUT_SECONDS
        ))
        caption = update.message.caption or ""

        description = await asyncio.wait_for(
            asyncio.to_thread(analyze_image, image_bytes, caption), timeout=30
        )
    except Exception as e:
        print(f"Image analysis failed: {e}")
        await update.message.reply_text("Sorry, image samajh nahi paya. Try again?")
        return

    await process_message(update, context, f"[User sent an image] {description}")


async def handle_document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document or document.mime_type != "application/pdf":
        await update.message.reply_text(
            "Abhi sirf PDF files support karta hoon. Kya iske alawa kuch aur bhejna chahte ho?"
        )
        return

    await update.message.chat.send_action(action="typing")

    try:
        tg_file = await asyncio.wait_for(
            context.bot.get_file(document.file_id), timeout=DOWNLOAD_TIMEOUT_SECONDS
        )
        file_bytes = bytes(await asyncio.wait_for(
            tg_file.download_as_bytearray(), timeout=DOWNLOAD_TIMEOUT_SECONDS
        ))

        extracted_text = await asyncio.wait_for(
            asyncio.to_thread(extract_pdf_text, file_bytes), timeout=30
        )
    except Exception as e:
        print(f"PDF extraction failed: {e}")
        await update.message.reply_text("Sorry, is PDF ko padh nahi paya. Try again?")
        return

    # If almost nothing was extracted (likely a scanned PDF with no
    # text layer), don't send it to the AI at all - that's exactly
    # the situation that caused it to hallucinate using old context
    # instead. Tell the user honestly instead.
    if len(extracted_text) < 30:
        await update.message.reply_text(
            "Is PDF se readable text extract nahi ho paya - shayad ye scanned "
            "image hai bina text layer ke. Kya iska text-based version hai?"
        )
        return

    caption = update.message.caption or "Give me a brief summary of this document."
    combined_message = (
        f"[User uploaded a PDF titled '{document.file_name}'. Their request: "
        f"{caption}. IMPORTANT: Base your answer ONLY on the document text "
        f"below - do not use any other document or image discussed earlier "
        f"in this conversation, even if the topic seems similar.]\n\n"
        f"Document content:\n{extracted_text}"
    )

    await process_message(update, context, combined_message)