import hashlib
import html
import logging
import os
import time
from urllib.parse import quote

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ["BOT_TOKEN"]
SP_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SP_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
http = httpx.AsyncClient(timeout=15)
_sp = {"token": None, "exp": 0.0}


async def deezer_search(q, limit=5):
    r = await http.get("https://api.deezer.com/search", params={"q": q, "limit": limit})
    r.raise_for_status()
    return r.json().get("data", [])


async def spotify_link(artist, title):
    if not (SP_ID and SP_SECRET):
        return None
    try:
        if time.time() > _sp["exp"]:
            r = await http.post("https://accounts.spotify.com/api/token",
                                data={"grant_type": "client_credentials"}, auth=(SP_ID, SP_SECRET))
            r.raise_for_status()
            _sp.update(token=r.json()["access_token"], exp=time.time() + r.json()["expires_in"] - 60)
        r = await http.get("https://api.spotify.com/v1/search",
                           params={"q": f"{artist} {title}", "type": "track", "limit": 1},
                           headers={"Authorization": f"Bearer {_sp['token']}"})
        items = r.json().get("tracks", {}).get("items", [])
        return items[0]["external_urls"]["spotify"] if items else None
    except Exception:
        logging.exception("Spotify")
        return None


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши название песни или «исполнитель - название», и я найду трек.")


async def search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    try:
        tracks = await deezer_search(q)
    except Exception:
        logging.exception("Deezer")
        await update.message.reply_text("Поиск сейчас недоступен, попробуйте позже.")
        return
    if not tracks:
        await update.message.reply_text("Ничего не нашёл. Попробуйте «исполнитель - название».")
        return
    for t in tracks:
        artist, title = t["artist"]["name"], t["title"]
        query = quote(f"{artist} {title}")
        sp = await spotify_link(artist, title)
