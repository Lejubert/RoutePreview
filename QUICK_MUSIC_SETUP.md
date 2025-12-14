# 🎵 Quick Music Setup (2 Minutes!)

## ⚡ Fastest Method

### Step 1: Download Music (1 minute)

Click these direct links to download royalty-free music:

**Option A: Pixabay (No Attribution Needed)**

1. Go to: https://pixabay.com/music/
2. Search for "travel" or "ambient"
3. Click any track you like
4. Click green "Download" button
5. Save the MP3 file

**Quick Recommendations:**
- **Upbeat**: Search "upbeat travel" → Download first result
- **Calm**: Search "ambient calm" → Download first result

### Step 2: Add to Project (30 seconds)

```bash
# Navigate to your project
cd /Users/aldrinjenson/personal/code/street_view_to_video

# Move downloaded files to audio_samples folder
mv ~/Downloads/music-*.mp3 audio_samples/upbeat_travel.mp3

# Or if you downloaded multiple:
mv ~/Downloads/upbeat.mp3 audio_samples/upbeat_travel.mp3
mv ~/Downloads/calm.mp3 audio_samples/calm_journey.mp3
```

### Step 3: Restart App (10 seconds)

```bash
# Stop Streamlit (Ctrl+C)
# Restart:
streamlit run app_enhanced.py
```

Done! Now "Sample: Upbeat Travel" will work in the dropdown! 🎉

---

## 🎯 Alternative: Use "Upload Custom"

Don't want to rename files? Just use "Upload Custom" in the app:

1. Download any MP3
2. In the app, select "Upload Custom"
3. Browse and select your MP3
4. Done!

This is easier but you have to upload each time.

---

## 📥 Direct Download Links

### Recommended Free Tracks (No Attribution)

**From Pixabay:**
1. https://pixabay.com/music/beats-chill-abstract-intention-12099/
2. https://pixabay.com/music/beats-lofi-study-112191/
3. https://pixabay.com/music/upbeat-success-inspirational-hip-hop-112461/

**Click → Download → Save to `audio_samples/`**

---

## 🎼 What to Name Your Files

For the app presets to work, name them:
- `upbeat_travel.mp3` - For "Sample: Upbeat Travel"
- `calm_journey.mp3` - For "Sample: Calm Journey"

Or name them anything and use "Upload Custom"!

---

## 💡 Pro Tip: Bulk Download

Want 5-10 tracks to choose from?

```bash
# Download several tracks from Pixabay
# Save to audio_samples/ with descriptive names:

audio_samples/
├── upbeat_travel.mp3      # For app preset
├── calm_journey.mp3       # For app preset
├── energetic_city.mp3     # Extra
├── peaceful_sunset.mp3    # Extra
└── epic_cinematic.mp3     # Extra
```

Then use "Upload Custom" to choose any of them!

---

## 🔧 Shell Script (Advanced)

Want to automate? Create `download_sample_music.sh`:

```bash
#!/bin/bash
mkdir -p audio_samples
cd audio_samples

echo "📥 Download 2 free tracks from Pixabay:"
echo "1. Visit: https://pixabay.com/music/search/travel/"
echo "2. Download 2 tracks you like"
echo "3. Move them here and rename:"
echo "   - upbeat_travel.mp3"
echo "   - calm_journey.mp3"
echo ""
echo "Current files in audio_samples/:"
ls -lh
```

---

## ✅ Verify Setup

Check if music is ready:

```bash
ls -lh audio_samples/
```

Should see:
```
upbeat_travel.mp3   (3-5 MB)
calm_journey.mp3    (3-5 MB)
```

---

## 🆘 Troubleshooting

### "Sample music not found"
- Check filename: Must be exactly `upbeat_travel.mp3` or `calm_journey.mp3`
- Check location: Must be in `audio_samples/` folder
- Restart Streamlit after adding files

### "Upload Custom doesn't show"
- Make sure you selected "Upload Custom" from dropdown
- Any MP3 file works with Upload Custom

### Don't want to deal with this?
- Just select "None" for now
- Generate silent videos
- Add music later using CLI tool:
  ```bash
  python regenerate_video.py --project <id> --audio your_music.mp3
  ```

---

## 🎬 My Recommendation

**For now:**
1. Select "None" in the app
2. Generate your video
3. Download 1-2 tracks when you have time
4. Use CLI tool to add music:
   ```bash
   python regenerate_video.py --project <project_id> --audio music.mp3
   ```

This way you can generate videos immediately and add music later!

---

**Need help?** The app works perfectly without music - it's totally optional! 🎵

