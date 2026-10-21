"""
ROBÔ DE VÍDEOS — roda sozinho (cron) na Oracle, separado do bot de promoções.

Cada execução:
  1. escolhe o nicho da vez (revezando) e busca produtos bons na Shopee
  2. gera o vídeo estilo achadinho (voz de IA + música + legenda)
  3. te manda no Telegram: o vídeo, a legenda pronta pro TikTok e o link de afiliado
     (pra colar no Shopee Vídeo / TikTok)

Uso:
    python bot_videos.py                 # execução normal (o cron chama assim)
    python bot_videos.py --nicho casa    # força um nicho
    python bot_videos.py --teste         # usa produtos de teste, sem Shopee e sem Telegram
    python bot_videos.py --teste --enviar  # teste, mas manda no Telegram
"""
import argparse
import json
import logging
import os
import random
import time
from datetime import datetime

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
os.chdir(AQUI)


def carregar_env(caminho=".env"):
    if not os.path.exists(caminho):
        return
    for linha in open(caminho, encoding="utf-8"):
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


carregar_env()

import gerar_video_ugc as ugc  # noqa: E402  (depois do .env, por causa da chave do Claude)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler("bot_videos.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger()

# Nichos e palavras de busca. Mude à vontade: o robô sorteia uma palavra por vídeo.
NICHOS = {
    "casa": ["organizador cozinha", "garrafa térmica", "potes herméticos", "utensílios cozinha", "jarra vidro",
             "luminária led", "porta tempero", "mop giratório", "mini processador", "umidificador"],
    "tecnologia": ["fone bluetooth", "carregador turbo", "suporte celular", "caixa de som bluetooth", "smartwatch",
                   "ring light", "power bank", "projetor portátil", "câmera wifi"],
    "moda_feminina": ["cropped feminino", "vestido verão", "conjunto feminino", "bolsa feminina", "blusa feminina",
                      "calça wide leg", "saia midi", "body feminino", "pijama feminino", "short jeans feminino"],
    "moda_masculina": ["camiseta oversized", "bermuda masculina", "camisa polo masculina", "calça cargo masculina",
                       "boné", "relógio masculino", "carteira masculina", "jaqueta masculina", "óculos de sol masculino"],
    "beleza": ["sérum facial", "perfume árabe", "kit maquiagem", "skincare", "cílios postiços", "escova secadora",
               "gloss labial", "lip tint"],
    "calcados": ["tênis feminino", "tênis masculino", "chinelo nuvem", "sandália feminina", "papete"],
    "pet": ["brinquedo cachorro", "caminha pet", "comedouro automático", "escova pet", "arranhador gato"],
    "fitness": ["garrafa academia", "elástico treino", "tapete yoga", "coqueteleira", "corda pular"],
    "gamer": ["mouse gamer", "teclado gamer", "headset gamer", "controle bluetooth", "fita led rgb"],
}
# visual (cores/voz) de cada nicho — os nichos extras usam um dos estilos prontos
VISUAL = {"pet": "geral", "fitness": "geral", "gamer": "tecnologia",
          "moda_feminina": "moda", "moda_masculina": "moda"}

HISTORICO = "historico.json"
PASTA = "videos"


def ler_historico():
    try:
        return json.load(open(HISTORICO, encoding="utf-8"))
    except Exception:
        return {"usados": [], "ultimo_nicho": None}


