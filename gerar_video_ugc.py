"""
Vídeos estilo "achadinho de TikTok" (como os exemplos): UM produto por vídeo,
foto em tela cheia com movimento, frase de gancho no topo, narração com voz
de IA e legenda palavra por palavra, terminando com a chamada pro grupo do WhatsApp (link na bio).

Uso:
    python gerar_video_ugc.py produtos.json                 # um vídeo por produto
    python gerar_video_ugc.py produtos.json --max 2         # só os 2 primeiros
    python gerar_video_ugc.py produtos.json --sem-voz       # sem narração (só texto)
    python gerar_video_ugc.py produtos.json --musica fundo.mp3

Cada produto no JSON pode ter, além dos campos normais:
    "imagens": ["url1", "url2", ...]   -> várias fotos (fica bem mais dinâmico)
    "nome_curto": "top tomara que caia"  -> como o produto é chamado na fala
    "gancho" / "falas"                    -> texto pronto (senão é gerado)

Roteiro: se a variável ANTHROPIC_API_KEY existir, o Claude escreve o gancho e a
fala de cada produto. Sem ela, usa modelos de frase prontos por categoria.
Voz: edge-tts (grátis, precisa de internet). pip install edge-tts anthropic
"""
import argparse
import asyncio
import json
import math
import os
import random
import re
import subprocess
import tempfile
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter

import gerar_video as gv
from estilos import ESTILOS, categoria

W, H, FPS = gv.W, gv.H, gv.FPS
BRANCO, PRETO = (255, 255, 255), (0, 0, 0)

# Visual e voz de cada categoria no estilo UGC
UGC = {
    "tecnologia": {"gancho": "caixa", "caixa": (12, 12, 16), "caixa_txt": (198, 255, 0), "fonte_gancho": "Inter-Black.otf",
                   "destaque": (198, 255, 0), "voz": "pt-BR-AntonioNeural"},
    "moda": {"gancho": "tiktok", "destaque": (255, 214, 10), "fonte_gancho": "Inter-ExtraBold.otf",
             "voz": "pt-BR-FranciscaNeural"},
    "calcados": {"gancho": "tiktok", "destaque": (255, 214, 10), "fonte_gancho": "Inter-ExtraBold.otf",
                 "voz": "pt-BR-AntonioNeural"},
    "casa": {"gancho": "caixa", "caixa": (196, 140, 46), "caixa_txt": (255, 248, 235), "fonte_gancho": "Lora-Italic.ttf",
             "destaque": (255, 214, 10), "voz": "pt-BR-FranciscaNeural"},
    "beleza": {"gancho": "caixa", "caixa": (214, 51, 132), "caixa_txt": BRANCO, "fonte_gancho": "Lora-Italic.ttf",
               "destaque": (255, 170, 210), "voz": "pt-BR-FranciscaNeural"},
    "geral": {"gancho": "tiktok", "destaque": (255, 214, 10), "fonte_gancho": "Inter-ExtraBold.otf",
              "voz": "pt-BR-FranciscaNeural"},
}

# ---------------- roteiro ----------------
GANCHOS = {
    "moda": ["como assim {esse} {n} {ta} tão {baratinho}?", "achei {o} {n} {perfeito} pro verão", "{esse} {n} {eh} {lindo} demais"],
    "calcados": ["como assim {esse} {n} {custa} só isso?", "achei {o} {n} mais {confortavel} da Shopee"],
    "tecnologia": ["{esse} {n} {vale} cada centavo", "{o} {n} mais {barato} que eu já achei", "para de pagar caro em {n}"],
    "casa": ["amei {esse} {n}", "sua casa precisa {desse} {n}", "olha que {n} {lindo}"],
    "beleza": ["como assim {esse} {n} {custa} isso?", "achei {o} {n} {perfeito}", "{esse} {n} {eh} {viciante}"],
    "geral": ["olha o que eu achei na Shopee", "como assim isso custa tão pouco?", "achadinho do dia"],
}


