import json
import os
import random

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

WORDS_FILE = "words.json"
PROGRESS_FILE = "progress.json"

with open(WORDS_FILE, "r", encoding="utf-8") as f:
    ALL_WORDS: dict = json.load(f)


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(ALL_WORDS)


def save_progress(words: dict) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)


def save_all_words(words: dict) -> None:
    with open(WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)


state = {
    "words": load_progress(),
    "current_word": None,
    "finished": False,
    "awaiting_add": False,
}

keyboard = ReplyKeyboardMarkup(
    [["/skip", "/restart", "/add_word"]], resize_keyboard=True
)


def get_next_word() -> str | None:
    return None if not state["words"] else random.choice(list(state["words"].keys()))


async def send_word(update: Update) -> None:
    if not state["words"]:
        state["finished"] = True
        await update.message.reply_text("🎉 You've learned all the words!", reply_markup=keyboard)
        return
    state["current_word"] = get_next_word()
    await update.message.reply_text(f"Translate: *{state['current_word']}*", parse_mode="Markdown", reply_markup=keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Just start/resume without resetting progress."""
    state["finished"] = False
    state["awaiting_add"] = False
    await update.message.reply_text("▶️ Resuming! Your progress is saved.", reply_markup=keyboard)
    await send_word(update)


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset all progress and restart."""
    state["words"] = dict(ALL_WORDS)
    state["current_word"] = None
    state["finished"] = False
    state["awaiting_add"] = False
    save_progress(state["words"])
    await update.message.reply_text("🔄 Restarted! All words reset.", reply_markup=keyboard)
    await send_word(update)


async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not state["current_word"]:
        return
    correct = state["words"][state["current_word"]]
    await update.message.reply_text(
        f"⏭ Skip!\n*{state['current_word']}* → {correct}", parse_mode="Markdown", reply_markup=keyboard
    )
    await send_word(update)


async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state["awaiting_add"] = True
    await update.message.reply_text(
        "✏️ Send the word and translation in format:\n`word — translation`",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if state["awaiting_add"]:
        text = update.message.text.strip()

        separator = None
        for sep in ["—", "–", "-"]:
            if sep in text:
                separator = sep
                break

        if not separator:
            await update.message.reply_text(
                "⚠️ Wrong format. Use:\n`word - translation`", parse_mode="Markdown", reply_markup=keyboard
            )
            return

        word, _, translation = text.partition(separator)
        word, translation = word.strip(), translation.strip()

        if not word or not translation:
            await update.message.reply_text("⚠️ Both word and translation must be non-empty.", reply_markup=keyboard)
            return
        if word in ALL_WORDS:
            await update.message.reply_text(f"⚠️ *{word}* already exists: {ALL_WORDS[word]}", parse_mode="Markdown", reply_markup=keyboard)
            state["awaiting_add"] = False
            return
        ALL_WORDS[word] = translation
        state["words"][word] = translation
        save_all_words(ALL_WORDS)
        save_progress(state["words"])
        state["awaiting_add"] = False
        await update.message.reply_text(f"✅ Added: *{word}* → {translation}", parse_mode="Markdown", reply_markup=keyboard)
        return

    # --- answer check flow ---
    if state["finished"] or not state["current_word"]:
        return
    user_answer = update.message.text.strip()
    correct = state["words"][state["current_word"]]
    if user_answer.lower() == correct.lower():
        del state["words"][state["current_word"]]
        save_progress(state["words"])
        await update.message.reply_text(
            f"✅ Correct!\n📚 Words left: {len(state['words'])}", reply_markup=keyboard
        )
        await send_word(update)
    else:
        await update.message.reply_text("❌ Wrong!", reply_markup=keyboard)


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("restart", restart))
app.add_handler(CommandHandler("skip", skip))
app.add_handler(CommandHandler("add_word", add_word))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))

if WEBHOOK_URL:
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook",
        url_path="webhook",
    )
else:
    app.run_polling()