def salvar_historico(h):
    h["usados"] = h["usados"][-2000:]
    json.dump(h, open(HISTORICO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def proximo_nicho(h, nichos):
    lista = list(nichos)
    if h.get("ultimo_nicho") in lista:
        return lista[(lista.index(h["ultimo_nicho"]) + 1) % len(lista)]
    return lista[0]


def musica():
    if not os.path.isdir("musicas"):
        return None
    ops = [os.path.join("musicas", m) for m in os.listdir("musicas") if m.lower().endswith((".mp3", ".wav", ".m4a"))]
    return random.choice(ops) if ops else None


# ---------------- Telegram ----------------
def tg(metodo, **kw):
    token = os.environ["TELEGRAM_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", timeout=120, **kw)
    if not r.ok:
        raise RuntimeError(f"Telegram {metodo}: {r.status_code} {r.text[:200]}")
    return r.json()


def enviar_telegram(video, legenda, produto):
    chat = os.environ["TELEGRAM_CHAT_ID"]
    with open(video, "rb") as f:
        tg("sendVideo", data={"chat_id": chat, "caption": legenda[:1000], "supports_streaming": "true"},
           files={"video": (os.path.basename(video), f, "video/mp4")})
    tg("sendMessage", data={
        "chat_id": chat,
        "text": (f"🔗 Link de afiliado:\n{produto['link']}\n\n"
                 f"💰 {ugc.gv.brl(produto['preco'])} (-{produto['desconto']}%)"
                 + (f" · comissão {produto['comissao'] * 100:.0f}%" if produto.get("comissao") else "")
                 + "\n\nPra postar: TikTok (cola a legenda acima) e Shopee Vídeo (marca o produto)."),
        "disable_web_page_preview": "true",
    })



# ---------------- TikTok (rascunhos) ----------------
def mandar_tiktok(video):
    """Se o TikTok estiver conectado, manda o vídeo pros rascunhos e avisa no Telegram."""
    try:
        import tiktok
        if not tiktok.configurado():
            return False
        tiktok.enviar_rascunho(video)
        log.info(f"vídeo enviado pros rascunhos do TikTok: {os.path.basename(video)}")
        try:
            tg("sendMessage", data={"chat_id": os.environ["TELEGRAM_CHAT_ID"],
                                    "text": "📲 Esse vídeo já está nos RASCUNHOS do seu TikTok.\n"
                                            "Abra o app → caixa de entrada/notificações → coloque um som em alta → Publicar."})
        except Exception:
            pass
        return True
    except Exception as e:
        log.warning(f"não consegui mandar pro TikTok: {e}")
        return False


KITS = "kits.json"


def salvar_kit(ids, produto, cat):
    """Guarda o produto de cada kit, pra o editor saber de qual produto é o vídeo que você responder."""
    try:
        kits = json.load(open(KITS, encoding="utf-8"))
    except Exception:
        kits = []
    p = {k: v for k, v in produto.items() if k in
         ("id", "nome", "nome_curto", "preco", "preco_antigo", "desconto", "nota", "vendidos", "link", "imagem", "cena")}
    p["categoria"] = cat
    kits.append({"ids": ids, "produto": p, "quando": datetime.now().isoformat(timespec="minutes")})
    json.dump(kits[-60:], open(KITS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def enviar_kit_ia(k, produto, cat):
    """Modo storyboard: storyboard (ou foto) + prompts prontos pra colar no YouTube Create."""
    from html import escape

    chat = os.environ["TELEGRAM_CHAT_ID"]
    ids = []
    img = k["storyboard"] or k["foto"]
    if img:
        tit = "🎬 Storyboard pronto" if k["storyboard"] else "📸 Foto do produto (gere o storyboard com o prompt 1)"
        tit = ("💎 Achado escondido · " if produto.get("estrategia") == "escondido" else "🔥 Em alta · ") + tit
        r = tg("sendPhoto", data={"chat_id": chat, "caption": f"{tit}\n{produto['nome'][:150]}"},
               files={"photo": ("storyboard.jpg", img, "image/jpeg")})
        ids.append(r["result"]["message_id"])
    passos = []
    if not k["storyboard"]:
        passos.append("<b>1) Storyboard</b> — mande a foto acima pro ChatGPT/Gemini com:\n"
                      f"<code>{escape(k['prompt_storyboard'])}</code>")
    if k.get("fundo"):
        passos.insert(0, f"🎨 Nicho: <b>{escape(k.get('nicho', ''))}</b> · fundo da vez: <i>{escape(k['fundo'])}</i>")
    passos.append(f"<b>{'1' if k['storyboard'] else '2'}) Vídeo</b> — YouTube Create → "
                  "Criar com IA → anexe o storyboard e a foto do produto como referência e cole:\n"
                  f"<code>{escape(k['prompt_video'])}</code>")
    passos.append("⚠️ Ao postar no TikTok, ative <b>“Conteúdo gerado por IA”</b>.")
    passos.append("✂️ Gerou o vídeo? <b>Responda esta mensagem com ele</b> que eu devolvo pronto "
                  "(gancho, voz, legenda e chamada pro Telegram). Escreva uma frase junto se quiser outro gancho.")
    passos.append(f"🔗 {escape(produto['link'])}")
    r = tg("sendMessage", data={"chat_id": chat, "text": "\n\n".join(passos), "parse_mode": "HTML",
                                "disable_web_page_preview": "true"})
    ids.append(r["result"]["message_id"])
    salvar_kit(ids, produto, cat)
    if k["erro"]:
        log.warning(f"storyboard não gerado: {k['erro'][:200]}")


# ---------------- principal ----------------
def limpar_antigos(dias=3):
    if not os.path.isdir(PASTA):
        return
    limite = time.time() - dias * 86400
    for arq in os.listdir(PASTA):
        cam = os.path.join(PASTA, arq)
        if os.path.getmtime(cam) < limite:
            os.remove(cam)


def rodar(nicho=None, quantos=1, teste=False, enviar=True, sem_voz=False, modo="ambos", estrategia=None):
    # alta = mais vendidos | escondido = vende bem mas pouca concorrência | misto = sorteia
    estrategia = estrategia or os.environ.get("ESTRATEGIA", "misto")
    if estrategia == "misto":
        estrategia = random.choice(["alta", "escondido"])
    h = ler_historico()
    nicho = nicho or proximo_nicho(h, NICHOS)

    if teste:
        produtos = json.load(open("teste_ugc/produtos.json", encoding="utf-8"))[:quantos]
        for p in produtos:
            p.setdefault("link", "https://s.shopee.com.br/TESTE")
    else:
        import shopee_api

        produtos, tentativas = [], 0
        palavras = NICHOS[nicho][:]
        random.shuffle(palavras)
        for palavra in palavras:
            tentativas += 1
            log.info(f"[{nicho}] buscando: {palavra}")
            produtos += shopee_api.bons_produtos(palavra, set(h["usados"]), quantos=quantos - len(produtos),
                                                 estrategia=estrategia)
            if len(produtos) >= quantos or tentativas >= 4:
                break
        if not produtos:
            log.warning(f"[{nicho}] nenhum produto bom achado; tente afrouxar os filtros")
            return 0
        for p in produtos:
            p["categoria"] = VISUAL.get(nicho, nicho)
            p["cena"] = nicho

    os.makedirs(PASTA, exist_ok=True)
    for p in produtos:
        cat = p.get("categoria") or nicho
        if modo in ("ugc", "ambos"):
            nome = f"{datetime.now():%Y%m%d_%H%M%S}_{nicho}.mp4"
            saida = os.path.join(PASTA, nome)
            try:
                ugc.gerar(p, saida, cat, musica(), usar_voz=not sem_voz)
                legenda = open(saida.replace(".mp4", "_legenda.txt"), encoding="utf-8").read()
                if enviar:
                    enviar_telegram(saida, legenda, p)
                    log.info(f"vídeo enviado no Telegram: {nome}")
                    mandar_tiktok(saida)
            except Exception:
                log.exception(f"falhou o vídeo de {p['nome'][:40]} (se gerou, está na pasta videos/)")
        if modo in ("ia", "ambos"):
            try:
                import storyboard

                k = storyboard.kit(p, cat)
                if enviar:
                    enviar_kit_ia(k, p, cat)
                    log.info("kit de vídeo com IA enviado")
                else:
                    log.info(f"[teste] prompt vídeo: {k['prompt_video']}")
            except Exception:
                log.exception("falhou o kit de vídeo com IA")
        if p.get("id"):
            h["usados"].append(p["id"])

    h["ultimo_nicho"] = nicho
    salvar_historico(h)
    limpar_antigos()
    return len(produtos)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nicho", choices=list(NICHOS))
    ap.add_argument("--quantos", type=int, default=int(os.environ.get("VIDEOS_POR_EXECUCAO", 1)))
    ap.add_argument("--teste", action="store_true")
    ap.add_argument("--enviar", action="store_true", help="no modo teste, manda no Telegram mesmo assim")
    ap.add_argument("--sem-voz", action="store_true")
    ap.add_argument("--estrategia", choices=["alta", "escondido", "misto"])
    ap.add_argument("--modo", choices=["ugc", "ia", "ambos"], default=os.environ.get("MODO", "ambos"),
                    help="ugc = vídeo pronto | ia = storyboard + prompts | ambos")
    a = ap.parse_args()
    rodar(a.nicho, a.quantos, a.teste, enviar=(not a.teste) or a.enviar, sem_voz=a.sem_voz, modo=a.modo,
          estrategia=a.estrategia)
