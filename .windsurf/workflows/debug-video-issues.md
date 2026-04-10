---
description: Debug video processing issues (end screen, captions, FFmpeg)
---

# Debug Video Processing Issues

## Common Issues Checklist

### 1. End Screen Not Appending
- [ ] Check video dimensions match end screen after scaling
- [ ] Verify FFmpeg filter syntax compatible with version (8.0+)
- [ ] Test with simple scale filter first: `scale=1080:1920`
- [ ] Check `concat` filter inputs have identical dimensions and SAR

### 2. Captions Not Burning
- [ ] Check `subtitles` filter available: `ffmpeg -filters | grep subtitles`
- [ ] Verify drawtext escaping: single quotes `'` → `\\'`, colons `:` → `\\:`
- [ ] Test drawtext enable syntax: `between(t\,start\,end)` with escaped commas
- [ ] Check font file exists: `/System/Library/Fonts/Helvetica.ttc`

### 3. FFmpeg Filter Debugging
```bash
# Test filter complex manually
ffmpeg -i clip.mp4 -i endscreen.png -filter_complex "[0:v]fade=t=out:st=24.5:d=0.5[clip]; [1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[end]; [clip][end]concat=n=2:v=1:a=0" -t 5 -y test.mp4
```

### 4. Key Files
- `backend/app/core/video_editor.py` - End screen, captions, FFmpeg filters
- `backend/app/core/drive_downloader.py` - Google Drive downloads
- `frontend/script.js` - Download buttons UI

## Testing Commands
```bash
# Check FFmpeg version
ffmpeg -version | head -1

# Test filter availability
ffmpeg -filters | grep -E "(drawtext|subtitles|fade|concat)"

# Verify end screen dimensions
ffprobe -v error -show_entries stream=width,height endscreen.png

# Check video clip dimensions
ffprobe -v error -show_entries stream=width,height clip.mp4
```
