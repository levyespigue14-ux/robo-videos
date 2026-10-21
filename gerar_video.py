"""
Gerador de vídeos de achadinhos da Shopee para TikTok / Reels / Shopee Vídeo.

É um bot SEPARADO do bot de promoções do Telegram: só lê uma lista de produtos
(JSON), separa por categoria (tecnologia, moda, calçados, casa, beleza, geral)
e gera um vídeo vertical 1080x1920 por categoria, cada um com seu estilo,
terminando com a chamada pro canal do Telegram.

Uso:
    python gerar_video.py produtos.json                     # um vídeo por categoria
    python gerar_video.py produtos.json --estilo tecnologia # força um estilo
    python gerar_video.py produtos.json --musica som.mp3

Formato do produtos.json (lista):
    [{"nome": "...", "preco_antigo": 138.14, "preco": 9.67, "desconto": 93,
      "nota": 4.8, "vendidos": "4526+", "imagem": "url ou caminho",
      "link": "https://s.shopee.com.br/...", "categoria": "opcional"}]

Requisitos: pip install pillow requests  +  ffmpeg (apt install ffmpeg)
"""
import argparse
import io
import json
import math
import os
import random
import subprocess
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from estilos import ESTILOS, agrupar

W, H = 1080, 1920
FPS = 30
TELEGRAM = "t.me/levylly_shop"
ARROBA = "@levylly_shop"

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTES = os.path.join(AQUI, "fonts")
BRANCO = (255, 255, 255)

DUR_INTRO = 1.8
DUR_PRODUTO = 2.7
DUR_OUTRO = 2.8

_cache_fontes = {}


def fonte(nome, tamanho):
    chave = (nome, int(tamanho))
    if chave not in _cache_fontes:
        _cache_fontes[chave] = ImageFont.truetype(os.path.join(FONTES, nome), int(tamanho))
    return _cache_fontes[chave]


F_BLACK = lambda s: fonte("Inter-Black.otf", s)
F_XBOLD = lambda s: fonte("Inter-ExtraBold.otf", s)
F_SERIF = lambda s: fonte("Lora-Italic.ttf", s)
F_POP = lambda s: fonte("Poppins-Bold.ttf", s)
F_POPM = lambda s: fonte("Poppins-Medium.ttf", s)


# ---------------- utilidades ----------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_back(t):
    t = clamp(t)
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


def prog(t, inicio, dur):
    return clamp((t - inicio) / dur)


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mistura(c1, c2, a):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * a) for i in range(3))


def quebrar(texto, f, largura, max_linhas=2):
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if f.getlength(teste) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
            if len(linhas) == max_linhas:
                break
    if len(linhas) < max_linhas and atual:
        linhas.append(atual)
    linhas = linhas[:max_linhas]
    if len(" ".join(linhas)) < len(" ".join(texto.split())):
        ult = linhas[-1]
        while f.getlength(ult + "…") > largura and " " in ult:
            ult = ult.rsplit(" ", 1)[0]
        linhas[-1] = ult + "…"
    return linhas


