"""
Street View to Video Generator
A Streamlit app that creates videos from Google Street View images along a route.
"""

import os
import shutil
import subprocess
import math
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
import requests
import polyline
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

# Load environment variables
load_dotenv()

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TEMP_DIR = Path("temp")
OUTPUT_DIR = Path("output")

# Create directories
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def geocode_address(address: str) -> tuple[float, float] | None:
    """Convert an address to lat/lng coordinates."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return (location["lat"], location["lng"])
    return None


def get_route(origin: tuple, destination: tuple) -> dict | None:
    """Get route between two points using Google Directions API."""
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "key": GOOGLE_API_KEY,
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data["status"] == "OK":
        route = data["routes"][0]
        return {
            "polyline": route["overview_polyline"]["encoded"],
            "distance": route["legs"][0]["distance"]["text"],
            "duration": route["legs"][0]["duration"]["text"],
            "start_address": route["legs"][0]["start_address"],
            "end_address": route["legs"][0]["end_address"],
        }
    return None


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google polyline into a list of coordinates."""
    return polyline.decode(encoded)


def calculate_distance(point1: tuple, point2: tuple) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    
    lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
    lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def calculate_heading(point1: tuple, point2: tuple) -> float:
    """Calculate the heading (bearing) from point1 to point2."""
    lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
    lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
    
    dlon = lon2 - lon1
    
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    heading = math.degrees(math.atan2(x, y))
    return (heading + 360) % 360


def sample_points_along_route(points: list[tuple], interval_meters: float) -> list[dict]:
    """Sample points along the route at regular intervals with headings."""
    sampled = []
    accumulated_distance = 0
    
    for i in range(len(points) - 1):
        current = points[i]
        next_point = points[i + 1]
        segment_distance = calculate_distance(current, next_point)
        heading = calculate_heading(current, next_point)
        
        # Add points along this segment
        while accumulated_distance <= segment_distance:
            # Interpolate position
            if segment_distance > 0:
                ratio = accumulated_distance / segment_distance
            else:
                ratio = 0
            
            lat = current[0] + ratio * (next_point[0] - current[0])
            lng = current[1] + ratio * (next_point[1] - current[1])
            
            sampled.append({
                "lat": lat,
                "lng": lng,
                "heading": heading,
            })
            
            accumulated_distance += interval_meters
        
        accumulated_distance -= segment_distance
    
    # Add the final point
    if points:
        last = points[-1]
        sampled.append({
            "lat": last[0],
            "lng": last[1],
            "heading": sampled[-1]["heading"] if sampled else 0,
        })
    
    return sampled