PRODUTOS = [  # nomes de produto que o robô procura dentro do título da Shopee
    "cílios", "cilios", "tênis", "tenis", "sandália", "chinelo", "sapato", "bota", "fone", "headset",
    "carregador", "cabo", "adaptador", "caixa de som", "suporte", "capa", "película", "smartwatch", "relógio",
    "mouse", "teclado", "luminária", "ring light", "garrafa", "jarra", "pote", "potes", "organizador", "panela",
    "copo", "copos", "caneca", "toalha", "tapete", "perfume", "sérum", "serum", "creme", "hidratante", "batom",
    "gloss", "base", "paleta", "escova", "secador", "chapinha", "camiseta", "camisa", "blusa", "cropped",
    "vestido", "saia", "short", "bermuda", "calça", "jaqueta", "moletom", "conjunto", "bolsa", "mochila",
    "óculos", "boné", "kit", "jogo", "biquíni", "pijama", "meia", "cinto", "brinco", "colar", "pulseira",
]
LIGA = {"de", "da", "do", "para", "pra", "com", "sem", "em", "e", "a", "o", "à"}


def nome_curto(nome):
    """'Super Fofo Cílios Postiços Fluffy 3D' -> 'cílios postiços'."""
    limpo = re.sub(r"[【】\[\]()!|,/+]", " ", nome)
    pal = [p for p in limpo.split() if p]
    baixo = [p.lower() for p in pal]
    # 1) acha o primeiro nome de produto conhecido dentro do título
    melhor = None
    for prod in PRODUTOS:
        partes = prod.split()
        for k in range(len(baixo) - len(partes) + 1):
            if baixo[k:k + len(partes)] == partes and (melhor is None or k < melhor[0]):
                melhor = (k, len(partes))
    if melhor:
        k, n = melhor
        out = baixo[k:k + n]
        prox = baixo[k + n:k + n + 2]
        if prox and prox[0] in {"de", "da", "do"} and len(prox) > 1 and not re.search(r"\d", prox[1]):
            out += prox                                   # "jarra de vidro"
        elif prox and prox[0] not in LIGA and prox[0].isalpha() and not pal[k + n].isupper():
            out.append(prox[0])                           # "cílios postiços", "garrafa térmica"
        return " ".join(out)
    # 2) não achou: usa as primeiras palavras (sem marca em MAIÚSCULA e sem números)
    pal = [p for p in pal if not re.search(r"\d", p) and not (p.isupper() and len(p) > 3)]
    if not pal:
        return "achadinho"
    if len(pal) >= 3 and pal[1].lower() in {"de", "da", "do"}:
        return " ".join(w.lower() for w in pal[:3])
    return " ".join(w.lower() for w in pal[:2])


def generos(n):
    """Concordância simples: 'jarra' -> feminino, 'cílios'/'potes' -> plural."""
    pal = n.split()[0].lower()
    plural = pal.endswith("s") and len(pal) > 3 and pal not in {"tênis", "lápis", "ônibus", "gás", "mês"}
    fem = pal.rstrip("s").endswith(("a", "ã", "ção", "gem", "dade")) and pal not in {"sistema", "problema", "tema"}
    if fem:
        g = dict(esse="essa", desse="dessa", o="a", ele="ela", lindo="linda", perfeito="perfeita",
                 barato="barata", confortavel="confortável", viciante="viciante", eh="é",
                 custa="custa", ta="tá", vale="vale", baratinho="baratinha")
    else:
        g = dict(esse="esse", desse="desse", o="o", ele="ele", lindo="lindo", perfeito="perfeito",
                 barato="barato", confortavel="confortável", viciante="viciante", eh="é",
                 custa="custa", ta="tá", vale="vale", baratinho="baratinho")
    if plural:
        g = {k: (v + "s" if k in {"esse", "desse", "o", "ele", "lindo", "perfeito", "barato", "viciante"} else v)
             for k, v in g.items()}
        g.update(confortavel="confortáveis", eh="são", custa="custam", ta="tão", vale="valem",
                 baratinho=g["baratinho"] + "s")
    return g


