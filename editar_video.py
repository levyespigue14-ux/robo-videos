"""
Finaliza o vídeo gerado na IA (YouTube Create): coloca gancho no topo, narração
com voz de IA, legenda palavra por palavra, etiqueta de preço e chamada pro grupo do WhatsApp (link na bio).

Uso direto (teste):
    python editar_video.py video_da_ia.mp4 --nome "Cílios 5D Fadvan" --preco 27.90 --antigo 59.90 --categoria beleza
"""
import argparse
import os
import subprocess
import tempfile

from PIL import Image

import gerar_video as gv
import gerar_video_ugc as ugc
from estilos import ESTILOS, categoria

W, H, FPS = gv.W, gv.H, gv.FPS


def duracao(arquivo):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arquivo],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def tem_audio(arquivo):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", arquivo], capture_output=True, text=True).stdout.strip()
    return bool(out)


def finalizar(video_in, p, saida, musica=None, usar_voz=True, gancho=None):
    cat = p.get("categoria") or categoria(p["nome"])
    cfg = ugc.UGC.get(cat, ugc.UGC["geral"])
    g, falas = ugc.roteiro(p, cat, curto=True)
    gancho = gancho or g
    print(f"[editar/{cat}] gancho: {gancho}\n  fala: {' '.join(falas)}")

    dur_video = duracao(video_in)
    with tempfile.TemporaryDirectory() as tmp:
        voz_mp3, palavras = ugc.narrar(falas, cfg["voz"], tmp, usar_voz)
        dur = max(dur_video, palavras[-1][2] + 0.8)
        blocos = ugc.blocos_legenda(palavras)
        ini_preco = next((w[1] for w in palavras if "R$" in w[0]), dur * 0.3)
        ini_cta = next((w[1] for w in palavras if "grupo" in w[0].lower() or "link" in w[0].lower()),
                       max(dur - 2.5, dur * 0.7))

        # lê os quadros do vídeo da IA já em 1080x1920 (repete o vídeo se a fala for mais longa)
        ler = ["ffmpeg", "-loglevel", "error"]
        if dur > dur_video + 0.05:
            ler += ["-stream_loop", "-1"]
        ler += ["-i", video_in, "-t", f"{dur:.2f}",
                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        leitor = subprocess.Popen(ler, stdout=subprocess.PIPE)

        mudo = os.path.join(tmp, "v.mp4")
        escritor = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                     "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                                     "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", mudo],
                                    stdin=subprocess.PIPE)
        tam = W * H * 3
        fr = 0
        while True:
            dado = leitor.stdout.read(tam)
            if len(dado) < tam:
                break
            t = fr / FPS
            q = Image.frombytes("RGB", (W, H), dado).convert("RGBA")
            ugc.desenhar_gancho(q, gancho, cfg, t)
            ugc.desenhar_preco(q, p, t, ini_preco, ini_cta - 0.2, cfg)
            ugc.desenhar_legenda(q, blocos, t, cfg)
            ugc.desenhar_cta(q, t, ini_cta, cfg)
            escritor.stdin.write(q.convert("RGB").tobytes())
            fr += 1
        leitor.wait()
        escritor.stdin.close()
        escritor.wait()

        # áudio: som original bem baixinho + voz + música baixa
        entradas, filtros, mix = ["-i", mudo], [], []
        n = 1
        if tem_audio(video_in):
            entradas += (["-stream_loop", "-1"] if dur > dur_video + 0.05 else []) + ["-i", video_in]
            filtros.append(f"[{n}:a]volume=0.15[orig]")
            mix.append("[orig]")
            n += 1
        if voz_mp3:
            entradas += ["-i", voz_mp3]
            filtros.append(f"[{n}:a]volume=1.0[voz]")
            mix.append("[voz]")
            n += 1
        if musica:
            entradas += ["-stream_loop", "-1", "-i", musica]
            filtros.append(f"[{n}:a]volume={0.12 if voz_mp3 else 0.7},afade=t=out:st={max(dur - 1, 0):.2f}:d=1[mus]")
            mix.append("[mus]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error"] + entradas
        if mix:
            filtros.append("".join(mix) + f"amix=inputs={len(mix)}:duration=longest:normalize=0[a]")
            cmd += ["-filter_complex", ";".join(filtros), "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
        cmd += ["-c:v", "copy", "-t", f"{dur:.2f}", "-movflags", "+faststart", saida]
        subprocess.run(cmd, check=True)

    legenda = (f"{gancho[0].upper() + gancho[1:]} 😱\nLink no meu grupo do WhatsApp — tá na bio! 📲\n\n"
               f"{ESTILOS.get(cat, ESTILOS['geral'])['tags']} #ia")
    print(f"  OK: {saida} ({dur:.1f}s){'' if voz_mp3 else ' [sem voz]'}")
    return saida, legenda


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--nome", required=True)
    ap.add_argument("--preco", type=float, required=True)
    ap.add_argument("--antigo", type=float, required=True)
    ap.add_argument("--categoria")
    ap.add_argument("--nome-curto")
    ap.add_argument("--musica")
    ap.add_argument("--saida", default="videos/finalizado.mp4")
    ap.add_argument("--sem-voz", action="store_true")
    a = ap.parse_args()
    prod = {"nome": a.nome, "preco": a.preco, "preco_antigo": a.antigo,
            "desconto": round((1 - a.preco / a.antigo) * 100), "categoria": a.categoria}
    if a.nome_curto:
        prod["nome_curto"] = a.nome_curto
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    finalizar(a.video, prod, a.saida, a.musica, not a.sem_voz)
