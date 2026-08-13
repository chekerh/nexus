"""AI Thumbnail Generator — keyframe extraction + FFmpeg compositing + Ollama scoring.

Pipeline:
  1. Extract N candidate frames at strategic timestamps (hook start, 25%, 50%, 75%).
  2. For each frame, generate a 1080×1920 (vertical) thumbnail.
  3. Use Ollama to score each frame's composition and predict engagement.
  4. Render final thumbnails with title overlay via FFmpeg drawtext.
  5. Return sorted list of best thumbnails.
"""

import json
import os
import re
import subprocess

import ollama

from .config import settings
from .model_router import get_ollama_model_for_task

THUMBNAIL_LAYOUTS = {
    "centered": {
        "title_y": "h/2-text_h/2",
        "fontsize": 52,
        "border_size": 4,
    },
    "bottom-text": {
        "title_y": "h-text_h-60",
        "fontsize": 46,
        "border_size": 3,
    },
    "top-text": {
        "title_y": "40",
        "fontsize": 46,
        "border_size": 3,
    },
    "split": {
        "title_y": "h/2-20",
        "fontsize": 56,
        "border_size": 5,
    },
}

FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD_PATH = "/System/Library/Fonts/Helvetica.ttc"


def _get_video_info(video_path: str) -> tuple:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        duration = float(result.stdout.strip()) if result.returncode == 0 else 0.0
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=s=x:p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        width, height = 1920, 1080
        if result.returncode == 0 and "x" in result.stdout.strip():
            parts = result.stdout.strip().split("x")
            if len(parts) == 2:
                width, height = int(parts[0]), int(parts[1])
        return duration, width, height
    except Exception:
        return 0.0, 1920, 1080


def _extract_frame(video_path: str, timestamp: float, output_path: str, width: int = 1080, height: int = 1920) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(timestamp),
        "-i",
        video_path,
        "-vframes",
        "1",
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        "-q:v",
        "2",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def _composite_title_on_frame(frame_path: str, output_path: str, title: str, layout: str = "centered") -> bool:
    layout_cfg = THUMBNAIL_LAYOUTS.get(layout, THUMBNAIL_LAYOUTS["centered"])
    escaped_title = title.replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")

    from typing import cast

    border_size = cast(int, layout_cfg["border_size"])
    fontsize = cast(int, layout_cfg["fontsize"])
    title_y = cast(str, layout_cfg["title_y"])

    border_filter = (
        f"drawtext=text='{escaped_title}':"
        f"fontfile={FONT_PATH}:"
        f"fontsize={fontsize + 2}:fontcolor=black@0.85:"
        f"x=(w-text_w)/2:y={title_y}:"
        f"borderw={border_size + 1}:bordercolor=black@0.7"
    )
    main_filter = (
        f"drawtext=text='{escaped_title}':"
        f"fontfile={FONT_PATH}:"
        f"fontsize={fontsize}:fontcolor=white:"
        f"x=(w-text_w)/2:y={title_y}"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        frame_path,
        "-vf",
        f"{border_filter},{main_filter}",
        "-q:v",
        "2",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except Exception:
        pass
    # Fallback: composite the title using Pillow when drawtext is unavailable
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(frame_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont | None = None
        for fp in (FONT_PATH, "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
            try:
                font = ImageFont.truetype(fp, fontsize)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        w, h = img.size
        lines = []
        for line in title.split("\n"):
            words, current = line.split(), ""
            for word in words:
                test = f"{current} {word}".strip()
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] - bbox[0] <= w - 120:
                    current = test
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        lines = [line for line in lines if line]
        py = {
            "centered": max(60, int(h * 0.3)),
            "bottom-text": max(60, h - 140),
            "top-text": 40,
            "split": max(60, int(h * 0.3)),
        }.get(layout, max(60, int(h * 0.3)))
        y: float = cast(int, py)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (w - (bbox[2] - bbox[0])) // 2
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
            y += (bbox[3] - bbox[1]) + 8
        img.save(output_path, quality=88)
        return os.path.getsize(output_path) > 1000
    except Exception:
        try:
            import shutil

            shutil.copy2(frame_path, output_path)
            return True
        except Exception:
            return False


def _score_frame_with_ollama(frame_path: str, transcript_context: str = "") -> tuple:
    """Score a thumbnail's engagement potential using Ollama vision.

    Returns (score: 0-10, reasoning: str).
    """
    try:
        import base64

        with open(frame_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        model = get_ollama_model_for_task("thumbnails")
        system = (
            "You are a thumbnail engagement analyst. Score this thumbnail 1-10 based on: "
            "visual clarity, focal point strength, color contrast, text readability, "
            "and likelihood to earn a click in a social media feed. "
            'Return STRICT JSON: {"score": <float 1-10>, "reason": "<brief reason>"}'
        )
        user_msg = f"Thumbnail frame. Transcript context: {transcript_context[:500]}"
        if transcript_context:
            user_msg += f"\nTranscript context: {transcript_context[:500]}"

        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg, "images": [b64]},
            ],
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            options={"temperature": 0.1, "num_predict": 128},
        )
        content = (response.get("message", {}) or {}).get("content", "").strip()
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            parsed = json.loads(match.group(0))
            score = float(parsed.get("score", 5.0))
            reason = parsed.get("reason", "")
            return max(0.0, min(10.0, score)), reason
    except Exception:
        pass
    return 5.0, ""