# Frases sorteadas a cada vídeo (pode adicionar as suas!)
# {esse} {n} {o} {ele} {lindo} {perfeito} {barato} são trocados automaticamente
ABERTURAS = [
    "Gente, para tudo e olha {esse} {n}!",
    "Eu não acreditei quando vi o preço {desse} {n}.",
    "Se você tava procurando {o} {n} {perfeito}, achei pra você.",
    "Corre aqui que eu achei {o} {n} mais {barato} da Shopee.",
    "Achadinho do dia: {esse} {n} aqui.",
    "Vocês precisam conhecer {esse} {n}.",
    "Sério, como ninguém me contou {desse} {n} antes?",
    "Olha o que eu achei hoje na Shopee: {esse} {n}.",
    "Quem mais tava precisando de {o} {n} assim?",
    "Esse é o tipo de achadinho que some rápido.",
]
PRECOS = [
    "Custava {antigo}, e agora tá saindo por só {preco}.",
    "De {antigo} por apenas {preco}. Isso mesmo!",
    "Tá com {desconto} por cento de desconto, saindo por {preco}.",
    "Sabe quanto tá? Só {preco}! Antes era {antigo}.",
    "Por menos de {redondo} reais você leva pra casa.",
]
PROVAS = [
    "Avaliação {nota} de 5, quem comprou amou.",
    "Nota {nota} na Shopee, avaliação lá em cima.",
    "Tá com nota {nota}, a galera tá amando.",
]
CHAMADAS = [
    "O link tá no meu grupo do WhatsApp, entra pela bio!",
    "Corre pro meu grupo do WhatsApp, o link tá na bio!",
    "Quer o link? Entra no meu grupo do WhatsApp, tá na bio.",
    "Tem esse e outros achadinhos no meu grupo do WhatsApp, link na bio!",
    "Entra no grupo do WhatsApp pela bio e pega o link antes que acabe!",
]


