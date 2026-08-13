"""Brain Rot Shorts Generator — AI script generation + video rendering with audio and dynamic backgrounds."""

import contextlib
import json
import logging
import os
import random
import subprocess
import tempfile
from datetime import UTC, datetime

from PIL import Image, ImageDraw, ImageFont

from ..core.model_router import get_ollama_model_for_task

logger = logging.getLogger("nexus.brainrot")

NICHES = {
    "drama": {
        "prompt": "Write a dramatic short story (20-40 seconds when read aloud) about {idea}. Use emotional hooks, shocking twists. Include 3 timestamped caption cues in the response as JSON.",
        "hook": "You won't believe what happened next",
    },
    "gaming": {
        "prompt": "Write a gaming-related short script (20-40 seconds when read aloud) about {idea}. Use hype language, callouts, and energy. Include 3 timestamped caption cues in JSON.",
        "hook": "This mechanic is BROKEN",
    },
    "fake_life_stories": {
        "prompt": "Write an engaging fake life story (20-40 seconds) about {idea}. Make it relatable, emotional, with a twist ending. Include 3 timestamped caption cues in JSON.",
        "hook": "My friends still don't know",
    },
    "motivation": {
        "prompt": "Write a hard-hitting motivational speech (20-40 seconds) about {idea}. Use short punchy sentences, bold claims. Include 3 timestamped caption cues in JSON.",
        "hook": "This will change everything",
    },
    "money": {
        "prompt": "Write a money-making tip or hustle story (20-40 seconds) about {idea}. Use specific numbers, results, and urgency. Include 3 timestamped caption cues in JSON.",
        "hook": "I made $10k doing this",
    },
    "facts": {
        "prompt": "Write 5 mind-blowing facts (20-40 seconds total) about {idea}. Each fact should be shocking and memorable. Include 3 timestamped caption cues in JSON.",
        "hook": "Number 3 will shock you",
    },
}


def _load_caption_styles():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "caption_styles.json")
    path = os.path.normpath(os.path.abspath(path))
    try:
        with open(path) as f:
            data = json.load(f)
        return {
            k: {
                dk: dv
                for dk, dv in v.items()
                if dk != "description" and dk != "label" and dk != "animation" and dk != "position"
            }
            for k, v in data.items()
        }
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load caption_styles.json (%s), falling back to defaults", e)
        return {
            "brain_rot": {"font": "Impact", "fontsize": 56, "fontcolor": "white", "borderw": 4, "bordercolor": "black"},
            "hype": {"font": "Arial-Bold", "fontsize": 64, "fontcolor": "yellow", "borderw": 3, "bordercolor": "red"},
            "clean": {"font": "Helvetica", "fontsize": 48, "fontcolor": "white", "borderw": 2, "bordercolor": "black"},
        }


def _load_caption_styles_meta():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "caption_styles.json")
    path = os.path.normpath(os.path.abspath(path))
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load caption_styles.json meta (%s)", e)
        return {}


CAPTION_STYLES = _load_caption_styles()
CAPTION_STYLES_META = _load_caption_styles_meta()


