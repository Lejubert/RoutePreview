# 🎬 Street View to Video

Transform any route into a cinematic Street View journey. Enter a start and end location, and this app creates a smooth video by stitching together Google Street View images along the path.

![Street View to Video](https://img.shields.io/badge/Made%20with-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)

## ✨ Features

- 🗺️ **Interactive Map Preview** - See your route before generating
- 📍 **Address Geocoding** - Just type any address
- 🎚️ **Customizable Settings** - Adjust FPS, interval, camera angle
- 💰 **Cost Estimator** - Know your API costs upfront
- 🎥 **Instant Preview & Download** - Watch and download your video

## 🚀 Quick Start

### Prerequisites

1. **Python 3.9+**
2. **FFmpeg** - Required for video creation
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # Windows (with chocolatey)
   choco install ffmpeg
   ```

3. **Google API Key** with these APIs enabled:
   - Maps JavaScript API
   - Geocoding API
   - Directions API
   - Street View Static API

### Installation

```bash
# Clone or navigate to the project
cd street_view_to_video

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_api_key_here
```

### Run the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## 📖 Usage

1. **Enter Locations** - Type your starting point and destination
2. **Adjust Settings** - Use the sidebar to customize:
   - Image interval (meters between captures)
   - Video FPS
   - Camera field of view
   - Camera pitch (up/down angle)
3. **Generate** - Click "Generate Video"
4. **Download** - Preview and download your video

## 💰 Cost Information

Google Street View Static API pricing:
- **$7.00 per 1,000 requests**
- **$200/month free credit** (~28,500 free images)

| Route Length | Images @20m | Est. Cost |
|--------------|-------------|-----------|
| 1 km         | 50          | $0.35     |
| 5 km         | 250         | $1.75     |
| 10 km        | 500         | $3.50     |

Most personal projects will stay within the free tier!

## 🗂️ Project Structure

```
street_view_to_video/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── .env               # Your API key (not in git)
├── .gitignore
├── output/            # Generated videos
└── temp/              # Temporary images (auto-cleaned)
```

## ⚠️ Limitations

- Max image resolution: 640x640 pixels
- Some areas may have sparse Street View coverage
- Rural/private roads may not have imagery

## 📝 License

MIT License - Use freely for personal projects!

