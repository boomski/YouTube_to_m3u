#!/usr/bin/env python3
# coding: utf-8
"""
youtube_m3ugrabber.py
Gera um ficheiro .m3u8 por canal dentro da pasta "canais".
Cada ficheiro tem o nome do canal (santizado) e inclui o link do stream
(escolhido pela mesma lógica de qualidade do script original).

Uso:
  python3 youtube_m3ugrabber.py -i ../youtube_channel_info.txt
  python3 youtube_m3ugrabber.py -i ../youtube_channel_info.txt --outdir ./canais --timeout 20

"""
from __future__ import annotations
import os
import sys
import argparse
import logging
import tempfile
import stat
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, quote_plus

try:
    from yt_dlp import YoutubeDL
except Exception:
    print("Erro: yt-dlp não instalado. Faz: pip install yt-dlp", file=sys.stderr)
    raise

FALLBACK_M3U = "https://raw.githubusercontent.com/thomraider12/YouTube_to_m3u/main/assets/offline.m3u"


def write_temp_cookies(cookies_text: str) -> Optional[str]:
    if not cookies_text:
        return None
    tf = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
    try:
        tf.write(cookies_text)
        tf.flush()
        tf.close()
        try:
            os.chmod(tf.name, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
        return tf.name
    except Exception:
        try:
            tf.close()
            os.unlink(tf.name)
        except Exception:
            pass
        return None


def remove_file_silent(path: Optional[str]) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except Exception:
        pass


def parse_height(fmt: Dict[str, Any]) -> int:
    h = fmt.get("height")
    if isinstance(h, int):
        return h or 0
    res = fmt.get("resolution") or fmt.get("format_note") or fmt.get("format") or ""
    if isinstance(res, str):
        m = re.search(r'(\d{2,4})x(\d{2,4})', res)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        m2 = re.search(r'(\d{2,4})p', res)
        if m2:
            try:
                return int(m2.group(1))
            except Exception:
                pass
    return 0


def is_hls_format(fmt: Dict[str, Any]) -> bool:
    proto = (fmt.get("protocol") or "").lower()
    ext = (fmt.get("ext") or "").lower()
    url = (fmt.get("url") or "").lower()
    if "m3u8" in proto or ext == "m3u8" or ".m3u8" in url:
        return True
    if "m3u8" in proto or "hls" in proto:
        return True
    return False


def choose_best_stream_url(info: Dict[str, Any]) -> str:
    formats: List[Dict[str, Any]] = info.get("formats") or []
    if not formats:
        if "url" in info and info.get("url"):
            return info.get("url")
        return FALLBACK_M3U

    entries = []
    for f in formats:
        height = parse_height(f)
        entries.append((height, f))
    entries.sort(key=lambda x: x[0], reverse=True)

    best_hls = None
    best_hls_height = -1
    for height, f in entries:
        if is_hls_format(f):
            url = f.get("url")
            if url:
                best_hls = url
                best_hls_height = height
                break

    if best_hls:
        logging.debug("Escolhido HLS (melhor disponível): %sp -> %s", best_hls_height, best_hls)
        return best_hls

    for height, f in entries:
        url = f.get("url")
        if url:
            logging.debug("Nenhum HLS encontrado; escolhido melhor formato: %sp -> %s", height, url)
            return url

    if "url" in info and info.get("url"):
        return info.get("url")
    return FALLBACK_M3U


def extract_stream_with_yt_dlp(url: str, cookiefile: Optional[str] = None, timeout: int = 15) -> str:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "dump_single_json": True,
        "socket_timeout": timeout,
        "geo_bypass": True,
        "geo_bypass_country": "PT",
        "xff": "PT",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }

    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        logging.debug("yt-dlp falhou para %s : %s", url, e)
        return FALLBACK_M3U

    try:
        chosen = choose_best_stream_url(info)
        return chosen
    except Exception as e:
        logging.debug("Erro a escolher stream para %s : %s", url, e)
        if info.get("url"):
            return info.get("url")
        return FALLBACK_M3U


def sanitize_filename(name: str, max_len: int = 200) -> str:
    """
    Remove caracteres perigosos e limita o comprimento.
    Mantém letras, números, espaços, '-', '_' e '.'.
    Substitui '/', '\\', ':' etc por '_'.
    """
    if not name:
        name = "canal"
    # remover caracteres de controlo
    name = "".join(ch for ch in name if ord(ch) >= 32)
    # substituir barras e dois-pontos e outros por underscore
    name = re.sub(r'[\\/:\*\?"<>\|]+', "_", name)
    # permitir apenas um conjunto de caracteres
    name = re.sub(r'[^0-9A-Za-zÀ-ž \-\._]', '_', name)
    # trim e limitar
    name = name.strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    if not name:
        name = "canal"
    return name


