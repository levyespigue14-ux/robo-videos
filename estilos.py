"""
Estilos visuais por tipo de produto + detecção automática da categoria pelo nome.

Para criar um estilo novo: copie um bloco de ESTILOS, mude as cores/textos
e adicione palavras-chave em PALAVRAS.
"""
import unicodedata

ESTILOS = {
    "tecnologia": {
        "titulo": "achadinhos",
        "palavra_serif": "tech",
        "subtitulo": "pro seu setup",
        "fundo_intro": (11, 15, 26), "texto_intro": (255, 255, 255), "serif_cor": (0, 229, 255),
        "faixa": (0, 229, 255), "faixa_txt": (11, 15, 26),
        # duas paletas que alternam entre os produtos: (fundo, cor do padrão, cor do texto)
        "cenas": [((11, 15, 26), (24, 34, 58), (255, 255, 255)),
                  ((18, 10, 38), (40, 22, 80), (255, 255, 255))],
        "padrao": "grade",
        "destaque": (198, 255, 0), "contorno": (0, 0, 0), "selo": (0, 229, 255), "selo_txt": (0, 0, 0),
        "num_fundo": (198, 255, 0), "num_txt": (0, 0, 0),
        "fonte_detalhe": "DejaVuSansMono-Bold.ttf",
        "fundo_outro": (11, 15, 26), "outro_destaque": (198, 255, 0), "outro_acento": (0, 229, 255),
        "pilula": (0, 229, 255), "pilula_txt": (0, 0, 0),
        "tags": "#tech #gadgets #setup #achadinhos #shopee #achadinhosdashopee #tecnologia",
    },
    "moda": {
        "titulo": "achadinhos",
        "palavra_serif": "de moda",
        "subtitulo": "looks baratinhos",
        "fundo_intro": (246, 239, 233), "texto_intro": (20, 20, 20), "serif_cor": (200, 85, 61),
        "faixa": (20, 20, 20), "faixa_txt": (246, 239, 233),
        "cenas": [((246, 239, 233), (236, 224, 214), (20, 20, 20)),
                  ((200, 85, 61), (186, 74, 52), (255, 255, 255))],
        "padrao": "moldura",
        "destaque": (20, 20, 20), "contorno": (255, 255, 255), "selo": (20, 20, 20), "selo_txt": (246, 239, 233),
        "num_fundo": (20, 20, 20), "num_txt": (246, 239, 233),
        "fonte_detalhe": "Poppins-Medium.ttf",
        "fundo_outro": (20, 20, 20), "outro_destaque": (246, 239, 233), "outro_acento": (226, 120, 95),
        "pilula": (200, 85, 61), "pilula_txt": (255, 255, 255),
        "tags": "#moda #lookdodia #achadinhos #shopee #achadinhosdashopee #modafeminina #modamasculina",
    },
    "calcados": {
        "titulo": "tênis &",
        "palavra_serif": "calçados",
        "subtitulo": "pra pisar bonito",
        "fundo_intro": (245, 245, 240), "texto_intro": (15, 15, 15), "serif_cor": (230, 57, 70),
        "faixa": (230, 57, 70), "faixa_txt": (255, 255, 255),
        "cenas": [((15, 15, 15), (32, 32, 32), (255, 255, 255)),
                  ((230, 57, 70), (210, 45, 58), (255, 255, 255))],
        "padrao": "listras",
        "destaque": (255, 255, 255), "contorno": (15, 15, 15), "selo": (255, 255, 255), "selo_txt": (230, 57, 70),
        "num_fundo": (255, 255, 255), "num_txt": (15, 15, 15),
        "fonte_detalhe": "Poppins-Bold.ttf",
        "fundo_outro": (15, 15, 15), "outro_destaque": (255, 255, 255), "outro_acento": (230, 57, 70),
        "pilula": (230, 57, 70), "pilula_txt": (255, 255, 255),
        "tags": "#tenis #sneakers #calçados #achadinhos #shopee #achadinhosdashopee #streetwear",
    },
    "casa": {
        "titulo": "achadinhos",
        "palavra_serif": "pra casa",
        "subtitulo": "cozinha e organização",
        "fundo_intro": (232, 239, 228), "texto_intro": (47, 93, 80), "serif_cor": (214, 150, 40),
        "faixa": (47, 93, 80), "faixa_txt": (255, 255, 255),
        "cenas": [((232, 239, 228), (220, 230, 214), (47, 93, 80)),
                  ((47, 93, 80), (56, 106, 92), (255, 255, 255))],
        "padrao": "bolinhas",
        "destaque": (214, 150, 40), "contorno": (255, 255, 255), "selo": (214, 150, 40), "selo_txt": (255, 255, 255),
        "num_fundo": (214, 150, 40), "num_txt": (255, 255, 255),
        "fonte_detalhe": "Poppins-Medium.ttf",
        "fundo_outro": (47, 93, 80), "outro_destaque": (255, 255, 255), "outro_acento": (240, 190, 90),
        "pilula": (214, 150, 40), "pilula_txt": (255, 255, 255),
        "tags": "#casa #cozinha #organização #achadinhos #shopee #achadinhosdashopee #utilidades",
    },
    "beleza": {
        "titulo": "achadinhos",
        "palavra_serif": "de beleza",
        "subtitulo": "skincare e perfumes",
        "fundo_intro": (255, 227, 236), "texto_intro": (90, 20, 50), "serif_cor": (214, 51, 132),
        "faixa": (214, 51, 132), "faixa_txt": (255, 255, 255),
        "cenas": [((255, 227, 236), (255, 212, 226), (90, 20, 50)),
                  ((214, 51, 132), (196, 40, 118), (255, 255, 255))],
        "padrao": "bolinhas",
        "destaque": (214, 51, 132), "contorno": (255, 255, 255), "selo": (201, 162, 39), "selo_txt": (255, 255, 255),
        "num_fundo": (214, 51, 132), "num_txt": (255, 255, 255),
        "fonte_detalhe": "Poppins-Medium.ttf",
        "fundo_outro": (90, 20, 50), "outro_destaque": (255, 227, 236), "outro_acento": (255, 140, 190),
        "pilula": (214, 51, 132), "pilula_txt": (255, 255, 255),
        "tags": "#beleza #skincare #perfume #achadinhos #shopee #achadinhosdashopee #make",
    },
    "geral": {
        "titulo": "achadinhos",
        "palavra_serif": "da Shopee",
        "subtitulo": "que valem a pena",
        "fundo_intro": (255, 244, 232), "texto_intro": (17, 17, 17), "serif_cor": (238, 77, 45),
        "faixa": (17, 17, 17), "faixa_txt": (255, 214, 10),
        "cenas": [((238, 77, 45), (226, 66, 36), (255, 255, 255)),
                  ((17, 17, 17), (28, 28, 28), (255, 255, 255))],
        "padrao": "listras",
        "destaque": (255, 214, 10), "contorno": (17, 17, 17), "selo": (255, 214, 10), "selo_txt": (17, 17, 17),
        "num_fundo": (255, 214, 10), "num_txt": (17, 17, 17),
        "fonte_detalhe": "Poppins-Bold.ttf",
        "fundo_outro": (17, 17, 17), "outro_destaque": (255, 214, 10), "outro_acento": (238, 77, 45),
        "pilula": (238, 77, 45), "pilula_txt": (255, 255, 255),
        "tags": "#achadinhos #shopee #achadinhosdashopee #promoção #comprinhas #achados",
    },
}

