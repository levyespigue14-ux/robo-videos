"""
EDITOR NO TELEGRAM — fica ligado e espera você mandar o vídeo gerado na IA.

Como usar no Telegram:
  • Responda a mensagem do kit (a dos prompts) com o vídeo do YouTube Create
    -> ele devolve o vídeo pronto: gancho, voz, legenda, preço e chamada pro Telegram.
  • Se mandar o vídeo sem responder nada, ele usa o ÚLTIMO produto enviado.
  • Escreva uma frase na legenda do vídeo pra usar como gancho no lugar do automático.

Rodar:  venv\\Scripts\\python editor_bot.py   (ou dois cliques no iniciar_editor.bat)
⚠️ Use um bot SÓ pra isso (token diferente do bot de promoções), senão os dois brigam pelas mensagens.
"""
import json
import os
import time
import traceback
from datetime import datetime

import requests

import bot_videos
from bot_videos import KITS, NICHOS, log, musica, tg  # também carrega o .env

import editar_video

TOKEN = os.environ["TELEGRAM_TOKEN"]
DONO = str(os.environ["TELEGRAM_CHAT_ID"])
PASTA = "videos"
AJUDA = ("👋 Sou o seu robô de vídeos.\n\n"
         "1️⃣ Toque num botão aqui embaixo pra receber um produto (foto + prompts):\n"
         "   🔥 Em alta = os mais vendidos  ·  💎 Achado escondido = vende bem, pouca concorrência\n"
         "2️⃣ Gere o vídeo no ChatGPT + YouTube Create.\n"
         "3️⃣ Responda a mensagem do kit com o vídeo — eu devolvo pronto pra postar.\n\n"
         "Quer outro gancho? Escreva a frase na legenda do vídeo.")

# botões do teclado do Telegram -> nicho (None = vai variando sozinho)
BOTOES = {"🎲 Produto variado": None, "🏠 Casa": "casa", "💄 Beleza": "beleza",
          "👗 Moda feminina": "moda_feminina", "👔 Moda masculina": "moda_masculina",
          "👗 Moda": "moda_feminina",  # botão antigo (caso o Telegram ainda mostre)
          "📱 Tecnologia": "tecnologia", "👟 Calçados": "calcados", "🐶 Pet": "pet",
          "💪 Fitness": "fitness", "🎮 Gamer": "gamer"}
ESTRATEGIAS = {"🔥 Em alta": "alta", "💎 Achado escondido": "escondido"}
TECLADO = json.dumps({"keyboard": [["🔥 Em alta", "💎 Achado escondido"], ["🏠 Casa", "💄 Beleza", "👟 Calçados"],
                                   ["👗 Moda feminina", "👔 Moda masculina"],
                                   ["📱 Tecnologia", "🐶 Pet"], ["💪 Fitness", "🎮 Gamer"]],
                      "resize_keyboard": True, "is_persistent": True})


def pedir_produto(chat, nicho, para=None, estrategia=None):
    nome = nicho or "variado"
    tipo = {"alta": "em alta", "escondido": "achado escondido"}.get(estrategia, "produto")
    responder(chat, f"🔎 Procurando {tipo} ({nome})…", para)
    qtd = bot_videos.rodar(nicho=nicho, quantos=1, modo="ia", estrategia=estrategia)
    if not qtd:
        responder(chat, f"😕 Não achei produto bom em {nome} agora (todos já usados ou fora dos filtros). "
                        "Tente outro nicho.")


def responder(chat, texto, para=None, teclado=False):
    dados = {"chat_id": chat, "text": texto, "disable_web_page_preview": "true"}
    if teclado:
        dados["reply_markup"] = TECLADO
    if para:
        dados["reply_to_message_id"] = para
    return tg("sendMessage", data=dados)


def achar_produto(msg):
    try:
        kits = json.load(open(KITS, encoding="utf-8"))
    except Exception:
        return None
    if not kits:
        return None
    resp = msg.get("reply_to_message")
    if resp:
        for kit in reversed(kits):
            if resp["message_id"] in kit["ids"]:
                return kit["produto"]
    return kits[-1]["produto"]


def baixar(file_id, destino):
    info = tg("getFile", data={"file_id": file_id})["result"]
    url = f"https://api.telegram.org/file/bot{TOKEN}/{info['file_path']}"
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for parte in r.iter_content(1 << 16):
                f.write(parte)


