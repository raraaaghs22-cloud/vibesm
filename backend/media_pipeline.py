"""Stage 1 of the grading pipeline: resolve a social video link to a watchable .mp4 (file or URL)."""
import os
import re
import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
import yt_dlp
import imageio_ffmpeg
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "").strip()
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "social-download-all-in-one.p.rapidapi.com").strip()
RESOLVE_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 120
MAX_VIDEO_BYTES = 50 * 1024 * 1024
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def youtube_id(url: str) -> Optional[str]:
    p = urlparse(url)
    if p.hostname and p.hostname.endswith("youtu.be"):
        return p.path.strip("/").split("/")[0] or None
    if "v" in parse_qs(p.query):
        return parse_qs(p.query)["v"][0]
    m = re.search(r"/(?:shorts|embed|live|v)/([\w-]{6,})", p.path)
    return m.group(1) if m else None


def _quality_rank(m: dict) -> int:
    q = (m.get("quality") or "").lower()
    return (2 if "no_watermark" in q or "nowm" in q else 0) + (1 if "hd" in q or "720" in q or "1080" in q else 0)


async def resolve_rapidapi(url: str) -> dict:
    async with httpx.AsyncClient(timeout=RESOLVE_TIMEOUT) as hc:
        r = await hc.post(f"https://{RAPIDAPI_HOST}/v1/social/autolink", json={"url": url},
                          headers={"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST})
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"RapidAPI: {data.get('message') or 'error'}")
    vids = [m for m in data.get("medias") or [] if m.get("type") == "video" and m.get("url")]
    if not vids:
        raise RuntimeError("RapidAPI: no video media")
    best = sorted(vids, key=_quality_rank, reverse=True)[0]
    return {"media_url": best["url"], "headers": {"User-Agent": UA}, "source": "rapidapi",
            "title": data.get("title"), "caption": data.get("title"), "author": data.get("author")}


def resolve_ytdlp(url: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": RESOLVE_TIMEOUT,
            "format": "b[ext=mp4][height<=720]/b[height<=720]/b"}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info.get("url"):
        raise RuntimeError("yt-dlp: no direct media url")
    return {"media_url": info["url"], "headers": info.get("http_headers") or {"User-Agent": UA}, "source": "yt-dlp",
            "title": info.get("title"), "caption": info.get("description"), "author": info.get("uploader")}


async def resolve_media(url: str) -> dict:
    errors = []
    if RAPIDAPI_KEY:
        try:
            return await resolve_rapidapi(url)
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:150])
    try:
        return await asyncio.to_thread(resolve_ytdlp, url)
    except Exception as e:  # noqa: BLE001
        errors.append(str(e)[:150])
    raise RuntimeError(" | ".join(errors))


async def download_file(media_url: str, headers: dict, path: str) -> None:
    size = 0
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as hc:
        async with hc.stream("GET", media_url) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in r.aiter_bytes(1 << 16):
                    size += len(chunk)
                    if size > MAX_VIDEO_BYTES:
                        raise RuntimeError("Video terlalu besar (>50MB)")
                    f.write(chunk)
    if size < 10_000:
        raise RuntimeError("File video kosong/tidak valid")


def download_ytdlp(url: str, folder: str) -> str:
    opts = {"outtmpl": f"{folder}/ydl.%(ext)s", "format": "b[ext=mp4][height<=720]/b[height<=720]/b",
            "max_filesize": MAX_VIDEO_BYTES, "quiet": True, "no_warnings": True, "noplaylist": True,
            "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(), "merge_output_format": "mp4"}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [f for f in os.listdir(folder) if f.startswith("ydl.")]
    if not files:
        raise RuntimeError("yt-dlp: download produced no file")
    return os.path.join(folder, files[0])


def fetch_transcript(video_id: str) -> Optional[str]:
    try:
        t = YouTubeTranscriptApi().fetch(video_id, languages=["id", "en"])
        return " ".join(s.text for s in t)[:6000] or None
    except Exception as e:  # noqa: BLE001
        logger.info(f"Transcript unavailable: {type(e).__name__}")
        return None


async def extract_media(url: str, platform: str, folder: str, youtube_public: bool) -> dict:
    """Returns {ok, mode: url|file, video_url, video_path, source, title, caption, transcript, error}. Never raises."""
    out = {"ok": False, "mode": None, "video_url": None, "video_path": None, "source": None,
           "title": None, "caption": None, "transcript": None, "error": None}
    try:
        if platform == "youtube":
            vid = youtube_id(url)
            if not (youtube_public and vid):
                out["error"] = "YouTube video tidak publik / tidak ditemukan"
                return out
            out.update(ok=True, mode="url", video_url=f"https://www.youtube.com/watch?v={vid}", source="youtube-url")
            try:
                out["transcript"] = await asyncio.wait_for(asyncio.to_thread(fetch_transcript, vid), RESOLVE_TIMEOUT)
            except asyncio.TimeoutError:
                pass
            return out
        try:
            res = await asyncio.wait_for(resolve_media(url), RESOLVE_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Timeout: link .mp4 tidak didapat dalam {RESOLVE_TIMEOUT} detik")
        out.update(source=res["source"], title=res.get("title"), caption=res.get("caption"))
        path = os.path.join(folder, "video.mp4")
        try:
            await asyncio.wait_for(download_file(res["media_url"], res["headers"], path), DOWNLOAD_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            if res["source"] != "yt-dlp":
                raise RuntimeError(f"Unduhan gagal: {str(e)[:150] or type(e).__name__}")
            logger.info(f"Direct download failed ({str(e)[:100]}), retrying with yt-dlp downloader")
            try:
                path = await asyncio.wait_for(asyncio.to_thread(download_ytdlp, url, folder), DOWNLOAD_TIMEOUT)
            except asyncio.TimeoutError:
                raise RuntimeError("Timeout saat mengunduh video")
        out.update(ok=True, mode="file", video_path=path)
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:300]
    if not out["ok"]:
        logger.info(f"Media extraction failed for {url}: {out['error']}")
    return out