def _extract_json(text: str) -> dict:
    import re

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    text = text.strip()
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        text = text[brace_start : brace_end + 1]

    def strip_trailing_commas(s):
        result = []
        in_string = False
        escape = False
        for i, ch in enumerate(s):
            if escape:
                escape = False
                result.append(ch)
                continue
            if ch == "\\" and in_string:
                escape = True
                result.append(ch)
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                result.append(ch)
                continue
            if not in_string and ch == ",":
                lookahead = s[i + 1 :].lstrip()
                if lookahead and lookahead[0] in "}]":
                    continue
            result.append(ch)
        return "".join(result)

    text = strip_trailing_commas(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    text = re.sub(r'"\s*\n\s*"(?=\w)', '",\n"', text)
    text = strip_trailing_commas(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def generate_script(niche: str, idea: str = "", caption_style: str = "brain_rot", language: str = "en") -> dict:
    """Generate a brain rot short script using Ollama."""
    import ollama

    niche_config = NICHES.get(niche, NICHES["drama"])
    idea_text = idea.strip() or f"a random {niche} scenario"
    prompt = niche_config["prompt"].format(idea=idea_text)

    lang_map = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese"}
    lang_name = lang_map.get(language, "English")
    system_prompt = f"""You are a viral short-form content generator. Generate 20-40 second scripts optimized for high retention.

Your response MUST be valid JSON with this exact structure:
{{
  "hook": "The opening hook line",
  "script": "The full script text that will be read aloud (60-120 words is ideal for 20-40s)",
  "caption_cues": [
    {{"time": 0, "text": "First caption"}},
    {{"time": 5, "text": "Second caption"}},
    {{"time": 10, "text": "Third caption"}}
  ]
}}

Rules:
- Script must be 60-120 words (20-40 seconds read time)
- First 3 seconds must be the hook
- Caption cues at 0s, ~5s, ~10s relative to script start
- Keep language simple, punchy, conversational
- End with a call to action or question
- Write the ENTIRE script and captions in {lang_name}"""
    try:
        brainrot_model = get_ollama_model_for_task("chat")
        response = ollama.chat(
            model=brainrot_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.8, "num_predict": 500},
        )
        content = response["message"]["content"]
        result = _extract_json(content)

        if not result.get("hook"):
            result["hook"] = niche_config["hook"]

        raw_script = result.get("script", "")
        if isinstance(raw_script, dict):
            texts = []
            cues = []
            for key in sorted(
                raw_script.keys(), key=lambda k: float(k) if str(k).replace(".", "", 1).isdigit() else 999
            ):
                entry = raw_script[key]
                if isinstance(entry, dict):
                    texts.append(entry.get("text", str(entry)))
                    t_val = entry.get(
                        "time", entry.get("timetye", float(key) if str(key).replace(".", "", 1).isdigit() else 0)
                    )
                    try:
                        t_val = float(t_val) if t_val is not None else 0.0
                    except (ValueError, TypeError):
                        t_val = float(key) if str(key).replace(".", "", 1).isdigit() else 0
                    cues.append({"time": t_val, "text": entry.get("text", str(entry))[:100]})
            result["script"] = " ".join(texts) if texts else idea_text
            if not result.get("caption_cues"):
                result["caption_cues"] = cues
        elif raw_script:
            result["script"] = str(raw_script)
        else:
            result["script"] = idea_text

        if not result.get("caption_cues"):
            result["caption_cues"] = [
                {"time": 0, "text": result["hook"][:100]},
                {"time": 5, "text": result["script"][:100]},
                {"time": 10, "text": "Like and follow for more!"},
            ]

        for cue in result.get("caption_cues", []):
            if "time" not in cue:
                for alt_key in ("timetye", "time end", "time_end", "start"):
                    if alt_key in cue:
                        cue["time"] = cue.pop(alt_key)
                        break
            cue["time"] = float(cue.get("time", 0))
            cue["text"] = str(cue.get("text", ""))[:200]

        result["niche"] = niche
        result["caption_style"] = caption_style
        result["generated_at"] = datetime.now(UTC).isoformat()
        return result
    except Exception as e:
        logger.error(f"Brainrot script generation failed: {e}")
        return {
            "hook": niche_config["hook"],
            "script": idea_text
            or f"Let me tell you about {niche}... It's wild out there. You won't believe what people are doing. This changes everything. Comment your thoughts below!",
            "caption_cues": [
                {"time": 0, "text": niche_config["hook"]},
                {"time": 5, "text": idea_text or niche},
                {"time": 10, "text": "Follow for daily content 🔥"},
            ],
            "niche": niche,
            "caption_style": caption_style,
            "generated_at": datetime.now(UTC).isoformat(),
        }


def _generate_tts(script_text: str, output_path: str) -> str:
    """Generate TTS audio from script text using gTTS."""
    try:
        from gtts import gTTS

        tts = gTTS(text=script_text, lang="en", slow=False)
        tts.save(output_path)
        if os.path.exists(output_path):
            logger.info(f"TTS audio saved to {output_path}")
            return output_path
    except Exception as e:
        logger.warning(f"TTS generation failed (fallback to no audio): {e}")
    return ""


def _generate_background_music(output_path: str, duration: float = 30) -> str:
    """Generate a simple ambient background music track using ffmpeg sine waves."""
    try:
        # Create a simple ambient beat from overlapping sine waves
        freqs = [220, 294, 330, 392]
        f1, f2 = random.sample(freqs, 2)
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc=sin({f1}*2*PI*t)*0.15 + sin({f2}*2*PI*t)*0.1:d={duration}:c=stereo:s=44100",
            "-af",
            "volume=0.3,afftdn=nf=-20,lowpass=f=1000,adelay=500|500",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path):
            return output_path
    except Exception as e:
        logger.warning(f"Background music generation failed: {e}")
    return ""