def url_to_safe_name(url: str) -> str:
    try:
        p = urlparse(url)
        safe = (p.netloc + p.path).strip("/")
        if not safe:
            safe = url
        # codificar caracteres reservados para ainda ficar legível
        safe = re.sub(r'[^0-9A-Za-zÀ-ž \-\._]', '_', safe)
        return sanitize_filename(safe)
    except Exception:
        return sanitize_filename(url)


def write_m3u8_file(outdir: str, channel_name: str, group_title: Optional[str], tvg_logo: Optional[str], tvg_id: Optional[str], stream_url: str) -> str:
    fname = sanitize_filename(channel_name) + ".m3u8"
    path = os.path.join(outdir, fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n')
            # escrever EXTINF com metadados se existirem
            gi = group_title or ""
            lg = tvg_logo or ""
            tid = tvg_id or ""
            # escapar aspas internas
            gi = gi.replace('"', "'")
            lg = lg.replace('"', "'")
            tid = tid.replace('"', "'")
            f.write(f'#EXTINF:-1 group-title="{gi}" tvg-logo="{lg}" tvg-id="{tid}",{channel_name}\n')
            f.write(stream_url.strip() + "\n")
        logging.info("Criado: %s", path)
    except Exception as e:
        logging.error("Falha a criar %s : %s", path, e)
    return path


def process_file(infile: str, outdir: str, cookiefile: Optional[str], timeout: int) -> None:
    if not os.path.exists(infile):
        raise FileNotFoundError(infile)

    os.makedirs(outdir, exist_ok=True)

    with open(infile, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f]

    pending_meta = None  # quando virmos uma linha com pipes guardamos metadados até aparecer URL
    for line in lines:
        line = line.strip()
        if not line or line.startswith("~~"):
            continue

        # se for uma linha de metadados (contains |) e não for uma URL
        if "|" in line and not line.lower().startswith("http"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                ch_name = parts[0]
                grp_title = parts[1]
                tvg_logo = parts[2]
                tvg_id = parts[3]
                pending_meta = {
                    "ch_name": ch_name,
                    "grp_title": grp_title,
                    "tvg_logo": tvg_logo,
                    "tvg_id": tvg_id,
                }
                # não escrevemos ficheiro ainda — esperamos pela linha com a URL
                continue
            else:
                # linha comentada / inválida - reset pending_meta
                pending_meta = None
                continue

        # se for linha com URL
        if line.lower().startswith("http"):
            logging.info("Processando URL: %s", line)
            stream = extract_stream_with_yt_dlp(line, cookiefile=cookiefile, timeout=timeout)

            if pending_meta:
                ch_name = pending_meta.get("ch_name") or url_to_safe_name(line)
                grp_title = pending_meta.get("grp_title")
                tvg_logo = pending_meta.get("tvg_logo")
                tvg_id = pending_meta.get("tvg_id")
                pending_meta = None  # consumido
            else:
                # não havia metadados anteriores -> gerar nome a partir da URL
                ch_name = url_to_safe_name(line)
                grp_title = ""
                tvg_logo = ""
                tvg_id = ""

            # escrever ficheiro .m3u8 dentro de outdir
            write_m3u8_file(outdir, ch_name, grp_title, tvg_logo, tvg_id, stream)
            continue

        # caso contrário, ignorar
        pending_meta = None
        continue


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gerar um .m3u8 por canal (usa yt-dlp para obter melhor stream).")
    parser.add_argument("-i", "--input", default="../youtube_channel_info.txt", help="Ficheiro de input (default ../youtube_channel_info.txt)")
    parser.add_argument("-o", "--outdir", default="canais", help="Pasta de output onde serão criados os .m3u8 (default ./canais)")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout para yt-dlp (segundos)")
    parser.add_argument("--debug", action="store_true", help="Ativa logging debug")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="[%(levelname)s] %(message)s")

    cookies_text = os.environ.get("YT_COOKIES", "") or os.environ.get("YOUTUBE_COOKIES", "")
    cookiefile_path = None
    try:
        if cookies_text:
            cookiefile_path = write_temp_cookies(cookies_text)
            logging.debug("Ficheiro de cookies temporário: %s", cookiefile_path)
        else:
            logging.debug("Sem cookies fornecidos; a correr sem autenticação.")

        process_file(args.input, args.outdir, cookiefile_path, args.timeout)
        logging.info("Processamento concluído. Ficheiros em: %s", os.path.abspath(args.outdir))

    finally:
        if cookiefile_path:
            remove_file_silent(cookiefile_path)
            logging.debug("Ficheiro de cookies temporário removido.")


if __name__ == "__main__":
    main()