def tratar(msg):
    chat = str(msg["chat"]["id"])
    if chat != DONO:
        return  # só obedece você
    texto = (msg.get("text") or "").strip()
    if texto.startswith("/start") or texto.startswith("/ajuda"):
        responder(chat, AJUDA, teclado=True)
        return
    if texto in ESTRATEGIAS:
        pedir_produto(chat, None, msg["message_id"], ESTRATEGIAS[texto])
        return
    if texto in BOTOES:
        pedir_produto(chat, BOTOES[texto], msg["message_id"])
        return
    if texto.startswith("/produto"):
        partes = texto.split()
        nicho = partes[1].lower() if len(partes) > 1 else None
        if nicho and nicho not in NICHOS:
            responder(chat, "Nichos: " + ", ".join(NICHOS))
            return
        pedir_produto(chat, nicho, msg["message_id"])
        return

    arq = msg.get("video") or msg.get("animation")
    doc = msg.get("document")
    if not arq and doc and str(doc.get("mime_type", "")).startswith("video"):
        arq = doc
    if not arq:
        if texto:
            responder(chat, "Toque num botão pra pedir um produto, ou me mande o vídeo 🎬 respondendo o kit.",
                      teclado=True)
        return
    if arq.get("file_size", 0) > 20 * 1024 * 1024:
        responder(chat, "⚠️ Vídeo maior que 20 MB. Mande como vídeo normal (não como arquivo) "
                        "que o Telegram comprime.", msg["message_id"])
        return

    produto = achar_produto(msg)
    if not produto:
        responder(chat, "Não achei nenhum produto. Rode o robô primeiro pra receber um kit.", msg["message_id"])
        return

    responder(chat, f"⏳ Editando o vídeo de: {produto['nome'][:60]}…", msg["message_id"])
    os.makedirs(PASTA, exist_ok=True)
    base = os.path.join(PASTA, f"{datetime.now():%Y%m%d_%H%M%S}_ia")
    entrada, saida = base + "_bruto.mp4", base + "_pronto.mp4"
    baixar(arq["file_id"], entrada)

    gancho = (msg.get("caption") or "").strip() or None
    _, legenda = editar_video.finalizar(entrada, produto, saida, musica(), gancho=gancho)

    with open(saida, "rb") as f:
        tg("sendVideo", data={"chat_id": chat, "caption": legenda[:1000], "supports_streaming": "true",
                              "reply_to_message_id": msg["message_id"]},
           files={"video": (os.path.basename(saida), f, "video/mp4")})
    responder(chat, f"✅ Pronto! Link pro Shopee Vídeo:\n{produto.get('link', '')}\n\n"
                    "No TikTok: ative “Conteúdo gerado por IA”.")
    if bot_videos.mandar_tiktok(saida):
        responder(chat, "⚠️ No TikTok, antes de publicar, ative “Conteúdo gerado por IA”.")
    log.info(f"editor: vídeo finalizado {saida}")


def main():
    log.info("editor ligado, esperando vídeos no Telegram…")
    offset = None
    while True:
        try:
            dados = {"timeout": 50, "allowed_updates": json.dumps(["message"])}
            if offset:
                dados["offset"] = offset
            r = requests.post(f"https://api.telegram.org/bot{TOKEN}/getUpdates", data=dados, timeout=70)
            if r.status_code == 409:
                log.error("Outro programa está usando ESTE token (provavelmente o bot de promoções). "
                          "Crie um bot novo no @BotFather só pros vídeos e troque o TELEGRAM_TOKEN no .env.")
                time.sleep(30)
                continue
            r.raise_for_status()
            for up in r.json().get("result", []):
                offset = up["update_id"] + 1
                msg = up.get("message")
                if not msg:
                    continue
                try:
                    tratar(msg)
                except Exception as e:
                    log.error(traceback.format_exc())
                    try:
                        responder(str(msg["chat"]["id"]), f"❌ Deu erro ao editar: {str(e)[:300]}")
                    except Exception:
                        pass
        except requests.RequestException as e:
            log.warning(f"sem conexão com o Telegram ({e.__class__.__name__}), tentando de novo…")
            time.sleep(10)


if __name__ == "__main__":
    main()