def _generate_dynamic_background(output_path: str, duration: int = 30) -> str:
    """Generate a dynamic animated gradient background using FFmpeg."""
    try:
        palette = [
            ("0x1a0a2e", "0x16213e"),
            ("0x0f3460", "0x533483"),
            ("0x2d1b69", "0x1a0a2e"),
            ("0x16213e", "0x0f3460"),
            ("0x533483", "0x2d1b69"),
        ]
        c1, c2 = random.choice(palette)

        # Animate between two colors using blend and a moving gradient
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={c1}:s=1080x1920:d={duration}:r=30",
            "-f",
            "lavfi",
            "-i",
            f"color=c={c2}:s=1080x1920:d={duration}:r=30",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=1080x1920:d=30:r=30",
            "-filter_complex",
            "[0:v][1:v]blend=all_mode=overlay:all_opacity=0.3[base];"
            "[2:v]format=rgba,geq=r='255*abs(sin(X/200+T/2))':"
            "g='255*abs(sin(X/200+T/2+2))':"
            "b='255*abs(sin(X/200+T/2+4))':a=0.15[mask];"
            "[base][mask]overlay[out]",
            "-map",
            "[out]",
            "-t",
            str(duration),
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)
        if os.path.exists(output_path):
            return output_path
    except Exception as e:
        logger.warning(f"Dynamic background failed: {e}")

    # Fallback: solid color
    try:
        color = "0x1a0a2e"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=1080x1920:d={duration}:r=30", output_path],
            capture_output=True,
            timeout=30,
        )
        return output_path if os.path.exists(output_path) else ""
    except Exception:
        return ""