def texto_centro(d, y, txt, f, cor, cx=W // 2):
    larg = f.getlength(txt)
    d.text((cx - larg / 2, y), txt, font=f, fill=cor)
    return larg


def pop_texto(base, txt, f, cor, centro, escala, rot=0, contorno=None):
    """Texto numa camada própria colada com zoom/rotação (efeito 'pop')."""
    if escala <= 0.01:
        return
    bbox = f.getbbox(txt)
    tw, th = bbox[2] - bbox[0] + 60, bbox[3] - bbox[1] + 60
    cam = Image.new("RGBA", (int(tw), int(th)), (0, 0, 0, 0))
    kw = {"stroke_width": contorno[0], "stroke_fill": contorno[1]} if contorno else {}
    ImageDraw.Draw(cam).text((30 - bbox[0], 30 - bbox[1]), txt, font=f, fill=cor, **kw)
    cam = cam.resize((max(1, int(tw * escala)), max(1, int(th * escala))), Image.LANCZOS)
    if rot:
        cam = cam.rotate(rot, resample=Image.BICUBIC, expand=True)
    base.alpha_composite(cam, (int(centro[0] - cam.width / 2), int(centro[1] - cam.height / 2)))


def estrela(d, cx, cy, r, cor):
    pts = [(cx + (r if k % 2 == 0 else r * 0.45) * math.cos(-math.pi / 2 + k * math.pi / 5),
            cy + (r if k % 2 == 0 else r * 0.45) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]
    d.polygon(pts, fill=cor)


def texto_cabe(txt, nome_fonte, tamanho, largura_max):
    while tamanho > 40 and fonte(nome_fonte, tamanho).getlength(txt) > largura_max:
        tamanho -= 6
    return fonte(nome_fonte, tamanho)


# ---------------- imagens dos produtos ----------------
def carregar_imagem(origem):
    if not origem:
        return None
    try:
        if str(origem).startswith("http"):
            import requests

            r = requests.get(origem, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        return Image.open(origem).convert("RGB")
    except Exception as e:
        print(f"  ! não carregou a imagem {origem}: {e}")
        return None


def imagem_reserva(nome, tam=820):
    img = Image.new("RGB", (tam, tam))
    d = ImageDraw.Draw(img)
    for i in range(tam):
        c = int(250 - 30 * i / tam)
        d.line([(0, i), (tam, i)], fill=(c, c - 8, c - 18))
    iniciais = "".join(p[0] for p in nome.split()[:2]).upper()
    texto_centro(d, tam // 2 - 110, iniciais, F_BLACK(130), (200, 120, 90), cx=tam // 2)
    texto_centro(d, tam // 2 + 70, "foto do produto", F_POPM(44), (170, 150, 140), cx=tam // 2)
    return img


def cartao_produto(img, tam=820, borda=22, raio=48):
    w, h = img.size
    lado = min(w, h)
    img = img.crop(((w - lado) // 2, (h - lado) // 2, (w + lado) // 2, (h + lado) // 2)).resize((tam, tam), Image.LANCZOS)
    total = tam + 2 * borda
    card = Image.new("RGBA", (total + 80, total + 80), (0, 0, 0, 0))
    sombra = Image.new("L", card.size, 0)
    ImageDraw.Draw(sombra).rounded_rectangle([50, 60, 50 + total, 60 + total], raio + borda, fill=140)
    card.paste((0, 0, 0, 255), (0, 0), sombra.filter(ImageFilter.GaussianBlur(22)))
    ImageDraw.Draw(card).rounded_rectangle([40, 40, 40 + total, 40 + total], raio + borda, fill=BRANCO)
    masc = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(masc).rounded_rectangle([0, 0, tam, tam], raio, fill=255)
    card.paste(img, (40 + borda, 40 + borda), masc)
    return card


# ---------------- fundos ----------------
def fundo(cor, cor_padrao, padrao, t):
    img = Image.new("RGBA", (W, H), cor)
    d = ImageDraw.Draw(img)
    if padrao == "listras":
        desloc = int(t * 120) % 240
        for x in range(-H, W + H, 240):
            xx = x + desloc
            d.polygon([(xx, 0), (xx + 110, 0), (xx + 110 - H * 0.35, H), (xx - H * 0.35, H)], fill=cor_padrao)
    elif padrao == "grade":
        desloc = int(t * 60) % 90
        for x in range(0, W + 90, 90):
            d.line([(x, 0), (x, H)], fill=cor_padrao, width=2)
        for y in range(-90, H + 90, 90):
            d.line([(0, y + desloc), (W, y + desloc)], fill=cor_padrao, width=2)
        # cantos tipo "mira"
        for (x, y, sx, sy) in [(40, 40, 1, 1), (W - 40, 40, -1, 1), (40, H - 40, 1, -1), (W - 40, H - 40, -1, -1)]:
            d.line([(x, y), (x + 70 * sx, y)], fill=cor_padrao[:3] if False else mistura(cor_padrao, BRANCO, 0.5), width=6)
            d.line([(x, y), (x, y + 70 * sy)], fill=mistura(cor_padrao, BRANCO, 0.5), width=6)
    elif padrao == "bolinhas":
        desloc = int(t * 40) % 120
        for yy, y in enumerate(range(-120, H + 120, 120)):
            for x in range(-120, W + 120, 120):
                xo = x + (60 if yy % 2 else 0)
                d.ellipse([xo - 16, y + desloc - 16, xo + 16, y + desloc + 16], fill=cor_padrao)
    elif padrao == "moldura":
        d.rectangle([36, 36, W - 36, H - 36], outline=cor_padrao, width=6)
        d.rectangle([56, 56, W - 56, H - 56], outline=cor_padrao, width=2)
    return img


# ---------------- cenas ----------------
def cena_intro(t, e, data_txt):
    img = Image.new("RGBA", (W, H), e["fundo_intro"])
    d = ImageDraw.Draw(img)
    tx = e["texto_intro"]

    # cabeçalho de revista
    p = ease_out(prog(t, 0, 0.35))
    y0 = int(-120 + 230 * p)
    fd = fonte(e["fonte_detalhe"], 36)
    d.rectangle([60, y0, W - 60, y0 + 6], fill=tx)
    d.text((60, y0 + 24), f"EDIÇÃO DE HOJE · {data_txt}", font=fd, fill=tx)
    d.text((W - 60 - fd.getlength(ARROBA), y0 + 24), ARROBA, font=fd, fill=e["serif_cor"])
    d.rectangle([60, y0 + 92, W - 60, y0 + 96], fill=tx)

    # título gigante
    y = 800
    for i, pal in enumerate(e["titulo"].upper().split()):
        es = ease_back(prog(t, 0.15 + i * 0.12, 0.35))
        f = texto_cabe(pal, "Inter-Black.otf", 230, W - 120)
        pop_texto(img, pal, f, tx, (W // 2, y), es, rot=-3 if i % 2 else 2)
        y += int(f.size * 1.0)

    es = ease_back(prog(t, 0.45, 0.35))
    f = texto_cabe(e["palavra_serif"], "Lora-Italic.ttf", 170, W - 140)
    pop_texto(img, e["palavra_serif"], f, e["serif_cor"], (W // 2, y + 50), es, rot=-4)

    p = ease_out(prog(t, 0.7, 0.4))
    if p > 0:
        fy = y + 250
        d.rectangle([80, fy, 80 + int((W - 160) * p), fy + 120], fill=e["faixa"])
        if p > 0.9:
            f = texto_cabe(e["subtitulo"].upper(), "Inter-ExtraBold.otf", 64, W - 220)
            texto_centro(d, fy + 60 - f.size * 0.62, e["subtitulo"].upper(), f, e["faixa_txt"])

    # rodapé de revista
    p = ease_out(prog(t, 0.9, 0.4))
    if p > 0:
        fd = fonte(e["fonte_detalhe"], 40)
        yb = int(H - 200 + 80 * (1 - p))
        d.rectangle([60, yb, W - 60, yb + 4], fill=tx)
        d.text((60, yb + 24), "PREÇOS DE HOJE", font=fd, fill=tx)
        txt = "arrasta pra ver ➜".replace(" ➜", "") + " >>"
        d.text((W - 60 - fd.getlength(txt), yb + 24), txt, font=fd, fill=e["serif_cor"])
    return img


def perto(c1, c2):
    return sum(abs(a - b) for a, b in zip(c1, c2)) < 120


def cena_produto(t, prod, card, idx, total, e):
    bg, cor_padrao, tx = e["cenas"][idx % len(e["cenas"])]
    # se a cor de destaque some no fundo desta cena, troca por cores que contrastam
    e = dict(e)
    if perto(e["num_fundo"], bg):
        e["num_fundo"], e["num_txt"] = tx, bg
    if perto(e["destaque"], bg):
        e["destaque"], e["contorno"] = tx, mistura(bg, (0, 0, 0), 0.45)
    img = fundo(bg, cor_padrao, e["padrao"], t)
    d = ImageDraw.Draw(img)
    fd = lambda s: fonte(e["fonte_detalhe"], s)

    # número do achadinho
    d.rounded_rectangle([70, 110, 290, 220], 30, fill=e["num_fundo"])
    texto_centro(d, 118, f"#{idx + 1}", F_BLACK(80), e["num_txt"], cx=180)
    d.text((310, 140), f"de {total}", font=fd(48), fill=tx)

    # cartão com zoom lento + entrada lateral
    entra = ease_out(prog(t, 0, 0.35))
    zoom = (1.06 - 0.06 * prog(t, 0, DUR_PRODUTO)) * 0.92
    lado = -1 if idx % 2 else 1
    rot = 3 * lado * (1 - entra) + 1.5 * lado
    c = card.resize((int(card.width * zoom), int(card.height * zoom)), Image.LANCZOS)
    c = c.rotate(rot, resample=Image.BICUBIC, expand=True)
    cx = int(W / 2 + (1 - entra) * W * lado)
    img.alpha_composite(c, (cx - c.width // 2, 700 - c.height // 2))

    # selo de desconto
    es = ease_back(prog(t, 0.35, 0.35))
    if es > 0.02:
        selo = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        sd = ImageDraw.Draw(selo)
        pontas = [(150 + (140 if k % 2 == 0 else 118) * math.cos(k * math.pi / 16),
                   150 + (140 if k % 2 == 0 else 118) * math.sin(k * math.pi / 16)) for k in range(32)]
        sd.polygon(pontas, fill=e["selo"])
        txt = f"-{int(prod['desconto'])}%"
        f = texto_cabe(txt, "Inter-Black.otf", 84, 200)
        sd.text((150 - f.getlength(txt) / 2, 150 - f.size * 0.62), txt, font=f, fill=e["selo_txt"])
        selo = selo.resize((max(1, int(300 * es)), max(1, int(300 * es))), Image.LANCZOS)
        selo = selo.rotate(-12 + 8 * math.sin(t * 4), resample=Image.BICUBIC, expand=True)
        img.alpha_composite(selo, (W - 160 - selo.width // 2, 330 - selo.height // 2))

    # nome
    p = ease_out(prog(t, 0.25, 0.35))
    if p > 0:
        y = int(1185 + 60 * (1 - p))
        for ln in quebrar(prod["nome"], F_XBOLD(56), W - 160, 2):
            texto_centro(d, y, ln, F_XBOLD(56), tx)
            y += 70

    # preço antigo riscado
    p = ease_out(prog(t, 0.5, 0.3))
    if p > 0:
        lw = texto_centro(d, 1362, "de " + brl(prod["preco_antigo"]), fd(54), mistura(tx, bg, 0.3))
        x0 = W / 2 - lw / 2
        d.line([(x0 - 6, 1402), (x0 - 6 + (lw + 12) * p, 1394)], fill=e["destaque"] if e["destaque"] != bg else tx, width=8)

    # preço novo
    es = ease_back(prog(t, 0.75, 0.35))
    txt = "por " + brl(prod["preco"])
    pop_texto(img, txt, texto_cabe(txt, "Inter-Black.otf", 150, W - 120), e["destaque"], (W // 2, 1540), es,
              rot=-2, contorno=(10, e["contorno"]))

    # nota e vendidos
    p = ease_out(prog(t, 1.1, 0.3))
    if p > 0 and prod.get("nota"):
        txt = f"{prod['nota']}   ·   {prod.get('vendidos', '')} vendidos"
        yy = int(1690 + 30 * (1 - p))
        lw = fd(44).getlength(txt)
        x0 = W / 2 - (lw + 56) / 2
        estrela(d, x0 + 20, yy + 30, 22, e["num_fundo"])
        d.text((x0 + 56, yy), txt, font=fd(44), fill=tx)

    # barra de progresso
    frac = (idx + prog(t, 0, DUR_PRODUTO)) / total
    d.rectangle([0, 0, W, 14], fill=(0, 0, 0))
    d.rectangle([0, 0, int(W * frac), 14], fill=e["num_fundo"])
    return img


def cena_outro(t, e):
    img = Image.new("RGBA", (W, H), e["fundo_outro"])
    d = ImageDraw.Draw(img)
    dest, acento = e["outro_destaque"], e["outro_acento"]

    pop_texto(img, "O LINK DE", F_BLACK(130), BRANCO if dest != BRANCO else acento, (W // 2, 520),
              ease_back(prog(t, 0, 0.35)), rot=-2)
    pop_texto(img, "TODOS ELES", F_BLACK(150), dest, (W // 2, 680), ease_back(prog(t, 0.12, 0.35)), rot=2)
    pop_texto(img, "tá no meu Telegram", F_SERIF(110), acento, (W // 2, 840), ease_back(prog(t, 0.24, 0.35)), rot=-3)

    p = ease_out(prog(t, 0.5, 0.4))
    if p > 0:
        pulso = 1 + 0.04 * math.sin(t * 9) if t > 0.9 else p
        pw, ph = int(860 * pulso), int(170 * pulso)
        x0, y0 = W // 2 - pw // 2, 1040 - ph // 2
        d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], ph // 2, fill=e["pilula"])
        f = F_BLACK(int(78 * pulso))
        texto_centro(d, 1040 - f.size * 0.62, TELEGRAM, f, e["pilula_txt"])

    p = ease_out(prog(t, 0.8, 0.4))
    if p > 0:
        texto_centro(d, 1210, "promoções novas todo dia", F_POPM(56), BRANCO)
        texto_centro(d, 1290, "só produto bem avaliado", F_POPM(56), mistura(BRANCO, e["fundo_outro"], 0.35))

    if t > 1.1:
        dy = int(18 * math.sin(t * 8))
        texto_centro(d, 1500, "LINK NA BIO", F_BLACK(96), dest)
        cx, cy = W // 2, 1690 + dy
        d.polygon([(cx - 70, cy - 40), (cx + 70, cy - 40), (cx, cy + 50)], fill=dest)
    return img


def flash(img, forca):
    if forca <= 0:
        return img
    return Image.alpha_composite(img, Image.new("RGBA", (W, H), (255, 255, 255, int(255 * forca))))


# ---------------- montagem ----------------
def gerar(produtos, saida, estilo="geral", musica=None):
    e = ESTILOS[estilo]
    data_txt = datetime.now().strftime("%d/%m")
    cards = [cartao_produto(carregar_imagem(p.get("imagem")) or imagem_reserva(p["nome"])) for p in produtos]

    cenas = [("intro", DUR_INTRO, None)] + [("produto", DUR_PRODUTO, i) for i in range(len(produtos))]
    cenas += [("outro", DUR_OUTRO, None)]
    duracao = sum(c[1] for c in cenas)

    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if musica:
        cmd += ["-stream_loop", "-1", "-i", musica, "-shortest", "-c:a", "aac", "-b:a", "160k",
                "-af", f"afade=t=out:st={duracao - 1:.2f}:d=1"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", saida]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    random.seed(1)
    for tipo, dur, i in cenas:
        for k in range(int(dur * FPS)):
            t = k / FPS
            if tipo == "intro":
                q = cena_intro(t, e, data_txt)
            elif tipo == "produto":
                q = cena_produto(t, produtos[i], cards[i], i, len(produtos), e)
            else:
                q = cena_outro(t, e)
            if k < 4 and tipo != "intro":  # corte com flash + tremida
                q = flash(q, 0.85 - k * 0.22)
                dx, dy = random.randint(-14, 14), random.randint(-14, 14)
                q = q.transform(q.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), fillcolor=(0, 0, 0))
            proc.stdin.write(q.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"OK [{estilo}]: {saida} ({duracao:.1f}s, {len(produtos)} produtos)")
    return saida


def legenda(produtos, estilo):
    e = ESTILOS[estilo]
    menor = min(p["preco"] for p in produtos)
    return (f"{e['titulo'].capitalize()} {e['palavra_serif']} a partir de {brl(menor)} 😱\n"
            f"O link de todos está no meu Telegram ({ARROBA}) — link na bio!\n\n{e['tags']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("produtos", help="arquivo JSON com a lista de produtos")
    ap.add_argument("--pasta", default="saida")
    ap.add_argument("--estilo", choices=list(ESTILOS), help="força um estilo (senão, separa por categoria)")
    ap.add_argument("--musica", help="mp3 opcional (sem música: adicione um som do próprio TikTok)")
    ap.add_argument("--max", type=int, default=5, help="produtos por vídeo")
    ap.add_argument("--min", type=int, default=3, help="mínimo de produtos pra fazer o vídeo da categoria")
    a = ap.parse_args()

    with open(a.produtos, encoding="utf-8") as f:
        todos = json.load(f)
    grupos = {a.estilo: todos} if a.estilo else agrupar(todos)

    hoje = datetime.now().strftime("%Y%m%d_%H%M")
    for estilo, prods in grupos.items():
        if len(prods) < a.min:
            print(f"- pulando {estilo}: só {len(prods)} produto(s)")
            continue
        prods = prods[: a.max]
        saida = os.path.join(a.pasta, f"{hoje}_{estilo}.mp4")
        gerar(prods, saida, estilo, a.musica)
        with open(saida.replace(".mp4", "_legenda.txt"), "w", encoding="utf-8") as f:
            f.write(legenda(prods, estilo))
