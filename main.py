import os
from collections import defaultdict, deque

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
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
- Kalau user sedang membahas Kallani, pahami bahwa Kallani adalah
  project yang sedang dibangun user.
- Jangan mengarang data.
- Kalau informasi tidak tersedia atau tidak yakin, katakan dengan jujur.
- Bedakan antara fakta, asumsi, proyeksi, dan opini.
- Kalau user memberikan angka atau data, gunakan angka tersebut
  sebagai konteks percakapan.
- Kalau pertanyaan merupakan lanjutan dari pembahasan sebelumnya,
  jangan mengulang dari nol. Lanjutkan topiknya.
"""


# ============================================================
# CONVERSATION MEMORY
# ============================================================

# Memory disimpan berdasarkan chat/grup Telegram.
#
# Contoh:
#
# chat_id grup A
#   ↓
# pertanyaan 1
# jawaban 1
# pertanyaan 2
# jawaban 2
#
# Memory dibatasi agar tidak terus membesar.

MAX_MEMORY_MESSAGES = 20

conversation_memory = defaultdict(
    lambda: deque(maxlen=MAX_MEMORY_MESSAGES)
)


# ============================================================
# SPLIT LONG TELEGRAM MESSAGE
# ============================================================

async def send_long_message(message, text, max_length=4000):
    """
    Telegram mempunyai batas panjang pesan.
    Kalau jawaban AI terlalu panjang, kita pecah
    menjadi beberapa pesan.
    """

    if not text:
        return

    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]

        await message.reply_text(chunk)


# ============================================================
# BUILD CONVERSATION INPUT
# ============================================================

def build_conversation_input(chat_id, current_question):
    """
    Menggabungkan memory percakapan sebelumnya
    dengan pertanyaan terbaru.
    """

    history = conversation_memory[chat_id]

    conversation_text = ""

    if history:
        conversation_text += """
Berikut adalah percakapan sebelumnya dalam thread/grup ini.
Gunakan sebagai konteks untuk memahami pertanyaan terbaru.

"""

        for item in history:
            role = item["role"]
            content = item["content"]

            if role == "user":
                conversation_text += f"USER:\n{content}\n\n"

            elif role == "assistant":
                conversation_text += f"BRE AI:\n{content}\n\n"

    conversation_text += f"""
PERTANYAAN TERBARU USER:
{current_question}
"""

    return conversation_text


# ============================================================
# HANDLE /CLEAR
# ============================================================

async def clear_memory(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Menghapus memory percakapan pada grup/chat tersebut.
    """

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
    # TRIGGER 1:
    # USER MENTION BRE AI
    # ========================================================

    is_mentioned = (
        f"@{bot_username.lower()}" in text.lower()
    )


    # ========================================================
    # TRIGGER 2:
    # USER REPLY KE PESAN BRE AI
    # ========================================================

    is_reply_to_bot = False

    replied_message = None

    if update.message.reply_to_message:

        replied_message = update.message.reply_to_message

        if replied_message.from_user:

            if replied_message.from_user.id == bot_id:
                is_reply_to_bot = True


    # ========================================================
    # CHAT BIASA
    # ========================================================

    # Kalau bukan mention dan bukan reply ke Bre,
    # Bre tidak ikut campur.
    #
    # Contoh:
    #
    # "Menurut gue Kallani keren."
    #
    # Bre diam.

    if not is_mentioned and not is_reply_to_bot:
        return


    # ========================================================
    # BERSIHKAN MENTION
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
    # KALAU REPLY KE BRE
    # ========================================================

    # Kita beritahu AI bahwa user sedang membalas
    # pesan Bre AI tertentu.
    #
    # Ini sangat membantu ketika user berkata:
    #
    # "Kalau 1.000 ha?"
    #
    # tanpa menjelaskan ulang konteksnya.

    if is_reply_to_bot and replied_message:

        replied_text = replied_message.text or ""

        if replied_text:

            user_text = f"""
USER SEDANG MEMBALAS PESAN BRE AI INI:

{replied_text}

PERTANYAAN / PESAN LANJUTAN USER:

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
    # GET CHAT ID
    # ========================================================

    chat_id = update.effective_chat.id


    # ========================================================
    # BUILD CONTEXT
    # ========================================================

    input_text = build_conversation_input(
        chat_id,
        user_text
    )


    # ========================================================
    # OPENAI
    # ========================================================

    try:

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
        # SIMPAN USER MESSAGE KE MEMORY
        # ====================================================

        conversation_memory[chat_id].append({
            "role": "user",
            "content": user_text
        })


        # ====================================================
        # SIMPAN JAWABAN BRE KE MEMORY
        # ====================================================

        conversation_memory[chat_id].append({
            "role": "assistant",
            "content": answer
        })


        # ====================================================
        # KIRIM JAWABAN
        # ====================================================

        await send_long_message(
            update.message,
            answer
        )


    except Exception as e:

        print(
            "ERROR:",
            repr(e)
        )

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


    # Pesan biasa
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
