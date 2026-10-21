"""
Busca produtos na API de Afiliados da Shopee (a mesma que o bot do Telegram usa)
e devolve no formato que o gerador de vídeos entende.

Precisa no .env:  SHOPEE_APP_ID=...   SHOPEE_SECRET=...
(pega no painel de afiliados: affiliate.shopee.com.br > Open API)
"""
import hashlib
import json
import os
import time

import requests

URL = "https://open-api.affiliate.shopee.com.br/graphql"

CONSULTA = """
query($keyword: String, $sortType: Int, $page: Int, $limit: Int) {
  productOfferV2(keyword: $keyword, sortType: $sortType, page: $page, limit: $limit) {
    nodes {
      itemId productName priceMin priceMax priceDiscountRate
      ratingStar sales imageUrl offerLink commissionRate shopName
    }
    pageInfo { page limit hasNextPage }
  }
}
"""

# sortType da Shopee: 1 = relevância, 2 = mais vendidos, 3 = maior preço, 4 = menor preço, 5 = maior comissão
MAIS_VENDIDOS = 2


def _assinatura(app_id, segredo, corpo, ts):
    return hashlib.sha256(f"{app_id}{ts}{corpo}{segredo}".encode()).hexdigest()


def buscar(palavra, limite=30, pagina=1, ordem=MAIS_VENDIDOS):
    app_id, segredo = os.environ["SHOPEE_APP_ID"], os.environ["SHOPEE_SECRET"]
    corpo = json.dumps({"query": CONSULTA, "variables": {
        "keyword": palavra, "sortType": ordem, "page": pagina, "limit": limite}}, separators=(",", ":"))
    ts = int(time.time())
    cab = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={_assinatura(app_id, segredo, corpo, ts)}",
    }
    r = requests.post(URL, data=corpo, headers=cab, timeout=20)
    r.raise_for_status()
    dados = r.json()
    if dados.get("errors"):
        raise RuntimeError(f"Shopee respondeu erro: {dados['errors']}")
    return dados["data"]["productOfferV2"]["nodes"]


def _vendidos(n):
    n = int(n or 0)
    if n >= 1000:
        return f"{n // 1000} mil+"
    return f"{n}+"


def converter(no):
    """Formato da API -> formato do gerador de vídeos."""
    preco = float(no["priceMin"])
    desc = float(no.get("priceDiscountRate") or 0)
    antigo = round(preco / (1 - desc / 100), 2) if 0 < desc < 100 else round(preco * 1.4, 2)
    return {
        "id": str(no["itemId"]),
        "nome": no["productName"],
        "preco": preco,
        "preco_antigo": antigo,
        "desconto": int(desc),
        "nota": round(float(no.get("ratingStar") or 0), 1),
        "vendidos": _vendidos(no.get("sales")),
        "imagem": no["imageUrl"],
        "link": no["offerLink"],
        "comissao": float(no.get("commissionRate") or 0),
    }


def bons_produtos(palavra, ja_usados=(), nota_min=4.6, desconto_min=30, vendas_min=300, quantos=3,
                  estrategia="alta"):
    """
    estrategia="alta"      -> EM ALTA: sorteia entre os 8 mais vendidos (o que está bombando).
    estrategia="escondido" -> ACHADO ESCONDIDO: pula os campeões de venda (que todo afiliado divulga) e
                              pega produtos que vendem bem mas estão "no meio da lista", priorizando
                              comissão mais alta -> menos concorrência pra você.
    """
    import random

    paginas = (1, 2) if estrategia == "alta" else (1, 2, 3)
    candidatos = []
    for pagina in paginas:
        try:
            nos = buscar(palavra, pagina=pagina)
        except Exception:
            if not candidatos:
                raise
            break
        for no in nos:
            if str(no["itemId"]) in ja_usados:
                continue
            if float(no.get("ratingStar") or 0) < nota_min:
                continue
            if float(no.get("priceDiscountRate") or 0) < desconto_min:
                continue
            if int(no.get("sales") or 0) < vendas_min:
                continue
            candidatos.append(no)
    candidatos.sort(key=lambda n: int(n.get("sales") or 0), reverse=True)

    if estrategia == "escondido" and len(candidatos) > 12:
        meio = candidatos[10:]                       # tira os 10 que mais vendem
        meio.sort(key=lambda n: float(n.get("commissionRate") or 0), reverse=True)
        topo = meio[:8]                              # os de maior comissão entre os "escondidos"
    else:
        topo = candidatos[:8]
    random.shuffle(topo)
    escolhidos = [converter(n) for n in topo[:quantos]]
    for p in escolhidos:
        p["estrategia"] = estrategia
    return escolhidos