# A ordem importa: calçados antes de moda, tecnologia antes do resto.
PALAVRAS = [
    ("calcados", ["tenis", "sandalia", "chinelo", "sapato", "bota", "papete", "sapatenis",
                  "rasteira", "crocs", "babuche", "mocassim", "sapatilha", "slide"]),
    ("tecnologia", ["cabo", "carregador", "fone", "bluetooth", "usb", "tipo-c", "tipo c", "caixa de som",
                    "suporte de celular", "suporte celular", "capa", "iphone", "adaptador", "smartwatch",
                    "relogio inteligente", "mouse", "teclado", "gamer", "power bank", "headset",
                    "controle", "camera", "ring light", "hub", "pendrive"]),
    ("beleza", ["perfume", "cilios", "serum", "maquiagem", "batom", "skincare", "skin care", "creme",
                "hidratante", "shampoo", "unha", "esmalte", "rimel", "pincel", "base liquida", "protetor solar"]),
    ("casa", ["garrafa", "cozinha", "panela", "pote", "organizador", "toalha", "lencol", "luminaria",
              "tapete", "copo", "caneca", "faca", "tabua", "air fryer", "cortina", "almofada", "termica"]),
    ("moda", ["camisa", "camiseta", "t-shirt", "blusa", "vestido", "calca", "short", "bermuda", "saia",
              "jaqueta", "moletom", "cropped", "baby look", "conjunto", "cueca", "meia", "bone", "relogio",
              "oculos", "bolsa", "mochila", "cinto", "pulseira", "colar", "brinco", "biquini", "pijama"]),
]


def _norm(txt):
    txt = unicodedata.normalize("NFD", txt.lower())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn")


def categoria(nome):
    n = _norm(nome)
    for cat, chaves in PALAVRAS:
        if any(k in n for k in chaves):
            return cat
    return "geral"


def agrupar(produtos):
    """Separa a lista de produtos por categoria -> {categoria: [produtos]}"""
    grupos = {}
    for p in produtos:
        cat = p.get("categoria") or categoria(p["nome"])
        grupos.setdefault(cat, []).append(p)
    return grupos
