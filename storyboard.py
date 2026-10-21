"""
Modo "vídeo com IA" pro YouTube Create (estilo achadinho do TikTok: mãos mostrando o produto).

  1. pega a foto do produto da Shopee
  2. gera um STORYBOARD 3x3 com IA (Google Gemini / Nano Banana) — opcional, precisa GEMINI_API_KEY
  3. monta o PROMPT do vídeo pronto pra colar no YouTube Create → Criar com IA
     (limites do YouTube Create: vídeo de até 10 s e prompt de até 900 caracteres)

Como o prompt é escolhido:
  - cada NICHO tem o seu jeito de apresentar (PERFIS)
  - dentro do nicho, o TIPO de produto (pijama, vestido, tênis, gloss, garrafa...) escolhe as cenas
    E os fundos — cada tipo só usa fundos que combinam com ele (pijama = cama/sofá, tênis = piso/calçada...)
  - roupa e calçado feminino usam fundos e mãos femininas; masculino usa os masculinos
  - o fundo entra num RODÍZIO: cada vídeo do mesmo tipo pega o próximo fundo (salvo em fundos_rodizio.json)

Sem GEMINI_API_KEY ele manda só a foto + o prompt do storyboard, pra você gerar no ChatGPT/Gemini.
"""
import base64
import io
import json
import os
import unicodedata

import requests

import gerar_video as gv

MODELO_IMAGEM = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
RODIZIO = "fundos_rodizio.json"
LIMITE_PROMPT = 900  # limite do YouTube Create

MAOS = {
    "fem": "Only female hands visible (nude manicure, thin gold rings), no face.",
    "masc": "Only male hands visible (short clean nails, black watch), no face.",
    "neutro": "Only hands visible, no face.",
}


def T(palavras, cenas, fem=None, masc=None, neutro=None):
    """Um tipo de produto: palavras do nome, 4 cenas e os fundos que combinam com ele."""
    return {"palavras": palavras, "cenas": cenas,
            "fundos": {"fem": fem, "masc": masc, "neutro": neutro or fem or masc}}


# =====================================================================
# MODA (feminina e masculina usam os mesmos tipos, com fundos de cada gênero)
# =====================================================================
MODA = [
    T(["pijama", "baby doll", "camisola", "pantufa"], [
        "hands open the clear package with the {p}",
        "hands stretch the top toward the camera, showing the print",
        "fingers smooth the soft fabric, close-up",
        "final flat-lay of the full {p}",
    ], fem=["white bouclé sofa with soft pillows", "pink satin bedsheet, cozy bed",
            "beige linen bed with fluffy pillows and a teddy bear"],
       masc=["navy blue bedsheet, cozy bed", "light gray sofa with a soft blanket",
             "dark gray cotton bedsheet with pillows"]),
    T(["vestido", "saia", "macacao", "jardineira"], [
        "hands unfold the {p} in one smooth motion",
        "hands hold it up to show the full length and cut",
        "the fabric sways and flows gently, close-up on texture",
        "final shot: the {p} laid out perfectly",
    ], fem=["bedroom with a tall mirror and a clothing rack", "white bed with linen sheets, morning light",
            "beige boutique fitting room with a velvet chair"]),
    T(["biquini", "maio", "saida de praia"], [
        "hands take the {p} out of a straw beach bag",
        "hands hold up each piece, showing the color",
        "close-up on fabric, straps and details",
        "final flat-lay with sunglasses and a towel",
    ], fem=["striped beach towel on wooden deck by the pool", "white sand with a straw hat and sunglasses",
            "light wooden deck with a beach bag"]),
    T(["bolsa", "mochila", "necessaire", "carteira"], [
        "hands pick up the {p} and turn it to show every side",
        "hands open the zipper and show the compartments",
        "hands place a phone and keys inside",
        "final shot: the {p} closed, hands adjusting the strap",
    ], fem=["white marble table with flowers and a perfume bottle", "light vanity table with jewelry",
            "beige boutique shelf with soft spotlights"],
       masc=["dark walnut desk with a notebook and pen", "black leather surface with car keys",
             "concrete table with sunglasses and a coffee cup"]),
    T(["relogio", "oculos", "colar", "brinco", "pulseira", "anel", "cinto", "bone"], [
        "hands open the box/pouch with the {p}",
        "hands rotate the {p} close to the camera, catching the light",
        "close-up on details and finish",
        "hands wear/hold it as if using it",
    ], fem=["white marble surface with flowers", "pink velvet jewelry tray", "light vanity table with a mirror"],
       masc=["dark walnut desk with a leather notebook", "black leather surface", "matte black table with a plant"]),
    T(["bermuda", "short", "calca", "cargo", "jeans"], [
        "hands unfold the {p} and hold it up",
        "hands stretch the waistband, showing comfort",
        "close-up on pockets, stitching and fabric",
        "final flat-lay with a matching top and sneakers",
    ], fem=["white bed with linen sheets", "light wooden floor with a cream rug", "bedroom with a clothing rack"],
       masc=["light concrete floor with sneakers", "gray bedsheet, minimalist bedroom", "streetwear setup with a skateboard"]),
]
MODA_PADRAO = T([], [
    "hands unfold the {p} slowly",
    "hands stretch it toward the camera, showing the front",
    "fingers smooth the fabric, close-up on texture",
    "final flat-lay of the {p}",
], fem=["white bouclé sofa", "beige linen bed", "bedroom with a clothing rack and mirror"],
   masc=["gray bedsheet, minimalist bedroom", "black leather sofa", "light concrete floor with sneakers"])