def fetch_street_view_image(lat: float, lng: float, heading: float, 
                            size: str = "640x640", fov: int = 90, pitch: int = 0) -> bytes | None:
    """Fetch a single Street View image."""
    url = "https://maps.googleapis.com/maps/api/streetview"
    params = {
        "location": f"{lat},{lng}",
        "heading": heading,
        "size": size,
        "fov": fov,
        "pitch": pitch,
        "key": GOOGLE_API_KEY,
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.content
    return None


def check_street_view_availability(lat: float, lng: float) -> bool:
    """Check if Street View is available at a location."""
    url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {
        "location": f"{lat},{lng}",
        "key": GOOGLE_API_KEY,
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    return data.get("status") == "OK"


def create_video_from_images(image_dir: Path, output_path: Path, fps: int = 10) -> bool:
    """Create video from images using FFmpeg."""
    # Get all images sorted by name
    images = sorted(image_dir.glob("*.jpg"))
    
    if not images:
        return False
    
    # Create a file list for FFmpeg
    list_file = image_dir / "images.txt"
    with open(list_file, "w") as f:
        for img in images:
            f.write(f"file '{img.absolute()}'\n")
            f.write(f"duration {1/fps}\n")
    
    # Run FFmpeg
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-vf", "scale=640:640:force_original_aspect_ratio=decrease,pad=640:640:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        st.error(f"FFmpeg error: {e}")
        return False


def cleanup_temp_dir():
    """Remove all files in the temp directory."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        TEMP_DIR.mkdir(exist_ok=True)


# ============================================================================
# STREAMLIT UI
# ============================================================================

# Page config
st.set_page_config(
    page_title="Street View to Video",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a beautiful dark theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    :root {
        --bg-primary: #0a0a0f;
        --bg-secondary: #12121a;
        --bg-tertiary: #1a1a24;
        --accent-primary: #6366f1;
        --accent-secondary: #8b5cf6;
        --accent-glow: rgba(99, 102, 241, 0.3);
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --border-color: #2a2a3a;
    }
    
    .stApp {
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0f0f1a 50%, var(--bg-primary) 100%);
    }
    
    /* Header styling */
    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
        margin-bottom: 2rem;
    }
    
    .main-header h1 {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 3.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
    }
    
    .main-header p {
        font-family: 'Space Grotesk', sans-serif;
        color: var(--text-secondary);
        font-size: 1.2rem;
        font-weight: 300;
    }
    
    /* Card styling */
    .stCard, [data-testid="stExpander"] {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 16px !important;
    }
    
    /* Input styling */
    .stTextInput > div > div > input {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        color: var(--text-primary) !important;
        font-family: 'Space Grotesk', sans-serif !important;
        padding: 0.75rem 1rem !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px var(--accent-glow) !important;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
        padding: 0.75rem 2rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px var(--accent-glow) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px var(--accent-glow) !important;
    }
    
    /* Slider styling */
    .stSlider > div > div > div > div {
        background: var(--accent-primary) !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: var(--bg-secondary) !important;
        border-right: 1px solid var(--border-color) !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown h2 {
        font-family: 'Space Grotesk', sans-serif;
        color: var(--text-primary);
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    /* Metrics styling */
    [data-testid="stMetric"] {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--text-secondary) !important;
    }
    
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        color: var(--accent-primary) !important;
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary)) !important;
    }
    
    /* Info boxes */
    .info-box {
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
    }
    
    .info-box.success {
        border-color: #22c55e;
        background: rgba(34, 197, 94, 0.1);
    }
    
    .info-box.warning {
        border-color: #f59e0b;
        background: rgba(245, 158, 11, 0.1);
    }
    
    /* Route info card */
    .route-info {
        background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .route-info h3 {
        font-family: 'Space Grotesk', sans-serif;
        color: var(--text-primary);
        margin-bottom: 1rem;
        font-size: 1.1rem;
    }
    
    .route-stat {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border-color);
    }
    
    .route-stat:last-child {
        border-bottom: none;
    }
    
    .route-stat-label {
        color: var(--text-secondary);
        font-family: 'Space Grotesk', sans-serif;
    }
    
    .route-stat-value {
        color: var(--accent-primary);
        font-family: 'JetBrains Mono', monospace;
        font-weight: 500;
    }
    
    /* Video container */
    .video-container {
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1rem;
        margin-top: 1rem;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 2rem 0;
        color: var(--text-secondary);
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>🎬 Street View to Video</h1>
    <p>Transform any route into a cinematic Street View journey</p>
</div>
""", unsafe_allow_html=True)

# Check API key
if not GOOGLE_API_KEY:
    st.error("⚠️ Google API key not found! Please add `GOOGLE_API_KEY` to your `.env` file.")
    st.stop()

# Sidebar - Settings
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    
    st.markdown("### 📍 Image Capture")
    interval = st.slider(
        "Distance between images (meters)",
        min_value=10,
        max_value=100,
        value=20,
        step=5,
        help="Lower = smoother video, but more images & higher cost"
    )
    
    st.markdown("### 🎥 Video Settings")
    fps = st.slider(
        "Frames per second",
        min_value=5,
        max_value=30,
        value=10,
        step=1,
        help="Higher = faster playback"
    )
    
    fov = st.slider(
        "Field of view",
        min_value=30,
        max_value=120,
        value=90,
        step=10,
        help="Camera zoom level (90 is default)"
    )
    
    pitch = st.slider(
        "Camera pitch",
        min_value=-45,
        max_value=45,
        value=0,
        step=5,
        help="Camera up/down angle"
    )
    
    st.markdown("---")
    
    st.markdown("### 💰 Cost Estimator")
    st.caption("Based on $7 per 1,000 requests")
    
    if "estimated_images" in st.session_state:
        num_images = st.session_state.estimated_images
        cost = (num_images / 1000) * 7
        st.metric("Estimated Images", f"{num_images:,}")
        st.metric("Estimated Cost", f"${cost:.2f}")
        
        if cost <= 0.20:  # Within free tier
            st.success("✅ Within $200/month free tier!")

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 📍 Enter Your Route")
    
    origin = st.text_input(
        "Starting Point",
        placeholder="e.g., Times Square, New York",
        key="origin_input"
    )
    
    destination = st.text_input(
        "Destination",
        placeholder="e.g., Central Park, New York",
        key="destination_input"
    )
    
    generate_btn = st.button("🚀 Generate Video", type="primary", use_container_width=True)

with col2:
    st.markdown("### 🗺️ Route Preview")
    
    # Initialize map
    map_center = [40.7128, -74.0060]  # Default to NYC
    m = folium.Map(
        location=map_center,
        zoom_start=12,
        tiles="CartoDB dark_matter"
    )
    
    # Add route if available
    if "route_coords" in st.session_state and st.session_state.route_coords:
        coords = st.session_state.route_coords
        
        # Add polyline
        folium.PolyLine(
            coords,
            color="#6366f1",
            weight=4,
            opacity=0.8
        ).add_to(m)
        
        # Add markers
        folium.Marker(
            coords[0],
            popup="Start",
            icon=folium.Icon(color="green", icon="play")
        ).add_to(m)
        
        folium.Marker(
            coords[-1],
            popup="End",
            icon=folium.Icon(color="red", icon="stop")
        ).add_to(m)
        
        # Fit bounds
        m.fit_bounds([coords[0], coords[-1]])
    
    st_folium(m, width=None, height=400, use_container_width=True)

# Process route
if generate_btn and origin and destination:
    cleanup_temp_dir()
    
    with st.status("🎬 Creating your Street View video...", expanded=True) as status:
        # Step 1: Geocode addresses
        st.write("📍 Finding locations...")
        origin_coords = geocode_address(origin)
        dest_coords = geocode_address(destination)
        
        if not origin_coords or not dest_coords:
            st.error("❌ Could not find one or both locations. Please try different addresses.")
            st.stop()
        
        st.write(f"✅ Found: {origin} → {destination}")
        
        # Step 2: Get route
        st.write("🛣️ Calculating route...")
        route = get_route(origin_coords, dest_coords)
        
        if not route:
            st.error("❌ Could not find a route between these locations.")
            st.stop()
        
        # Decode and store route
        route_coords = decode_polyline(route["polyline"])
        st.session_state.route_coords = route_coords
        
        st.write(f"✅ Route: {route['distance']} ({route['duration']})")
        
        # Step 3: Sample points
        st.write("📸 Calculating image positions...")
        sampled_points = sample_points_along_route(route_coords, interval)
        num_images = len(sampled_points)
        st.session_state.estimated_images = num_images
        
        st.write(f"✅ Will capture {num_images} images")
        
        # Step 4: Fetch images
        st.write("🖼️ Downloading Street View images...")
        progress_bar = st.progress(0)
        
        successful_images = 0
        for i, point in enumerate(sampled_points):
            image_data = fetch_street_view_image(
                point["lat"],
                point["lng"],
                point["heading"],
                fov=fov,
                pitch=pitch
            )
            
            if image_data:
                # Save image
                image_path = TEMP_DIR / f"frame_{i:05d}.jpg"
                with open(image_path, "wb") as f:
                    f.write(image_data)
                successful_images += 1
            
            progress_bar.progress((i + 1) / num_images)
        
        st.write(f"✅ Downloaded {successful_images}/{num_images} images")
        
        # Step 5: Create video
        st.write("🎥 Rendering video...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"streetview_{timestamp}.mp4"
        
        success = create_video_from_images(TEMP_DIR, output_path, fps=fps)
        
        if success and output_path.exists():
            status.update(label="✅ Video created successfully!", state="complete")
            st.session_state.video_path = str(output_path)
            st.session_state.video_ready = True
        else:
            st.error("❌ Failed to create video. Make sure FFmpeg is installed.")
            st.code("brew install ffmpeg  # macOS\nsudo apt install ffmpeg  # Ubuntu", language="bash")

# Display video if ready
if st.session_state.get("video_ready") and st.session_state.get("video_path"):
    st.markdown("---")
    st.markdown("### 🎬 Your Video")
    
    video_path = st.session_state.video_path
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.video(video_path)
    
    with col2:
        st.markdown("#### 📊 Video Info")
        if os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            st.metric("File Size", f"{file_size:.1f} MB")
        
        st.metric("FPS", fps)
        
        if "estimated_images" in st.session_state:
            duration = st.session_state.estimated_images / fps
            st.metric("Duration", f"{duration:.1f}s")
        
        # Download button
        with open(video_path, "rb") as f:
            st.download_button(
                label="⬇️ Download Video",
                data=f,
                file_name=os.path.basename(video_path),
                mime="video/mp4",
                use_container_width=True
            )

# Footer
st.markdown("""
<div class="footer">
    Made with ❤️ using Google Street View API & Streamlit
</div>
""", unsafe_allow_html=True)