def _score_frame_heuristic(frame_path: str) -> float:
    """Heuristic fallback scoring based on image properties via FFmpeg."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,pix_fmt",
                "-of",
                "json",
                frame_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        info = json.loads(result.stdout) if result.stdout else {}
        streams = info.get("streams", [])
        if streams:
            w = streams[0].get("width", 0)
            h = streams[0].get("height", 0)
            # Prefer higher resolution and 16:9-ish aspect ratio
            if w > 0 and h > 0:
                aspect = w / h
                aspect_score = 10.0 - min(10.0, abs(aspect - 1.78) * 10)
                res_score = min(10.0, (w * h) / (1920 * 1080) * 10)
                return aspect_score * 0.4 + res_score * 0.6
        return 5.0
    except Exception:
        return 5.0


def _suggest_overlay_title(transcript: str, duration: float, clip_texts: list[str]) -> str:
    """Use Ollama to suggest a clickable thumbnail title from transcript context."""
    context = "\n".join(clip_texts[:3]) if clip_texts else transcript[:1000]
    try:
        model = get_ollama_model_for_task("thumbnails")
        system = (
            "You are a thumbnail copywriter. Given video context, suggest ONE short "
            "clickable title (max 5 words) for a YouTube Shorts/TikTok thumbnail. "
            "Make it curiosity-gap, urgent, or benefit-driven. "
            'Return STRICT JSON: {"title": "<title text>"}'
        )
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Video context (transcript): {context[:800]}"},
            ],
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            options={"temperature": 0.3, "num_predict": 64},
        )
        content = (response.get("message", {}) or {}).get("content", "").strip()
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            parsed = json.loads(match.group(0))
            title = parsed.get("title", "")
            if title and len(title) < 60:
                return title
    except Exception:
        pass
    return ""


def _generate_layout_variants(title: str) -> list[tuple]:
    """Return list of (layout_name, title_variant) tuples."""
    variants = []
    for layout in ["centered", "bottom-text", "top-text", "split"]:
        variants.append((layout, title))
    if len(title) > 20:
        # For long titles, use a shorter variant
        short = title.rsplit(" ", 1)[0] if " " in title else title[:15]
        variants.append(("centered", short))
    return variants


def generate_thumbnails(
    video_path: str,
    transcript: str,
    hooks: list[dict],
    clips_dir: str,
    clip_index: int = 0,
    title: str = "",
) -> list[dict]:
    """Generate thumbnails for a specific clip.

    Returns list of thumbnail result dicts with path, score, layout, title.
    """
    duration, src_w, src_h = _get_video_info(video_path)
    if duration <= 0:
        return []

    hook = hooks[clip_index] if clip_index < len(hooks) else {}
    hook_start = float(hook.get("start", 0))
    hook_end = float(hook.get("end", duration))
    hook_text = hook.get("text", "")

    timestamps = []
    (hook_start + hook_end) / 2
    # Strategic extraction points
    for pct in [0.0, 0.15, 0.5, 0.85]:
        ts = hook_start + (hook_end - hook_start) * pct
        timestamps.append(ts)
    # Add hook-specific timestamps
    if hook_start > 0:
        timestamps.append(hook_start)
    if hook_end < duration:
        timestamps.append(max(0, hook_end - 1))

    # Deduplicate and sort
    timestamps = sorted(set(round(t, 1) for t in timestamps if 0 <= t < duration))

    results = []
    frame_dir = os.path.join(clips_dir, f"thumb_clip{clip_index}")
    os.makedirs(frame_dir, exist_ok=True)

    target_w, target_h = 1080, 1920

    for i, ts in enumerate(timestamps):
        frame_path = os.path.join(frame_dir, f"frame_{i}.jpg")
        ok = _extract_frame(video_path, ts, frame_path, target_w, target_h)
        if not ok:
            continue

        # Score
        ai_score, reason = _score_frame_with_ollama(frame_path, hook_text)
        heuristic_score = _score_frame_heuristic(frame_path)
        final_score = ai_score * 0.7 + heuristic_score * 0.3

        # Generate overlay title if not provided
        overlay_title = title or _suggest_overlay_title(transcript, duration, [hook_text])

        # Generate layout variants for top frames
        layouts = _generate_layout_variants(overlay_title)
        for layout_name, variant_title in layouts:
            variant_path = os.path.join(frame_dir, f"thumb_{clip_index}_{i}_{layout_name}.jpg")
            ok = _composite_title_on_frame(frame_path, variant_path, variant_title, layout_name)
            if not ok:
                continue

            results.append(
                {
                    "clip_index": clip_index,
                    "variant_name": f"frame-{i}-{layout_name}",
                    "image_path": variant_path,
                    "title_overlay": variant_title,
                    "layout": layout_name,
                    "score": round(final_score, 2),
                    "ai_reason": reason,
                    "timestamp": ts,
                }
            )

    # Sort by score descending, take top 4
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:8]


def generate_all_clip_thumbnails(
    video_path: str,
    transcript: str,
    hooks: list[dict],
    clips_dir: str,
    titles: list[str] | None = None,
) -> list[list[dict]]:
    """Generate thumbnails for all clips."""
    all_results = []
    for idx in range(len(hooks)):
        title = titles[idx] if titles and idx < len(titles) else ""
        clip_thumbs = generate_thumbnails(
            video_path,
            transcript,
            hooks,
            clips_dir,
            clip_index=idx,
            title=title,
        )
        all_results.append(clip_thumbs)
    return all_results
