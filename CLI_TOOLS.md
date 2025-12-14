# 🛠️ CLI Tools Guide

## 🎥 Regenerate Videos from Existing Images

Use `regenerate_video.py` to create new videos from already-downloaded images without hitting the API again!

---

## 📋 Quick Commands

### List all your projects
```bash
python regenerate_video.py --list
```

### Regenerate with different FPS
```bash
python regenerate_video.py --project <project_id> --fps 20
```

### Add music to existing project
```bash
python regenerate_video.py --project <project_id> --audio my_music.mp3
```

### Both FPS and music
```bash
python regenerate_video.py --project <project_id> --fps 15 --audio audio_samples/upbeat.mp3
```

---

## 🎯 Use Cases

### 1. Fix Choppy Video
Your video seems choppy? Regenerate with higher FPS:
```bash
# Original was 10 FPS, try 20 FPS
python regenerate_video.py --project <project_id> --fps 20
```

### 2. Add Background Music
Forgot to add music? No problem:
```bash
# Download music first, then:
python regenerate_video.py --project <project_id> --audio my_track.mp3
```

### 3. Try Different Settings
Experiment without re-downloading images:
```bash
# Slower playback
python regenerate_video.py --project <project_id> --fps 8

# Faster playback
python regenerate_video.py --project <project_id> --fps 24
```

### 4. Fix Corrupted Video
If video generation failed or was interrupted:
```bash
python regenerate_video.py --project <project_id>
```

---

## 📖 Full Options

```bash
python regenerate_video.py --help
```

**Options:**
- `--list, -l` - List all projects
- `--project, -p <id>` - Project ID to regenerate
- `--fps <number>` - New FPS (default: use original)
- `--audio, -a <file>` - Add audio file
- `--output, -o <filename>` - Output filename (default: video_regenerated.mp4)

---

## 🔍 Finding Your Project ID

### Method 1: List command
```bash
python regenerate_video.py --list
```

### Method 2: Check projects folder
```bash
ls projects/
```

Project IDs look like:
- `santamonicapier_venicebeachboardwalk_20251214_074335`
- `timessquare_centralpark_20251214_063245`

---

## 💡 Pro Tips

### Tip 1: Test FPS values
```bash
# Try 3-4 different FPS values to find what you like
python regenerate_video.py -p <id> --fps 10 -o video_10fps.mp4
python regenerate_video.py -p <id> --fps 15 -o video_15fps.mp4
python regenerate_video.py -p <id> --fps 20 -o video_20fps.mp4
```

### Tip 2: Batch process
```bash
# Add music to all your videos
for project in projects/*/; do
    python regenerate_video.py --project $(basename $project) --audio my_music.mp3
done
```

### Tip 3: Keep originals
The script creates `video_regenerated.mp4` by default, so your original `video.mp4` is safe!

---

## 📊 FPS Guide

| FPS | Use Case | Video Feel |
|-----|----------|------------|
| 5-8 | Time-lapse effect | Very fast |
| 10-12 | Quick preview | Fast |
| **15-18** | **Recommended** | **Smooth & natural** |
| 20-24 | Cinema quality | Very smooth |
| 30+ | Overkill | Huge file sizes |

---

## 🎵 Adding Music

### Step 1: Download music
See `DOWNLOAD_MUSIC.md` for sources

### Step 2: Place in project
```bash
# Option A: Use audio_samples folder
cp ~/Downloads/my_music.mp3 audio_samples/

# Option B: Put anywhere
# Just reference the path
```

### Step 3: Regenerate with audio
```bash
python regenerate_video.py --project <id> --audio audio_samples/my_music.mp3
```

---

## ⚠️ Troubleshooting

### "No images found"
Check that the project folder has an `images/` subdirectory:
```bash
ls projects/<project_id>/images/
```

### "FFmpeg error"
Make sure FFmpeg is installed:
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg

# Test it
ffmpeg -version
```

### "Project not found"
Use `--list` to see correct project IDs:
```bash
python regenerate_video.py --list
```

---

## 🚀 Example Workflow

```bash
# 1. See what you have
python regenerate_video.py --list

# 2. Pick a project (copy the ID)

# 3. Download some music
# (Visit pixabay.com/music)

# 4. Regenerate with music and better FPS
python regenerate_video.py \
  --project santamonicapier_venicebeachboardwalk_20251214_074335 \
  --fps 18 \
  --audio audio_samples/upbeat_travel.mp3 \
  --output my_awesome_video.mp4

# 5. Done! Video is saved in the project folder
```

---

## 💰 Cost Savings

**The best part:** Regenerating is **100% FREE**!
- No API calls
- Uses existing images
- Unlimited regenerations
- Try different settings risk-free

---

## 🎬 Quick Reference

| Task | Command |
|------|---------|
| List projects | `python regenerate_video.py -l` |
| Basic regen | `python regenerate_video.py -p <id>` |
| Change FPS | `python regenerate_video.py -p <id> --fps 20` |
| Add music | `python regenerate_video.py -p <id> -a music.mp3` |
| Both | `python regenerate_video.py -p <id> --fps 20 -a music.mp3` |
| Custom output | `python regenerate_video.py -p <id> -o my_video.mp4` |

---

## 📖 See Also

- `DOWNLOAD_MUSIC.md` - How to get background music
- `ENHANCEMENTS_SUMMARY.md` - All new features
- `START_HERE.md` - Main guide

Happy video making! 🎬

