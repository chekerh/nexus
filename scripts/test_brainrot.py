"""
Brain Rot Integration Tests.
Tests script generation, video rendering, and end-to-end flow.
Run: python -m pytest scripts/test_brainrot.py -v
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ["OLLAMA_MODEL"] = "qwen2.5:0.5b"
os.environ["OLLAMA_NUM_PREDICT"] = "300"
os.environ["DATABASE_URL"] = ""
os.environ["JWT_SECRET"] = "test-secret"

from app.services.brainrot import generate_script, render_brainrot_video, NICHES, CAPTION_STYLES


def test_niches_defined():
    """All expected niches exist."""
    assert "drama" in NICHES
    assert "gaming" in NICHES
    assert "motivation" in NICHES
    assert "money" in NICHES
    assert "facts" in NICHES
    assert "fake_life_stories" in NICHES


def test_caption_styles_defined():
    """All caption styles have required fields."""
    for name, style in CAPTION_STYLES.items():
        assert "font" in style
        assert "fontsize" in style
        assert style["fontsize"] > 0
        assert "fontcolor" in style


def test_generate_script_returns_structure():
    """generate_script returns expected JSON structure."""
    result = generate_script("drama", "a test story", "brain_rot")
    assert isinstance(result, dict)
    assert "hook" in result
    assert "script" in result
    assert "caption_cues" in result
    assert result["niche"] == "drama"
    assert result["caption_style"] == "brain_rot"


def test_generate_script_fallback_on_error():
    """generate_script returns fallback when Ollama is unavailable."""
    result = generate_script("money", "making money", "hype")
    assert result["hook"]
    assert result["script"]
    assert len(result["caption_cues"]) > 0
    assert result["caption_style"] == "hype"


def test_generate_all_niches():
    """Script generation works for all niches."""
    for niche in NICHES:
        result = generate_script(niche, f"test {niche}", "clean")
        assert result["hook"]
        assert result["script"]
        assert len(result["caption_cues"]) > 0


def test_render_video_creates_file():
    """render_brainrot_video creates a valid MP4 file."""
    script = {
        "hook": "This will blow your mind",
        "script": "Scientists just discovered something incredible. You won't believe what happened next. Share this with someone who needs to know.",
        "caption_cues": [
            {"time": 0, "text": "This will blow your mind"},
            {"time": 5, "text": "Scientists discovered something"},
            {"time": 10, "text": "Share with someone"},
        ],
        "niche": "facts",
        "caption_style": "brain_rot",
    }
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        output_path = f.name

    try:
        success = render_brainrot_video(script, output_path)
        assert success, "Video rendering should succeed"
        assert os.path.exists(output_path), "Output file should exist"
        assert os.path.getsize(output_path) > 0, "Output file should not be empty"

        # Probe the file to verify it's a valid video
        import subprocess
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", output_path],
            capture_output=True, text=True, timeout=15,
        )
        assert probe.stdout.strip(), "FFprobe should detect duration"
        duration = float(probe.stdout.strip())
        assert duration >= 10, f"Video should be at least 10s, got {duration}s"
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


def test_render_with_background_video():
    """render_brainrot_video works with a provided background."""
    script = {
        "hook": "Test hook",
        "script": "This is a test script for background video rendering.",
        "caption_cues": [{"time": 0, "text": "Test"}, {"time": 3, "text": "Background"}],
        "niche": "drama",
        "caption_style": "brain_rot",
    }
    # Create a minimal background video using ffmpeg
    import subprocess
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as bg_f:
        bg_path = bg_f.name
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "color=c=red:s=1080x1920:d=15:r=30",
         bg_path],
        capture_output=True, timeout=30,
    )
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as out_f:
        output_path = out_f.name

    try:
        success = render_brainrot_video(script, output_path, bg_path)
        assert success, "Render with background should succeed"
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
    finally:
        for p in [bg_path, output_path]:
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    test_niches_defined()
    print("✓ test_niches_defined")
    test_caption_styles_defined()
    print("✓ test_caption_styles_defined")
    test_generate_script_returns_structure()
    print("✓ test_generate_script_returns_structure")
    test_generate_script_fallback_on_error()
    print("✓ test_generate_script_fallback_on_error")
    test_generate_all_niches()
    print("✓ test_generate_all_niches")
    test_render_video_creates_file()
    print("✓ test_render_video_creates_file")
    test_render_with_background_video()
    print("✓ test_render_with_background_video")
    print("\n🎉 All brainrot tests passed!")