def roteiro_modelo(p, cat, curto=False):
    n = p.get("nome_curto") or nome_curto(p["nome"])
    g = generos(n)
    rnd = random.Random()  # sorteia diferente a cada vídeo
    gancho = rnd.choice(GANCHOS.get(cat, GANCHOS["geral"])).format(n=n, **g)
    dados = dict(
        n=n, **g,
        antigo=gv.brl(p["preco_antigo"]), preco=gv.brl(p["preco"]),
        desconto=int(p.get("desconto") or 0), redondo=int(p["preco"] // 5 * 5 + 5),
        nota=str(p.get("nota", "")).replace(".", ","),
        vendidos=str(p.get("vendidos", "")).replace("+", "").strip(),
    )
    precos = PRECOS if dados["desconto"] >= 10 else [x for x in PRECOS if "desconto" not in x]
    falas = [rnd.choice(ABERTURAS).format(**dados), rnd.choice(precos).format(**dados)]
    if p.get("nota") and not curto:
        falas.append(rnd.choice(PROVAS).format(**dados))
    falas.append(rnd.choice(CHAMADAS))
    return gancho, falas


def roteiro_claude(p, cat):
    import anthropic

    cli = anthropic.Anthropic()
    pedido = (
        "Você escreve roteiros curtos de vídeo de achadinhos da Shopee para TikTok, em português do Brasil, "
        "tom animado e natural de influenciadora, sem exagero. Produto:\n"
        f"{json.dumps(p, ensure_ascii=False)}\nCategoria: {cat}\n\n"
        "Responda SÓ com JSON: {\"nome_curto\": \"como chamar o produto em 2-4 palavras\", "
        "\"gancho\": \"frase curta pro topo do vídeo, até 8 palavras, sem emoji\", "
        "\"falas\": [\"3 a 4 frases curtas da narração, total até 40 palavras; uma delas fala o preço; "
        "a última manda entrar no meu grupo do WhatsApp pelo link da bio\"]}"
    )
    r = cli.messages.create(model="claude-haiku-5-5", max_tokens=400, messages=[{"role": "user", "content": pedido}])
    txt = r.content[0].text
    dados = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    return dados["gancho"], dados["falas"]


def roteiro(p, cat, curto=False):
    if p.get("gancho") and p.get("falas"):
        return p["gancho"], p["falas"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return roteiro_claude(p, cat)
        except Exception as e:
            print(f"  ! Claude falhou ({e}); usando modelo pronto")
    return roteiro_modelo(p, cat, curto)


# ---------------- voz + tempo de cada palavra ----------------
async def _tts(texto, voz, mp3):
    import edge_tts

    try:
        com = edge_tts.Communicate(texto, voz, rate="+12%", boundary="WordBoundary")
    except TypeError:  # versões antigas do edge-tts
        com = edge_tts.Communicate(texto, voz, rate="+12%")
    palavras = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                ini = ch["offset"] / 1e7
                palavras.append((ch["text"], ini, ini + ch["duration"] / 1e7))
    return palavras


def tempos_estimados(texto):
    """Sem voz: estima quando cada palavra 'seria falada'."""
    t, palavras = 0.3, []
    for w in texto.split():
        d = 0.16 + 0.055 * len(w)
        palavras.append((w, t, t + d))
        t += d + (0.28 if w[-1] in ".!?," else 0.04)
    return palavras


def narrar(falas, voz, pasta_tmp, usar_voz=True):
    texto = " ".join(falas)
    if usar_voz:
        mp3 = os.path.join(pasta_tmp, "voz.mp3")
        try:
            palavras = asyncio.run(_tts(texto, voz, mp3))
            if palavras:
                return mp3, palavras
            print("  ! a voz veio sem marcação de palavras; legenda com tempo estimado")
            return mp3, tempos_estimados(texto)
        except Exception as e:
            print(f"  ! sem voz ({type(e).__name__}): gerando só com legenda")
    return None, tempos_estimados(texto)


def blocos_legenda(palavras, max_pal=3):
    """Junta as palavras em blocos de até 3 (quebra em fim de frase)."""
    blocos, atual = [], []
    for w in palavras:
        atual.append(w)
        if len(atual) == max_pal or w[0][-1] in ".!?,":
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    return blocos


# ---------------- imagens ----------------
def preparar_foto(img):
    """Foto vertical: preenche a tela. Foto quadrada (Shopee): fundo desfocado + foto grande."""
    w, h = img.size
    base = img.copy()
    esc = max(W / w, H / h) * 1.18
    fundo = base.resize((int(w * esc), int(h * esc)), Image.LANCZOS)
    fundo = fundo.crop(((fundo.width - W) // 2, (fundo.height - H) // 2, (fundo.width + W) // 2, (fundo.height + H) // 2))
    if w / h < 0.75:
        return fundo.convert("RGB"), True
    fundo = fundo.filter(ImageFilter.GaussianBlur(40))
    fundo = Image.blend(fundo, Image.new("RGB", (W, H), PRETO), 0.25)
    return fundo.convert("RGB"), False


def quadro_foto(foto, fundo_tela_cheia, t, dur, k):
    """Zoom/pan lento + leve tremida de câmera na mão."""
    fundo, cheia = fundo_tela_cheia
    z = 1.0 + 0.12 * (t / dur)
    if k % 2:
        z = 1.12 - 0.12 * (t / dur)
    dx = 6 * math.sin(t * 2.3 + k) + (18 if k % 3 == 0 else -18) * (t / dur)
    dy = 5 * math.cos(t * 1.9 + k)
    if cheia:
        im = fundo.resize((int(W * z), int(H * z)), Image.BILINEAR)
        x0, y0 = (im.width - W) / 2 - dx, (im.height - H) / 2 - dy
        return im.crop((int(x0), int(y0), int(x0) + W, int(y0) + H)).convert("RGBA")
    tela = fundo.copy().convert("RGBA")
    lado = int(W * 1.08 * z)
    f = foto.copy()
    fw, fh = f.size
    m = min(fw, fh)
    f = f.crop(((fw - m) // 2, (fh - m) // 2, (fw + m) // 2, (fh + m) // 2)).resize((lado, lado), Image.BILINEAR)
    tela.paste(f, (int((W - lado) / 2 + dx), int((H - lado) / 2 - 40 + dy)))
    return tela


# ---------------- textos sobre o vídeo ----------------
def desenhar_gancho(img, gancho, cfg, t):
    d = ImageDraw.Draw(img)
    a = gv.ease_out(gv.prog(t, 0, 0.3))
    if cfg["gancho"] == "tiktok":
        f = gv.fonte(cfg["fonte_gancho"], 60)
        y = 210 - int(20 * (1 - a))
        for ln in gv.quebrar(gancho, f, W - 160, 2):
            lw = f.getlength(ln)
            d.text(((W - lw) / 2, y), ln, font=f, fill=BRANCO, stroke_width=6, stroke_fill=PRETO)
            y += 76
    else:
        txt = gancho.upper() if cfg["fonte_gancho"] != "Lora-Italic.ttf" else gancho
        f = gv.texto_cabe(txt, cfg["fonte_gancho"], 70, W - 200)
        linhas = gv.quebrar(txt, f, W - 200, 2)
        larg = max(f.getlength(l) for l in linhas)
        alt = 92 * len(linhas) + 36
        x0, y0 = 80, 190
        largura = int((larg + 60) * a)
        if largura > 10:
            d.rectangle([x0, y0, x0 + largura, y0 + alt], fill=cfg["caixa"])
        if a > 0.85:
            y = y0 + 20
            for ln in linhas:
                d.text((x0 + 30, y), ln, font=f, fill=cfg["caixa_txt"])
                y += 92


def desenhar_legenda(img, blocos, t, cfg):
    bloco = None
    for b in blocos:
        if b[0][1] - 0.05 <= t <= b[-1][2] + 0.25:
            bloco = b
    if not bloco:
        return
    f = gv.F_BLACK(78)
    pal = [w[0] for w in bloco]
    esp = f.getlength(" ")
    larg = sum(f.getlength(p) for p in pal) + esp * (len(pal) - 1)
    while larg > W - 120 and f.size > 50:
        f = gv.F_BLACK(f.size - 6)
        esp = f.getlength(" ")
        larg = sum(f.getlength(p) for p in pal) + esp * (len(pal) - 1)
    pop = 0.85 + 0.15 * gv.ease_back(gv.prog(t, bloco[0][1] - 0.05, 0.18))
    cam = Image.new("RGBA", (int(larg + 60), f.size + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    x = 30
    for w in bloco:
        ativo = w[1] - 0.05 <= t
        cor = cfg["destaque"] if (w[1] - 0.05 <= t <= w[2] + 0.1) else BRANCO
        if not ativo:
            cor = BRANCO
        d.text((x, 20), w[0], font=f, fill=cor, stroke_width=7, stroke_fill=PRETO)
        x += f.getlength(w[0]) + esp
    cam = cam.resize((int(cam.width * pop), int(cam.height * pop)), Image.LANCZOS)
    img.alpha_composite(cam, ((W - cam.width) // 2, 1430 - cam.height // 2))


def desenhar_preco(img, p, t, ini, fim, cfg):
    if not (ini <= t <= fim):
        return
    e = gv.ease_back(gv.prog(t, ini, 0.3))
    if e <= 0.02:
        return
    s = Image.new("RGBA", (440, 230), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle([10, 10, 430, 220], 40, fill=BRANCO)
    antigo = "de " + gv.brl(p["preco_antigo"])
    f1 = gv.F_POP(40)
    lw = f1.getlength(antigo)
    d.text((220 - lw / 2, 30), antigo, font=f1, fill=(120, 120, 120))
    d.line([(220 - lw / 2 - 4, 58), (220 + lw / 2 + 4, 54)], fill=(230, 40, 40), width=5)
    novo = gv.brl(p["preco"])
    f2 = gv.texto_cabe(novo, "Inter-Black.otf", 96, 400)
    d.text((220 - f2.getlength(novo) / 2, 82), novo, font=f2, fill=(20, 20, 20))
    s = s.resize((int(440 * e), int(230 * e)), Image.LANCZOS).rotate(6, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(s, (W - 70 - s.width, 1120 - s.height // 2))


def desenhar_cta(img, t, ini, cfg):
    if t < ini:
        return
    d = ImageDraw.Draw(img)
    a = gv.ease_back(gv.prog(t, ini, 0.35))
    pul = 1 + 0.035 * math.sin((t - ini) * 9)
    pw, ph = int(780 * a * pul), int(130 * a * pul)
    if pw < 20:
        return
    cx, cy = W // 2, 1690
    d.rounded_rectangle([cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2], ph // 2,
                        fill=(37, 211, 102))  # verde do WhatsApp
    if a > 0.8:
        txt = "GRUPO DO WHATSAPP NA BIO"
        base = gv.texto_cabe(txt, "Inter-Black.otf", 60, 700)
        f = gv.F_BLACK(int(base.size * pul))
        gv.texto_centro(d, cy - f.size * 0.62, txt, f, BRANCO)
    # setinhas piscando (estilo dos exemplos)
    for i in range(3):
        if int((t - ini) * 6 + i) % 3 != 2:
            x, y = 70 + i * 34, 1780
            d.polygon([(x, y), (x + 26, y), (x + 13, y + 22)], fill=BRANCO)


# ---------------- montagem ----------------
def gerar(p, saida, estilo=None, musica=None, usar_voz=True):
    cat = estilo or p.get("categoria") or categoria(p["nome"])
    cfg = UGC[cat]
    gancho, falas = roteiro(p, cat)
    print(f"[{cat}] {p['nome'][:40]}…\n  gancho: {gancho}\n  fala: {' '.join(falas)}")

    fontes_img = p.get("imagens") or ([p["imagem"]] if p.get("imagem") else [])
    fotos = [i for i in (gv.carregar_imagem(u) for u in fontes_img[:5]) if i is not None]
    if not fotos:
        fotos = [gv.imagem_reserva(p["nome"], 1080)]
    if len(fotos) == 1:  # só 1 foto: cria "cortes" de detalhe pra o vídeo não ficar parado
        f0 = fotos[0]
        w, h = f0.size
        fotos += [f0.crop((int(w * .15), int(h * .15), int(w * .85), int(h * .85))),
                  f0.crop((0, 0, int(w * .7), int(h * .7))),
                  f0.crop((int(w * .3), int(h * .3), w, h))]
    prep = [preparar_foto(f) for f in fotos]

    with tempfile.TemporaryDirectory() as tmp:
        voz_mp3, palavras = narrar(falas, cfg["voz"], tmp, usar_voz)
        dur = max(10.0, palavras[-1][2] + 0.9)
        blocos = blocos_legenda(palavras)

        # momento em que fala o preço -> aparece a etiqueta
        ini_preco = next((w[1] for w in palavras if "R$" in w[0] or re.match(r"^\d+,\d\d", w[0])), dur * 0.3)
        # momento em que fala do Telegram -> aparece o botão
        ini_cta = next((w[1] for w in palavras if "grupo" in w[0].lower() or "link" in w[0].lower()), dur - 2.5)

        # trocas de foto: corte seco a cada ~2,2s (repete as fotos se precisar)
        n_cortes = max(1, round(dur / 2.2))
        seg = dur / n_cortes

        os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
        video_mudo = os.path.join(tmp, "v.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
               "-crf", "20", "-pix_fmt", "yuv420p", video_mudo]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for fr in range(int(dur * FPS)):
            t = fr / FPS
            k = min(int(t / seg), n_cortes - 1)
            foto, pr = fotos[k % len(fotos)], prep[k % len(prep)]
            q = quadro_foto(foto, pr, t - k * seg, seg, k)
            desenhar_gancho(q, gancho, cfg, t)
            desenhar_preco(q, p, t, ini_preco, ini_cta - 0.2, cfg)
            desenhar_legenda(q, blocos, t, cfg)
            desenhar_cta(q, t, ini_cta, cfg)
            proc.stdin.write(q.convert("RGB").tobytes())
        proc.stdin.close()
        proc.wait()

        # junta voz + música (música baixinha por baixo da voz)
        entradas, filtros, mix = ["-i", video_mudo], [], []
        n = 1
        if voz_mp3:
            entradas += ["-i", voz_mp3]
            filtros.append(f"[{n}:a]adelay=0|0,volume=1.0[voz]")
            mix.append("[voz]")
            n += 1
        if musica:
            entradas += ["-stream_loop", "-1", "-i", musica]
            vol = 0.12 if voz_mp3 else 0.8
            filtros.append(f"[{n}:a]volume={vol},afade=t=out:st={dur - 1:.2f}:d=1[mus]")
            mix.append("[mus]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error"] + entradas
        if mix:
            filtros.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0[a]")
            cmd += ["-filter_complex", ";".join(filtros), "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
        cmd += ["-c:v", "copy", "-t", f"{dur:.2f}", "-movflags", "+faststart", saida]
        subprocess.run(cmd, check=True)

    tags = ESTILOS[cat]["tags"]
    with open(saida.replace(".mp4", "_legenda.txt"), "w", encoding="utf-8") as f:
        f.write(f"{gancho[0].upper() + gancho[1:]} 😱\nLink no meu grupo do WhatsApp — tá na bio! 📲\n\n{tags}")
    print(f"  OK: {saida} ({dur:.1f}s){'' if voz_mp3 else ' [sem voz]'}")
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("produtos")
    ap.add_argument("--pasta", default="saida")
    ap.add_argument("--max", type=int, default=2, help="quantos vídeos gerar")
    ap.add_argument("--estilo", choices=list(UGC))
    ap.add_argument("--musica", default="musicas", help="mp3 ou pasta com várias músicas (sorteia uma por vídeo)")
    ap.add_argument("--sem-voz", action="store_true")
    a = ap.parse_args()

    with open(a.produtos, encoding="utf-8") as f:
        prods = json.load(f)[: a.max]
    hora = datetime.now().strftime("%Y%m%d_%H%M")
    def sortear_musica():
        if a.musica and os.path.isdir(a.musica):
            ops = [os.path.join(a.musica, m) for m in os.listdir(a.musica) if m.lower().endswith((".mp3", ".wav", ".m4a"))]
            return random.choice(ops) if ops else None
        return a.musica if a.musica and os.path.exists(a.musica) else None

    for i, p in enumerate(prods, 1):
        gerar(p, os.path.join(a.pasta, f"{hora}_ugc_{i}.mp4"), a.estilo, sortear_musica(), not a.sem_voz)
