"""
Envio dos vídeos para os RASCUNHOS do TikTok (Content Posting API, modo Upload).

O vídeo cai na caixa de entrada do app do TikTok; você abre, coloca um som em alta e publica.

Configuração (uma vez só):
  1. No .env:  TIKTOK_CLIENT_KEY=...  TIKTOK_CLIENT_SECRET=...  TIKTOK_REDIRECT_URI=...
  2. Rode:     python tiktok.py conectar     (abre o login do TikTok; cole de volta o endereço final)

Uso manual:
  python tiktok.py enviar videos/arquivo.mp4
  python tiktok.py status
"""
import json
import os
import secrets
import sys
import time
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQ_TOKEN = os.path.join(AQUI, "tiktok_token.json")
API = "https://open.tiktokapis.com/v2"
ESCOPOS = "user.info.basic,video.upload"


def _env(nome):
    v = os.environ.get(nome, "").strip()
    if not v:
        raise RuntimeError(f"Falta {nome} no .env")
    return v


def configurado() -> bool:
    """Envio automático só liga com TIKTOK_ATIVO=1 no .env (precisa do app aprovado pelo TikTok)."""
    return (os.environ.get("TIKTOK_ATIVO", "0").strip() == "1"
            and bool(os.environ.get("TIKTOK_CLIENT_KEY")) and os.path.exists(ARQ_TOKEN))


# ---------------- login (OAuth) ----------------
def url_login() -> str:
    q = {"client_key": _env("TIKTOK_CLIENT_KEY"), "scope": ESCOPOS, "response_type": "code",
         "redirect_uri": _env("TIKTOK_REDIRECT_URI"), "state": secrets.token_hex(8)}
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(q)


def _salvar(dados: dict):
    dados["expira_em"] = time.time() + int(dados.get("expires_in", 86400)) - 120
    dados["refresh_expira_em"] = time.time() + int(dados.get("refresh_expires_in", 31536000)) - 120
    with open(ARQ_TOKEN, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=1)


def _pedir_token(form: dict) -> dict:
    form = {"client_key": _env("TIKTOK_CLIENT_KEY"), "client_secret": _env("TIKTOK_CLIENT_SECRET"), **form}
    r = requests.post(f"{API}/oauth/token/", data=form, timeout=30,
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"TikTok recusou o login: {d}")
    _salvar(d)
    return d


def trocar_codigo(endereco_ou_codigo: str) -> dict:
    texto = endereco_ou_codigo.strip()
    codigo = parse_qs(urlparse(texto).query).get("code", [texto])[0] if "code=" in texto else texto
    return _pedir_token({"code": codigo, "grant_type": "authorization_code",
                         "redirect_uri": _env("TIKTOK_REDIRECT_URI")})


def token() -> str:
    if not os.path.exists(ARQ_TOKEN):
        raise RuntimeError("TikTok não conectado. Rode: python tiktok.py conectar")
    d = json.load(open(ARQ_TOKEN, encoding="utf-8"))
    if time.time() < d.get("expira_em", 0):
        return d["access_token"]
    if time.time() > d.get("refresh_expira_em", 0):
        raise RuntimeError("Login do TikTok venceu. Rode de novo: python tiktok.py conectar")
    return _pedir_token({"grant_type": "refresh_token", "refresh_token": d["refresh_token"]})["access_token"]


# ---------------- envio ----------------
def enviar_rascunho(caminho: str) -> str:
    """Manda o vídeo para a caixa de entrada (rascunhos) do TikTok. Devolve o publish_id."""
    tamanho = os.path.getsize(caminho)
    MB = 1024 * 1024
    if tamanho <= 64 * MB:
        pedaco, total = tamanho, 1
    else:
        pedaco = 10 * MB
        total = tamanho // pedaco  # o último pedaço leva o resto (regra do TikTok)
    cab = {"Authorization": f"Bearer {token()}", "Content-Type": "application/json; charset=UTF-8"}
    r = requests.post(f"{API}/post/publish/inbox/video/init/", headers=cab, timeout=30, json={
        "source_info": {"source": "FILE_UPLOAD", "video_size": tamanho,
                        "chunk_size": pedaco, "total_chunk_count": total}})
    d = r.json()
    if d.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok recusou o envio: {d['error']}")
    url, pid = d["data"]["upload_url"], d["data"]["publish_id"]

    with open(caminho, "rb") as f:
        for i in range(total):
            inicio = i * pedaco
            fim = tamanho - 1 if i == total - 1 else inicio + pedaco - 1
            f.seek(inicio)
            corpo = f.read(fim - inicio + 1)
            up = requests.put(url, data=corpo, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(corpo)),
                "Content-Range": f"bytes {inicio}-{fim}/{tamanho}"})
            if up.status_code not in (200, 201, 206):
                raise RuntimeError(f"Falhou subir o vídeo pro TikTok: {up.status_code} {up.text[:200]}")
    return pid


def status(publish_id: str) -> dict:
    cab = {"Authorization": f"Bearer {token()}", "Content-Type": "application/json; charset=UTF-8"}
    return requests.post(f"{API}/post/publish/status/fetch/", headers=cab, timeout=30,
                         json={"publish_id": publish_id}).json()


def quem_sou() -> str:
    r = requests.get(f"{API}/user/info/", params={"fields": "display_name"},
                     headers={"Authorization": f"Bearer {token()}"}, timeout=30).json()
    return r.get("data", {}).get("user", {}).get("display_name", "?")


# ---------------- linha de comando ----------------
if __name__ == "__main__":
    try:
        import bot_videos  # noqa: F401  (só pra carregar o .env)
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ajuda"
    if cmd == "conectar":
        u = url_login()
        print("\n1) Vai abrir o TikTok. Entre com a conta @levylly2 e clique em Autorizar.")
        print("2) Depois ele vai para uma página (pode dar 'página não encontrada', tudo bem).")
        print("3) Copie o ENDEREÇO COMPLETO lá de cima do navegador e cole aqui.\n")
        print(u, "\n")
        webbrowser.open(u)
        d = trocar_codigo(input("Cole o endereço aqui: "))
        print(f"\n✅ TikTok conectado! Conta: {quem_sou()}  (login vale por 1 ano)")
    elif cmd == "enviar" and len(sys.argv) > 2:
        pid = enviar_rascunho(sys.argv[2])
        print(f"✅ Enviado pros rascunhos do TikTok (id {pid}). Abra o app do TikTok > notificações/caixa de entrada.")
    elif cmd == "status" and len(sys.argv) > 2:
        print(json.dumps(status(sys.argv[2]), indent=1, ensure_ascii=False))
    elif cmd == "status":
        print("Conectado como:", quem_sou())
    else:
        print(__doc__)
    if os.name == "nt":
        input("\nAperte Enter para fechar")