# =====================================================================
# PERFIS POR NICHO
# =====================================================================
PERFIS = {
    "moda_feminina": {"gen": "fem", "tipos": MODA, "padrao": MODA_PADRAO,
                      "clima": "cozy, cute aesthetic, satisfying unboxing"},
    "moda_masculina": {"gen": "masc", "tipos": MODA, "padrao": MODA_PADRAO,
                       "clima": "clean modern streetwear vibe"},
    "moda": {"gen": None, "tipos": MODA, "padrao": MODA_PADRAO, "clima": "clean aesthetic, satisfying unboxing"},

    "calcados": {"gen": None, "clima": "clean sneaker-showcase vibe", "tipos": [
        T(["tenis", "sapatenis", "bota"], [
            "hands open the shoebox and the tissue paper",
            "hands rotate one {p} close to the camera, side profile",
            "hands flip it to show the sole",
            "the pair side by side, hands aligning them",
        ], fem=["light wooden floor with a cream rug", "white bed with linen sheets", "pink-toned bedroom floor"],
           masc=["gray concrete floor", "urban sidewalk at golden hour", "dark wooden floor with a skateboard"]),
        T(["chinelo", "sandalia", "papete", "rasteira", "slide"], [
            "hands pick up one {p} from the pair",
            "hands squeeze the sole, showing how soft it is",
            "close-up on straps and texture",
            "the pair side by side, ready to wear",
        ], fem=["poolside light stone floor", "white bathroom floor with a fluffy rug", "light wooden deck"],
           masc=["poolside stone floor", "gray bathroom tiles", "light wooden deck with a towel"]),
    ], "padrao": T([], [
        "hands open the box with the {p}",
        "hands rotate it close to the camera",
        "hands show the sole and inside",
        "the pair side by side",
    ], fem=["light wooden floor"], masc=["gray concrete floor"])},

    "beleza": {"gen": "fem", "clima": "fresh, glowy beauty vibe, natural and confident",
               "camera": "Eye-level close-up, selfie/UGC style, the model looks at the camera.",
               "modelo": {"fem": "A young Brazilian woman with natural makeup uses the product and shows the result to the camera.",
                          "masc": "A young Brazilian man uses the product and shows the result to the camera.",
                          "neutro": "A young Brazilian woman with natural makeup uses the product and shows the result to the camera."},
               "tipos": [
        T(["gloss", "batom", "lip", "tint", "labial"], [
            "she holds the {p} next to her face and opens it",
            "close-up: she applies it on her lips",
            "she presses her lips and smiles, glossy result",
            "she shows the {p} and her lips side by side to the camera",
        ], fem=["bright bathroom with a round mirror", "pink vanity with a lighted mirror", "bedroom vanity with soft window light"]),
        T(["cilios"], [
            "she shows the box of {p} to the camera",
            "close-up: she applies the lash clusters in the mirror",
            "she blinks slowly, fluffy lashes in close-up",
            "she smiles at the camera holding the box",
        ], fem=["vanity with a lighted mirror", "bright bathroom mirror", "pink vanity table"]),
        T(["perfume", "body splash", "colonia"], [
            "the model takes the {p} out of the box",
            "she sprays it on the neck and wrist, mist in slow motion",
            "she smells the wrist and smiles",
            "she shows the bottle to the camera",
        ], fem=["bedroom with fresh flowers and soft light", "white marble vanity with flowers", "golden-hour window light"],
           masc=["modern bathroom with dark tiles", "bedroom with a dark wood dresser", "black marble counter"]),
        T(["secador", "escova", "chapinha", "modelador"], [
            "she shows the {p} to the camera",
            "she uses it on her hair, close-up of the result",
            "she runs her fingers through the smooth hair",
            "she flips her hair and smiles holding the {p}",
        ], fem=["bright bathroom with a mirror", "bedroom vanity with hair accessories", "salon-style mirror with soft light"]),
        T(["serum", "skincare", "creme", "hidratante", "protetor", "mascara facial"], [
            "she shows the {p} to the camera",
            "she applies a few drops on her face",
            "she spreads it gently, glowy skin close-up",
            "she smiles holding the {p}",
        ], fem=["bright bathroom with a round mirror", "white vanity with towels and plants", "bedroom with soft morning light"],
           masc=["modern bathroom mirror", "bright bathroom with gray tiles"]),
        T(["maquiagem", "base", "corretivo", "blush", "paleta", "rimel"], [
            "she shows the {p} to the camera",
            "she applies it in front of the mirror",
            "close-up of the result on her skin",
            "she smiles at the camera holding the {p}",
        ], fem=["vanity with a lighted mirror", "pink vanity table with brushes", "bright bathroom mirror"]),
    ], "padrao": T([], [
        "she shows the {p} to the camera",
        "she uses the {p}, close-up",
        "close-up of the result",
        "she smiles holding the {p}",
    ], fem=["bright bathroom with a mirror", "pink vanity table", "bedroom with soft window light"],
       masc=["modern bathroom mirror", "black marble counter"])},

    "casa": {"gen": None, "clima": "clean, organized, satisfying home vibe", "tipos": [
        T(["pote", "hermetico", "mantimento", "porta tempero"], [
            "messy groceries next to the empty {p}",
            "hands fill the {p} with grains and pasta",
            "hands close the lid and stack them",
            "final shot: a tidy, organized pantry",
        ], neutro=["organized pantry shelf in beige tones", "white marble kitchen countertop", "light wooden kitchen shelf"]),
        T(["organizador", "cesto", "prateleira", "estante", "gaveta"], [
            "a messy space next to the {p}",
            "hands arrange items into the {p}",
            "everything fits perfectly, close-up",
            "before vs after, clean and organized",
        ], neutro=["white kitchen cabinet", "light wooden shelf in a laundry room", "bathroom counter in beige tones"]),
        T(["garrafa", "jarra", "copo", "caneca", "termica", "squeeze"], [
            "hands pick up the {p}",
            "a drink poured into it in slow motion",
            "close-up on the lid and material",
            "the {p} styled with fruits or coffee",
        ], neutro=["light wooden kitchen countertop with lemons", "white marble countertop with a coffee",
                   "breakfast table with fresh fruit"]),
        T(["luminaria", "abajur", "fita led", "led", "luz"], [
            "the {p} in a dim room",
            "a hand turns it on, warm glow",
            "hands change the color/brightness",
            "the cozy room lit by the {p}",
        ], neutro=["bedroom nightstand in a dim room", "cozy living room at night", "bookshelf corner at night"]),
        T(["mop", "vassoura", "rodo", "limpeza", "esponja"], [
            "a dirty surface next to the {p}",
            "hands clean it in one satisfying pass",
            "close-up of the shiny clean result",
            "the {p} folded and stored",
        ], neutro=["light ceramic kitchen floor", "white bathroom tiles", "gray porcelain floor"]),
        T(["panela", "frigideira", "forma", "utensilio", "faca", "processador", "airfryer"], [
            "hands take the {p} out of the box",
            "the {p} in use, cooking something tasty",
            "close-up on material and finish",
            "the {p} on the counter with the finished food",
        ], neutro=["modern kitchen with a stovetop", "light wooden countertop with vegetables", "white marble kitchen island"]),
    ], "padrao": T([], [
        "hands pick up the {p}",
        "the {p} in use in a real everyday moment",
        "close-up on details",
        "the {p} styled, everything tidy",
    ], neutro=["white marble kitchen countertop", "light wooden table with a plant", "bright organized living room"])},

    "tecnologia": {"gen": None, "clima": "clean tech-review vibe, crisp details", "tipos": [
        T(["fone", "headset", "earbuds", "caixa de som"], [
            "hands open the box of the {p}",
            "hands show the {p} close to the camera",
            "it connects to a phone, LED lights up",
            "close-up on buttons and fit",
        ], neutro=["clean white desk with a laptop", "bed with a book and phone", "light wooden desk with a plant"]),
        T(["carregador", "power bank", "cabo", "suporte"], [
            "hands take the {p} out of the box",
            "hands plug it into a phone, charging icon on screen",
            "close-up on ports and finish",
            "the {p} in use on the setup",
        ], neutro=["bedside table with a lamp", "clean white desk", "car dashboard"]),
        T(["smartwatch", "relogio inteligente"], [
            "hands open the {p} box",
            "the screen turns on, close-up",
            "a finger swipes through the apps",
            "the {p} on the wrist",
        ], neutro=["clean white desk", "gym bench", "light wooden table with a coffee"]),
    ], "padrao": T([], [
        "hands open the box of the {p}",
        "hands rotate it close to the camera",
        "the {p} turns on, working",
        "the {p} in use on the setup",
    ], neutro=["clean white desk setup", "light wooden desk with a plant", "matte gray desk mat"])},

    "gamer": {"gen": None, "clima": "dark neon gaming vibe, energetic", "tipos": [], "padrao": T([], [
        "hands open the {p} box under RGB light",
        "hands show the {p} close to the camera",
        "RGB lights turn on in a wave",
        "hands use it as if gaming",
    ], neutro=["black desk mat with purple RGB glow", "gaming setup with LED strips", "dark desk with neon cyan light"])},

    "pet": {"gen": None, "clima": "cute, warm, funny pet vibe", "tipos": [
        T(["arranhador", "gato"], [
            "hands place the {p} on the floor",
            "a cat comes closer, curious",
            "the cat plays with the {p}",
            "happy cat resting next to it",
        ], neutro=["cozy living room rug", "light wooden floor by a window", "soft gray sofa corner"]),
    ], "padrao": T([], [
        "hands show the {p} to the camera",
        "a cute dog comes closer, curious",
        "the dog uses/plays with the {p}",
        "happy dog next to the {p}",
    ], neutro=["cozy living room rug", "backyard grass", "light wooden floor"])},

    "fitness": {"gen": None, "clima": "energetic, motivating workout vibe", "tipos": [], "padrao": T([], [
        "hands pick up the {p}",
        "hands show how it works",
        "a quick workout move with it (neck down)",
        "the {p} ready on the workout corner",
    ], neutro=["light gym floor with a yoga mat", "home workout corner with dumbbells", "outdoor park track"])},

    "geral": {"gen": None, "clima": "clean aesthetic product showcase", "tipos": [], "padrao": T([], [
        "hands pick up the {p}",
        "hands rotate it close to the camera",
        "the {p} in use",
        "the {p} styled on the background",
    ], neutro=["white marble surface", "light wooden table with a plant", "white textured sofa"])},
}

