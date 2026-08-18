import os
from collections import defaultdict, deque

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================
# ENVIRONMENT
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# BRE AI PERSONALITY
# ============================================================

SYSTEM_PROMPT = """
Lu adalah Bre AI, AI co-pilot untuk project Kallani.

Gaya bicara:
- Bahasa Indonesia santai dan natural.
- Gunakan "bre" jika cocok.
- Boleh menggunakan wkwk dan emoji seperlunya.
- Jangan terlalu formal.
- Jawab langsung ke inti.
- Kalau sedang membahas Kallani, pahami bahwa Kallani adalah
  project yang sedang dibangun user.
- Jangan mengarang data.
- Kalau tidak yakin, katakan dengan jujur.
- Bedakan fakta, asumsi, proyeksi, dan opini.
- Kalau pertanyaan merupakan lanjutan pembahasan sebelumnya,
  jangan mengulang dari nol. Lanjutkan topiknya.
"""


# ============================================================
# CONVERSATION MEMORY
# ============================================================

MAX_MEMORY_MESSAGES = 20

conversation_memory = defaultdict(
    lambda: deque(maxlen=MAX_MEMORY_MESSAGES)
)


# ============================================================
# SEND LONG MESSAGE
# ============================================================

async def send_long_message(message, text, max_length=4000):
    if not text:
        return

    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        await message.reply_text(chunk)


# ============================================================
# BUILD CONVERSATION INPUT
# ============================================================

def build_conversation_input(chat_id, current_question):

    history = conversation_memory[chat_id]

    conversation_text = ""

    if history:

        conversation_text += """
Berikut adalah percakapan sebelumnya.
Gunakan percakapan ini sebagai konteks untuk memahami
pertanyaan terbaru.

"""

        for item in history:

            if item["role"] == "user":
                conversation_text += (
                    f"USER:\n{item['content']}\n\n"
                )

            elif item["role"] == "assistant":
                conversation_text += (
                    f"BRE AI:\n{item['content']}\n\n"
                )

    conversation_text += (
        f"PERTANYAAN TERBARU USER:\n{current_question}"
    )

    return conversation_text


# ============================================================
# CLEAR MEMORY
# ============================================================

async def clear_memory(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    conversation_memory[chat_id].clear()

    await update.message.reply_text(
        "Memory percakapan grup ini sudah gue hapus bre 🧠🧹"
    )


# ============================================================
# HANDLE MESSAGE
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = update.message.text.strip()

    if not text:
        return

    # ========================================================
    # BOT IDENTITY
    # ========================================================

    bot_username = context.bot.username
    bot_id = context.bot.id

    # ========================================================
    # TRIGGER 1: MENTION
    # ========================================================

    is_mentioned = False

    if bot_username:
        is_mentioned = (
            f"@{bot_username.lower()}" in text.lower()
        )

    # ========================================================
    # TRIGGER 2: REPLY TO BRE AI
    # ========================================================

    is_reply_to_bot = False
    replied_message = None

    if update.message.reply_to_message:

        replied_message = update.message.reply_to_message

        if replied_message.from_user:

            # Cara pertama: cek ID bot
            if replied_message.from_user.id == bot_id:
                is_reply_to_bot = True

            # Cara kedua: cek username bot
            if (
                bot_username
                and replied_message.from_user.username
                and replied_message.from_user.username.lower()
                == bot_username.lower()
            ):
                is_reply_to_bot = True

    # ========================================================
    # DEBUG LOG
    # ========================================================

    print(
        f"Message received | "
        f"mentioned={is_mentioned} | "
        f"reply_to_bot={is_reply_to_bot}"
    )

    # ========================================================
    # IGNORE NORMAL CHAT
    # ========================================================

    if not is_mentioned and not is_reply_to_bot:

        print("⏭️ Ignored normal chat")

        return

    # ========================================================
    # REMOVE BOT MENTION
    # ========================================================

    user_text = text

    if bot_username:

        user_text = user_text.replace(
            f"@{bot_username}",
            ""
        )

        user_text = user_text.replace(
            f"@{bot_username.lower()}",
            ""
        )

        user_text = user_text.strip()

    # ========================================================
    # REPLY CONTEXT
    # ========================================================

    if is_reply_to_bot and replied_message:

        replied_text = replied_message.text or ""

        if replied_text:

            user_text = f"""
PESAN BRE AI YANG SEDANG DIBALAS:

{replied_text}

PESAN LANJUTAN USER:

{user_text}
""".strip()

    # ========================================================
    # EMPTY MESSAGE
    # ========================================================

    if not user_text.strip():

        await update.message.reply_text(
            "Yo bre 😎 Ada yang mau dibahas?"
        )

        return

    # ========================================================
    # CHAT ID
    # ========================================================

    chat_id = update.effective_chat.id

    # ========================================================
    # BUILD MEMORY CONTEXT
    # ========================================================

    input_text = build_conversation_input(
        chat_id,
        user_text
    )

    # ========================================================
    # OPENAI
    # ========================================================

    try:

        print("🧠 Sending request to OpenAI...")

        response = client.responses.create(
            model="gpt-5.6",
            instructions=SYSTEM_PROMPT,
            input=input_text,
        )

        answer = response.output_text.strip()

        if not answer:

            answer = (
                "Bre, gue nggak mendapatkan jawaban "
                "dari model kali ini 😅"
            )

        # ====================================================
        # SAVE USER MESSAGE
        # ====================================================

        conversation_memory[chat_id].append({
            "role": "user",
            "content": user_text
        })

        # ====================================================
        # SAVE AI ANSWER
        # ====================================================

        conversation_memory[chat_id].append({
            "role": "assistant",
            "content": answer
        })

        print("✅ OpenAI response received")

        # ====================================================
        # SEND RESPONSE
        # ====================================================

        await send_long_message(
            update.message,
            answer
        )

    except Exception as e:

        print("ERROR:", repr(e))

        await update.message.reply_text(
            "Waduh bre, otak gue lagi error bentar 😂"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # /clear
    app.add_handler(
        CommandHandler(
            "clear",
            clear_memory
        )
    )

    # Message handler
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("🔥 Bre AI is running...")
    print("🧠 Conversation memory: ON")
    print("💬 Mention + Reply mode: ON")

    app.run_polling()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
