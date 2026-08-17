import os
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = """
Lu adalah Bre AI.

Gaya bicara:
- Santai seperti ngobrol dengan teman dekat.
- Gunakan bahasa Indonesia informal.
- Boleh menggunakan "bre", "wkwk", dan emoji seperlunya.
- Jangan terlalu formal.
- Tetap akurat dan jujur.
- Kalau tidak tahu, bilang tidak tahu.
- Jangan mengarang fakta.
- Jawaban harus jelas dan langsung ke inti.

Lu adalah AI assistant di grup Telegram.
"""


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    text = update.message.text

    if not text:
        return

    # Hanya merespons kalau bot di-mention
    bot_username = context.bot.username

    if f"@{bot_username}" not in text:
        return

    # Hilangkan mention bot
    user_text = text.replace(
        f"@{bot_username}",
        ""
    ).strip()

    if not user_text:
        await update.message.reply_text(
            "Yo bre 😎 Ada yang mau ditanyain?"
        )
        return

    try:
        response = client.responses.create(
            model="gpt-5.6",
            instructions=SYSTEM_PROMPT,
            input=user_text,
        )

        answer = response.output_text

        await update.message.reply_text(answer)

    except Exception as e:
        print("ERROR:", e)

        await update.message.reply_text(
            "Waduh bre, otak gue lagi error bentar 😂"
        )


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("🔥 Bre AI is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