def render_brainrot_video(script_data: dict, output_path: str, background_video: str = "") -> bool:
    """Render a brain rot short video with captions, TTS voiceover, and background music."""
    caption_style = CAPTION_STYLES.get(script_data.get("caption_style", "brain_rot"), CAPTION_STYLES["brain_rot"])
    cues = script_data.get("caption_cues", [])
    script_text = script_data.get("script", "")

    # Duration based on script length (rough: 150 words/min = 2.5 words/sec)
    word_count = len(script_text.split())
    duration = max(15, min(45, int(word_count / 2.5) + 3))

    # Generate or use background video
    temp_files = []
    if background_video and os.path.exists(background_video):
        bg_path = background_video
    else:
        bg_path = _generate_dynamic_background(output_path.replace(".mp4", "_bg.mp4"), duration)
        temp_files.append(bg_path)

    if not bg_path or not os.path.exists(bg_path):
        logger.error("Failed to create background video")
        return False

    # Probe actual background duration
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                bg_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if probe.stdout.strip():
            bg_duration = float(probe.stdout.strip())
            if bg_duration < duration:
                # Loop background to fill duration via concat
                loop_path = output_path.replace(".mp4", "_loop.mp4")
                loop_cmd = [
                    "ffmpeg",
                    "-y",
                    "-stream_loop",
                    "-1",
                    "-i",
                    bg_path,
                    "-t",
                    str(duration),
                    "-c",
                    "copy",
                    loop_path,
                ]
                subprocess.run(loop_cmd, capture_output=True, timeout=60)
                bg_path = loop_path
                temp_files.append(loop_path)
    except Exception:
        pass

    # Generate captions
    caption_pngs = _generate_caption_pngs(cues, caption_style)
    temp_files.extend([p for p in caption_pngs if p and os.path.exists(p)])
    tts_audio = ""
    bg_music = ""

    # Generate TTS audio
    if script_text:
        tts_path = output_path.replace(".mp4", "_tts.mp3")
        tts_audio = _generate_tts(script_text, tts_path)
        if tts_audio:
            temp_files.append(tts_audio)

    # Generate background music
    music_path = output_path.replace(".mp4", "_music.aac")
    bg_music = _generate_background_music(music_path, duration)
    if bg_music:
        temp_files.append(bg_music)

    try:
        # Build FFmpeg command
        inputs = ["-i", bg_path]
        filter_parts = ["[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg]"]
        prev_label = "bg"

        for i, (cue, png_path) in enumerate(zip(cues, caption_pngs, strict=False)):
            if not png_path or not os.path.exists(png_path):
                continue
            t = float(cue.get("time", i * 5))
            text = cue.get("text", "")
            if not text:
                continue

            start = max(0, t)
            end = min(duration, start + 4.0)
            y_pct = "0.35" if i == 0 else ("0.50" if i == 1 else "0.65")
            input_idx = i + 1
            inputs.extend(["-i", png_path])
            out_label = f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{input_idx}:v]overlay=x=(W-w)/2:y=H*{y_pct}"
                f":enable=between(t\\,{start}\\,{end})[{out_label}]"
            )
            prev_label = out_label

        # Audio setup — merge into single filter_complex
        num_video_inputs = len(inputs) // 2
        audio_inputs = []
        audio_idx = num_video_inputs

        if bg_music and os.path.exists(bg_music):
            audio_inputs.extend(["-i", bg_music])
            filter_parts.append(f"[{audio_idx}:a]volume=0.3[music]")
            audio_idx += 1

        if tts_audio and os.path.exists(tts_audio):
            audio_inputs.extend(["-i", tts_audio])
            filter_parts.append(f"[{audio_idx}:a]volume=1.5[voice]")
            audio_idx += 1

        filter_complex = ";".join(filter_parts)

        # Build audio map: mix if multiple sources, else silent
        has_music = bg_music and os.path.exists(bg_music)
        has_voice = tts_audio and os.path.exists(tts_audio)

        if has_music and has_voice:
            filter_complex += ";[music][voice]amix=inputs=2:duration=first[audio]"
            audio_map = ["-map", "[audio]", "-c:a", "aac", "-b:a", "96k", "-shortest"]
        elif has_music:
            audio_map = ["-map", "[music]", "-c:a", "aac", "-b:a", "96k", "-shortest"]
        elif has_voice:
            audio_map = ["-map", "[voice]", "-c:a", "aac", "-b:a", "96k", "-shortest"]
        else:
            audio_inputs.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
            audio_map = ["-map", f"{num_video_inputs}:a", "-c:a", "aac", "-b:a", "64k", "-shortest"]

        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            *audio_inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            f"[{prev_label}]",
            *audio_map,
            "-t",
            str(duration),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            output_path,
        ]

        logger.info(f"Rendering brainrot video ({duration}s, {len(caption_pngs)} captions)")
        result = subprocess.run(cmd, capture_output=True, timeout=180, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr[-500:]}")
            return _render_fallback(bg_path, output_path, duration)
        return os.path.exists(output_path)
    except Exception as e:
        logger.error(f"Brainrot render exception: {e}")
        return _render_fallback(bg_path, output_path, duration)
    finally:
        _cleanup_temp_files(temp_files)