TEMPOS = ["0-2s", "2-5s", "5-8s", "8-10s"]

# =====================================================================
# Lógica
# =====================================================================
FEM = ["feminin", "mulher", "dama", "vestido", "saia", "cropped", "sutia", "calcinha", "biquini", "maio",
       "baby doll", "camisola", "salto", "rasteira", "sapatilha", "lingerie", "gloss", "batom", "cilios"]
MASC = ["masculin", "homem", "cueca", "barba"]


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def genero(p, nicho):
    """'fem', 'masc' ou 'neutro'. Nome com feminino E masculino (unissex) vira neutro."""
    n = _norm(p.get("nome", ""))
    f = any(k in n for k in FEM)
    m = any(k in n for k in MASC)
    if f != m:
        return "fem" if f else "masc"
    if f and m:
        return "neutro"
    return PERFIS.get(nicho, {}).get("gen") or "neutro"


def proximo_fundo(chave, lista):
    """Rodízio: cada tipo de produto pega o próximo fundo da SUA lista."""
    try:
        r = json.load(open(RODIZIO, encoding="utf-8"))
    except Exception:
        r = {}
    i = (r.get(chave, -1) + 1) % len(lista)
    r[chave] = i
    try:
        json.dump(r, open(RODIZIO, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    except Exception:
        pass
    return lista[i]


def _nicho(p, cat):
    for n in (p.get("cena"), cat):
        if n in PERFIS:
            return n
    return "geral"


def montar(p, cat):
    """Escolhe nicho, tipo, gênero, fundo (rodízio) e cenas do produto."""
    nicho = _nicho(p, cat)
    perfil = PERFIS[nicho]
    gen = genero(p, nicho)
    nome = _norm(p.get("nome", ""))
    tipo = next((t for t in perfil["tipos"] if any(_norm(k) in nome for k in t["palavras"])), perfil["padrao"])
    fundos = tipo["fundos"]
    lista = fundos.get(gen) or fundos.get("neutro") or fundos.get("fem") or fundos.get("masc")
    if gen == "neutro" and not fundos.get("neutro"):
        gen_maos = "fem" if fundos.get("fem") else "masc"
    else:
        gen_maos = gen
    chave = f"{nicho}|{(tipo['palavras'] or ['padrao'])[0]}|{gen}"
    curto = p.get("nome_curto") or nome_curto_simples(p["nome"])
    pessoa = (perfil.get("modelo") or {}).get(gen) or MAOS[gen_maos]
    return {
        "nicho": nicho, "genero": gen, "fundo": proximo_fundo(chave, lista), "maos": pessoa,
        "camera": perfil.get("camera", "Overhead shot."),
        "cenas": [c.format(p=curto) for c in tipo["cenas"]], "clima": perfil["clima"], "curto": curto,
    }


def prompt_storyboard(p, cat, m):
    quadros = "; ".join(f"{i + 1}) {c}" for i, c in enumerate(m["cenas"]))
    return (
        f"Create a 3x3 storyboard grid (9 frames) for a vertical 9:16 product video of the product in the photo: "
        f"\"{p['nome']}\". {m['camera']} Background: {m['fundo']}. {m['maos']} "
        f"Sequence: {quadros}; extra frames are in-between moments. "
        f"Photorealistic, smartphone look, natural light. Keep the product IDENTICAL to the photo "
        f"(colors, print, shape). No text."
    )


def prompt_video(p, cat, m):
    """Prompt pro YouTube Create: 10 s, vertical, até 900 caracteres."""
    cenas = " ".join(f"{TEMPOS[i]}: {c}." for i, c in enumerate(m["cenas"]))
    partes = [
        "Vertical 9:16, 10 seconds, follow the storyboard.",
        f"Product: {m['curto']}, identical to the reference image.",
        f"{m['camera']} Background: {m['fundo']}.",
        m["maos"],
        cenas,
        f"Smooth natural movements, soft natural light, {m['clima']}.",
        "Audio: soft lo-fi music and gentle ASMR sounds, no speech.",
        "No text, no logos.",
    ]
    texto = " ".join(partes)
    if len(texto) > LIMITE_PROMPT:  # corta o que é menos importante primeiro
        partes.pop(6)
        texto = " ".join(partes)
    return texto[:LIMITE_PROMPT]


def nome_curto_simples(nome):
    import gerar_video_ugc as u
    return u.nome_curto(nome)


def baixar_foto(p):
    img = gv.carregar_imagem(p.get("imagem") or (p.get("imagens") or [None])[0])
    if img is None:
        return None
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def gerar_storyboard(foto_jpg, prompt):
    """Chama o Gemini (Nano Banana) e devolve os bytes da imagem do storyboard (ou None)."""
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave or not foto_jpg:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO_IMAGEM}:generateContent"
    corpo = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(foto_jpg).decode()}},
            {"text": prompt},
        ]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}},
    }
    r = requests.post(url, json=corpo, headers={"x-goog-api-key": chave}, timeout=180)
    if not r.ok:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
    for cand in r.json().get("candidates", []):
        for parte in cand.get("content", {}).get("parts", []):
            dado = parte.get("inline_data") or parte.get("inlineData")
            if dado and dado.get("data"):
                return base64.b64decode(dado["data"])
    raise RuntimeError("Gemini não devolveu imagem")


def kit(p, cat):
    """Monta tudo que vai pro Telegram neste modo."""
    foto = baixar_foto(p)
    m = montar(p, cat)
    ps, pv = prompt_storyboard(p, cat, m), prompt_video(p, cat, m)
    story, erro = None, None
    try:
        story = gerar_storyboard(foto, ps)
    except Exception as e:
        erro = str(e)
    return {"foto": foto, "storyboard": story, "prompt_storyboard": ps, "prompt_video": pv, "erro": erro,
            "nicho": m["nicho"], "genero": m["genero"], "fundo": m["fundo"]}