def _render_fallback(bg_path: str, output_path: str, duration: int) -> bool:
    """Fallback: copy background with silent audio if main render fails."""
    try:
        "-i" if os.path.exists(bg_path) else "-f lavfi -i color=c=#1a0a2e:s=1080x1920:d=30:r=30"
        if os.path.exists(bg_path):
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                bg_path,
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=#1a0a2e:s=1080x1920:r=30",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-c:a",
                "aac",
                "-t",
                str(duration),
                output_path,
            ]
        subprocess.run(cmd, capture_output=True, timeout=60)
        return os.path.exists(output_path)
    except Exception:
        return False


def _cleanup_temp_files(files: list):
    for f in files:
        if f and os.path.exists(f):
            with contextlib.suppress(Exception):
                os.remove(f)


def _generate_caption_pngs(cues: list, style: dict) -> list:
    """Generate transparent PNG images for each caption cue using Pillow."""
    pngs = []
    font_path = _find_font()
    font_size = style.get("fontsize", 56)
    borderw = style.get("borderw", 3)
    font_color = style.get("fontcolor", "white")
    border_color = style.get("bordercolor", "black")

    for i, cue in enumerate(cues):
        text = cue.get("text", "")
        if not text:
            pngs.append("")
            continue

        font: ImageFont.ImageFont | ImageFont.FreeTypeFont
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        dummy = Image.new("RGBA", (1080, 300), (0, 0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy)

        # Wrap text to fit 1080px width
        wrapped_lines = []
        for line in text.split("\n"):
            words = line.split()
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = dummy_draw.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
                if w < 1000:
                    current_line = test_line
                else:
                    wrapped_lines.append(current_line)
                    current_line = word
            wrapped_lines.append(current_line)

        display_text = "\n".join(wrapped_lines) if wrapped_lines else text

        # Measure wrapped text
        text_bbox = dummy_draw.textbbox((0, 0), display_text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Add semi-transparent background box behind text
        box_pad = 20
        y_positions = [0.35, 0.50, 0.65]
        y_val = y_positions[i] if i < len(y_positions) else 0.50
        text_y_center = int(1920 * y_val)
        box_top = text_y_center - text_h // 2 - box_pad
        box_bottom = text_y_center + text_h // 2 + box_pad
        draw.rounded_rectangle(
            [
                (1080 - min(text_w + box_pad * 2, 1060)) // 2,
                box_top,
                (1080 + min(text_w + box_pad * 2, 1060)) // 2,
                box_bottom,
            ],
            radius=12,
            fill=(0, 0, 0, 160),
        )

        text_x = (1080 - text_w) // 2
        text_y = text_y_center - text_h // 2

        # Draw border
        for dx in range(-borderw, borderw + 1):
            for dy in range(-borderw, borderw + 1):
                if dx * dx + dy * dy <= borderw * borderw:
                    draw.multiline_text(
                        (text_x + dx, text_y + dy),
                        display_text,
                        fill=_parse_color(border_color, 200),
                        font=font,
                        align="center",
                    )

        # Draw fill text
        draw.multiline_text(
            (text_x, text_y), display_text, fill=_parse_color(font_color, 255), font=font, align="center"
        )

        png_path = os.path.join(tempfile.gettempdir(), f"brainrot_cap_{i}_{random.randint(10000, 99999)}.png")
        img.save(png_path)
        pngs.append(png_path)

    return pngs


def _parse_color(color_str: str, alpha: int = 255) -> tuple:
    color_map = {
        "white": (255, 255, 255, alpha),
        "black": (0, 0, 0, alpha),
        "yellow": (255, 255, 0, alpha),
        "red": (255, 0, 0, alpha),
        "green": (0, 255, 0, alpha),
        "blue": (0, 0, 255, alpha),
    }
    if color_str.lower() in color_map:
        return color_map[color_str.lower()]
    return (255, 255, 255, alpha)


def _find_font() -> str:
    candidates = [
        "/System/Library/Fonts/Impact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/usr/share/fonts/truetype/impact/impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/Impact.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(
            ["fc-match", "-v", "Impact", "--format=%{file}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stdout.strip() and os.path.exists(result.stdout.strip()):
            return result.stdout.strip()
    except Exception:
        pass
    return "/System/Library/Fonts/Helvetica.ttc"
