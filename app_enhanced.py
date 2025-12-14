"""
Street View to Video Generator - Enhanced Version
With video history, cost tracking, better organization, and audio support
"""

import os
import shutil
import subprocess
import math
import time
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import streamlit as st
import requests
import polyline
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Load environment variables
load_dotenv()

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PROJECTS_DIR = Path("projects")
OUTPUT_DIR = Path("output")  # Legacy support

# Create directories
PROJECTS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Costs (per 1,000 requests)
COST_GEOCODING = 5.00 / 1000
COST_DIRECTIONS = 5.00 / 1000
COST_STREETVIEW = 7.00 / 1000

# Example routes
EXAMPLE_ROUTES = {
    "🗽 Times Square → Central Park (NYC)": {
        "start": "Times Square, New York, NY",
        "end": "Central Park, New York, NY",
        "description": "Classic NYC route through Midtown"
    },
    "🌉 Golden Gate Bridge Walk (SF)": {
        "start": "Golden Gate Bridge, San Francisco, CA",
        "end": "Sausalito, CA",
        "description": "Iconic bridge with bay views"
    },
    "🏖️ Santa Monica to Venice (LA)": {
        "start": "Santa Monica Pier, CA",
        "end": "Venice Beach Boardwalk, CA",
        "description": "Scenic Pacific Coast beach drive"
    },
    "🎡 London Eye → Big Ben": {
        "start": "London Eye, London, UK",
        "end": "Big Ben, Westminster, London, UK",
        "description": "Thames riverside landmarks"
    },
    "🗼 Eiffel Tower → Arc de Triomphe": {
        "start": "Eiffel Tower, Paris, France",
        "end": "Arc de Triomphe, Paris, France",
        "description": "Champs-Élysées iconic avenue"
    },
    "🏛️ Colosseum → Trevi Fountain": {
        "start": "Colosseum, Rome, Italy",
        "end": "Trevi Fountain, Rome, Italy",
        "description": "Ancient Rome to Baroque"
    },
    "🌸 Shibuya → Tokyo Tower": {
        "start": "Shibuya Crossing, Tokyo, Japan",
        "end": "Tokyo Tower, Tokyo, Japan",
        "description": "Modern Tokyo streets"
    },
    "🌁 Lombard St → Pier 39 (SF)": {
        "start": "Lombard Street, San Francisco, CA",
        "end": "Pier 39, San Francisco, CA",
        "description": "Crookedest street to waterfront"
    },
    "🏛️ Lincoln Memorial → Capitol": {
        "start": "Lincoln Memorial, Washington, DC",
        "end": "US Capitol, Washington, DC",
        "description": "National Mall monuments"
    },
    "🎰 Vegas Strip Experience": {
        "start": "Stratosphere Tower, Las Vegas, NV",
        "end": "Welcome to Las Vegas Sign, NV",
        "description": "Full Las Vegas Strip"
    },
    "🌴 Miami Ocean Drive": {
        "start": "Ocean Drive, Miami Beach, FL",
        "end": "South Pointe Park, Miami Beach, FL",
        "description": "Art Deco beachfront"
    },
    "🏖️ Bondi to Coogee (Sydney)": {
        "start": "Bondi Beach, Sydney, Australia",
        "end": "Coogee Beach, Sydney, Australia",
        "description": "Famous coastal walk"
    },
    "Custom Route": {
        "start": "",
        "end": "",
        "description": "Enter your own locations"
    }
}


# ============================================================================
# PROJECT MANAGEMENT
# ============================================================================

def create_project_id(start: str, end: str) -> str:
    """Create a unique project ID from route info."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Clean location names for folder
    start_clean = "".join(c for c in start.split(",")[0] if c.isalnum() or c.isspace()).strip().replace(" ", "")[:20]
    end_clean = "".join(c for c in end.split(",")[0] if c.isalnum() or c.isspace()).strip().replace(" ", "")[:20]
    
    return f"{start_clean}_{end_clean}_{timestamp}".lower()


def save_project_metadata(project_id: str, metadata: dict):
    """Save project metadata to JSON file."""
    project_dir = PROJECTS_DIR / project_id
    metadata_path = project_dir / "metadata.json"
    
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Saved metadata to {metadata_path}")


def load_project_metadata(project_id: str) -> Optional[dict]:
    """Load project metadata from JSON file."""
    metadata_path = PROJECTS_DIR / project_id / "metadata.json"
    
    if not metadata_path.exists():
        return None
    
    with open(metadata_path, "r") as f:
        return json.load(f)


def get_all_projects() -> List[dict]:
    """Get list of all projects with metadata."""
    projects = []
    
    if not PROJECTS_DIR.exists():
        return projects
    
    for project_dir in sorted(PROJECTS_DIR.iterdir(), reverse=True):
        if project_dir.is_dir():
            metadata = load_project_metadata(project_dir.name)
            if metadata:
                metadata["project_id"] = project_dir.name
                projects.append(metadata)
    
    return projects


def calculate_costs(geocoding_calls: int, directions_calls: int, streetview_calls: int) -> dict:
    """Calculate API costs."""
    geocoding_cost = geocoding_calls * COST_GEOCODING
    directions_cost = directions_calls * COST_DIRECTIONS
    streetview_cost = streetview_calls * COST_STREETVIEW
    total_cost = geocoding_cost + directions_cost + streetview_cost
    
    return {
        "geocoding": round(geocoding_cost, 4),
        "directions": round(directions_cost, 4),
        "streetview": round(streetview_cost, 2),
        "total": round(total_cost, 2),
        "calls": {
            "geocoding": geocoding_calls,
            "directions": directions_calls,
            "streetview": streetview_calls
        }
    }


# ============================================================================
# CORE FUNCTIONS (from original app.py)
# ============================================================================

def geocode_address(address: str) -> tuple[float, float] | None:
    """Convert an address to lat/lng coordinates."""
    logger.info(f"Geocoding: {address}")
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        status = data.get("status")
        
        logger.info(f"Geocoding status: {status}")
        
        if status == "OK":
            location = data["results"][0]["geometry"]["location"]
            coords = (location["lat"], location["lng"])
            logger.info(f"✅ Found: {coords}")
            return coords
        else:
            error_msg = data.get("error_message", "No error message")
            logger.error(f"❌ Geocoding failed: {status} - {error_msg}")
            return None
    except Exception as e:
        logger.error(f"❌ Geocoding exception: {str(e)}")
        return None


def get_route(origin: tuple, destination: tuple) -> dict | None:
    """Get route between two points using Google Directions API."""
    logger.info(f"Getting route from {origin} to {destination}")
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "key": GOOGLE_API_KEY,
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        status = data.get("status")
        logger.info(f"Directions API status: {status}")
        
        if status == "OK" and "routes" in data and len(data["routes"]) > 0:
            route = data["routes"][0]
            
            if "overview_polyline" not in route:
                logger.error("Missing overview_polyline in route")
                return None
            
            if "legs" not in route or len(route["legs"]) == 0:
                logger.error("Missing legs in route")
                return None
            
            leg = route["legs"][0]
            
            result = {
                "polyline": route["overview_polyline"].get("points", ""),
                "distance": leg.get("distance", {}).get("text", "Unknown"),
                "duration": leg.get("duration", {}).get("text", "Unknown"),
                "start_address": leg.get("start_address", "Unknown"),
                "end_address": leg.get("end_address", "Unknown"),
            }
            
            if not result["polyline"]:
                logger.error("Empty polyline in route")
                return None
            
            logger.info(f"Route found: {result['distance']}, {result['duration']}")
            return result
        else:
            error_msg = data.get("error_message", "No error message")
            logger.error(f"Directions API failed: {status} - {error_msg}")
            return None
    except Exception as e:
        logger.error(f"Directions API exception: {str(e)}")
        return None


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google polyline into a list of coordinates."""
    return polyline.decode(encoded)


def calculate_distance(point1: tuple, point2: tuple) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000
    
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
        
        while accumulated_distance <= segment_distance:
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
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.content
        else:
            logger.warning(f"Street View image fetch failed: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Street View image exception: {str(e)}")
        return None


def add_direction_overlay(image: Image.Image, heading: float, street_name: str = "") -> Image.Image:
    """Add direction arrow and optional street name overlay to image."""
    draw = ImageDraw.Draw(image)
    
    # Draw direction arrow
    arrow_size = 40
    center_x, center_y = image.width - 60, 60
    
    # Draw circle background
    draw.ellipse(
        [(center_x - arrow_size, center_y - arrow_size), 
         (center_x + arrow_size, center_y + arrow_size)],
        fill=(0, 0, 0, 180),
        outline=(255, 255, 255)
    )
    
    # Draw arrow pointing north (adjust based on heading)
    # Simple triangle pointing up
    points = [
        (center_x, center_y - 20),  # Top
        (center_x - 10, center_y + 10),  # Bottom left
        (center_x + 10, center_y + 10),  # Bottom right
    ]
    draw.polygon(points, fill=(255, 255, 255))
    
    # Add street name if provided
    if street_name:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        except:
            font = ImageFont.load_default()
        
        # Draw text with background
        text_bbox = draw.textbbox((0, 0), street_name, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = 10
        text_y = image.height - text_height - 20
        
        # Background rectangle
        draw.rectangle(
            [(text_x - 5, text_y - 5), 
             (text_x + text_width + 5, text_y + text_height + 5)],
            fill=(0, 0, 0, 180)
        )
        
        # Text
        draw.text((text_x, text_y), street_name, fill=(255, 255, 255), font=font)
    
    return image


def create_video_from_images(image_dir: Path, output_path: Path, fps: int = 10, 
                            audio_path: Optional[Path] = None) -> bool:
    """Create video from images using FFmpeg, optionally with audio."""
    images = sorted(image_dir.glob("*.jpg"))
    
    if not images:
        return False
    
    # Create file list for FFmpeg
    list_file = image_dir / "images.txt"
    with open(list_file, "w") as f:
        for img in images:
            f.write(f"file '{img.absolute()}'\n")
            f.write(f"duration {1/fps}\n")
    
    # Base FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-vf", "scale=640:640:force_original_aspect_ratio=decrease,pad=640:640:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
    ]
    
    # Add audio if provided
    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path), "-c:a", "aac", "-shortest"])
    
    cmd.append(str(output_path))
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"FFmpeg error: {e}")
        return False


# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(
    page_title="Street View to Video",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS (keeping your beautiful dark theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #0a0a0f 0%, #0f0f1a 50%, #0a0a0f 100%);
    }
    
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
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Check API key
if not GOOGLE_API_KEY:
    st.error("⚠️ Google API key not found! Please add `GOOGLE_API_KEY` to your `.env` file.")
    st.stop()

# Header
st.markdown("""
<div class="main-header">
    <h1>🎬 Street View to Video</h1>
    <p>Transform any route into a cinematic Street View journey</p>
</div>
""", unsafe_allow_html=True)

# Create tabs
tab1, tab2 = st.tabs(["🎬 Create Video", "📁 Video Gallery"])

# ============================================================================
# TAB 1: CREATE VIDEO
# ============================================================================

with tab1:
    # Sidebar settings
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        st.markdown("### 📍 Image Capture")
        interval = st.slider(
            "Distance between images (meters)", 
            10, 100, 15, 5,
            help="Lower = smoother video. Recommended: 10-20m"
        )
        
        st.markdown("### 🎥 Video Settings")
        fps = st.slider(
            "Frames per second", 
            5, 30, 15, 1,
            help="Higher = smoother playback. Recommended: 10-20 fps"
        )
        fov = st.slider(
            "Field of view", 
            30, 120, 90, 10,
            help="90° is natural. Lower = zoomed in, Higher = wide angle"
        )
        pitch = st.slider(
            "Camera pitch (up/down angle)", 
            -45, 45, 0, 5,
            help="0° = level, positive = up, negative = down"
        )
        
        st.markdown("### 🎨 Enhancements")
        add_overlays = st.checkbox("Add direction arrows", value=False)
        
        st.markdown("### 🎵 Audio")
        
        # Audio presets
        audio_preset = st.selectbox(
            "Background Music",
            ["None", "Upload Custom", "Sample: Upbeat Travel", "Sample: Calm Journey"],
            index=0,
            help="Add background music to your video"
        )
        
        audio_file = None
        audio_preset_path = None
        
        if audio_preset == "Upload Custom":
            audio_file = st.file_uploader("Upload MP3 file", type=['mp3'])
        elif audio_preset == "Sample: Upbeat Travel":
            audio_preset_path = Path("audio_samples/upbeat_travel.mp3")
            if not audio_preset_path.exists():
                st.warning("⚠️ Sample music not found. See `DOWNLOAD_MUSIC.md` to add music files.")
                audio_preset_path = None
        elif audio_preset == "Sample: Calm Journey":
            audio_preset_path = Path("audio_samples/calm_journey.mp3")
            if not audio_preset_path.exists():
                st.warning("⚠️ Sample music not found. See `DOWNLOAD_MUSIC.md` to add music files.")
                audio_preset_path = None
        
        st.markdown("---")
        st.markdown("### 💰 Cost Estimator")
        if "estimated_cost" in st.session_state:
            cost_data = st.session_state.estimated_cost
            st.metric("Estimated Cost", f"${cost_data['total']}")
            with st.expander("Cost Breakdown"):
                st.write(f"Geocoding: ${cost_data['geocoding']}")
                st.write(f"Directions: ${cost_data['directions']}")
                st.write(f"Street View: ${cost_data['streetview']}")
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📍 Enter Your Route")
        
        selected_example = st.selectbox(
            "Choose an example or create custom",
            options=list(EXAMPLE_ROUTES.keys()),
            index=0,
            help="Popular routes from around the world",
            key="route_selector"
        )
        
        # Clear route coords when changing routes
        if "last_selected_route" not in st.session_state:
            st.session_state.last_selected_route = selected_example
        elif st.session_state.last_selected_route != selected_example:
            st.session_state.route_coords = None
            st.session_state.last_selected_route = selected_example
        
        # Show description
        route_desc = EXAMPLE_ROUTES[selected_example].get("description", "")
        if route_desc:
            st.caption(f"ℹ️ {route_desc}")
        
        default_start = EXAMPLE_ROUTES[selected_example]["start"]
        default_end = EXAMPLE_ROUTES[selected_example]["end"]
        
        origin = st.text_input("Starting Point", value=default_start, placeholder="e.g., Times Square, New York")
        destination = st.text_input("Destination", value=default_end, placeholder="e.g., Central Park, New York")
        
        generate_btn = st.button("🚀 Generate Video", type="primary", use_container_width=True)
    
    with col2:
        st.markdown("### 🗺️ Route Preview")
        
        map_center = [40.7128, -74.0060]
        m = folium.Map(location=map_center, zoom_start=12, tiles="CartoDB dark_matter")
        
        if "route_coords" in st.session_state and st.session_state.route_coords:
            coords = st.session_state.route_coords
            folium.PolyLine(coords, color="#6366f1", weight=4, opacity=0.8).add_to(m)
            folium.Marker(coords[0], popup="Start", icon=folium.Icon(color="green", icon="play")).add_to(m)
            folium.Marker(coords[-1], popup="End", icon=folium.Icon(color="red", icon="stop")).add_to(m)
            m.fit_bounds([coords[0], coords[-1]])
        
        # Use selected route as key to force map refresh when route changes
        map_key = f"map_{selected_example.replace(' ', '_')}"
        st_folium(m, width=None, height=400, use_container_width=True, key=map_key)
    
    # Generate video
    if generate_btn and origin and destination:
        logger.info(f"🎬 Starting video generation: {origin} → {destination}")
        
        # Create project ID and directory
        project_id = create_project_id(origin, destination)
        project_dir = PROJECTS_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        images_dir = project_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # Initialize costs
        api_calls = {"geocoding": 0, "directions": 0, "streetview": 0}
        
        with st.status("🎬 Creating your Street View video...", expanded=True) as status:
            # Step 1: Geocode
            st.write("📍 Finding locations...")
            origin_coords = geocode_address(origin)
            api_calls["geocoding"] += 1
            
            if not origin_coords:
                st.error(f"❌ Could not find starting location: '{origin}'")
                st.stop()
            
            dest_coords = geocode_address(destination)
            api_calls["geocoding"] += 1
            
            if not dest_coords:
                st.error(f"❌ Could not find destination: '{destination}'")
                st.stop()
            
            st.write(f"✅ Start: {origin_coords[0]:.6f}, {origin_coords[1]:.6f}")
            st.write(f"✅ End: {dest_coords[0]:.6f}, {dest_coords[1]:.6f}")
            
            # Step 2: Get route
            st.write("🛣️ Calculating route...")
            route = get_route(origin_coords, dest_coords)
            api_calls["directions"] += 1
            
            if not route:
                st.error("❌ Could not find a route")
                st.stop()
            
            route_coords = decode_polyline(route["polyline"])
            st.session_state.route_coords = route_coords
            
            st.write(f"✅ Distance: {route['distance']}, Duration: {route['duration']}")
            
            # Step 3: Sample points
            st.write("📸 Calculating image positions...")
            sampled_points = sample_points_along_route(route_coords, interval)
            num_images = len(sampled_points)
            
            # Calculate costs
            costs = calculate_costs(api_calls["geocoding"], api_calls["directions"], num_images)
            st.session_state.estimated_cost = costs
            
            st.write(f"✅ Will capture {num_images} images")
            st.info(f"💰 Estimated cost: ${costs['total']}")
            
            # Step 4: Fetch images
            st.write("---")
            st.write("### 🖼️ Downloading Street View images...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            successful_images = 0
            start_time = time.time()
            
            for i, point in enumerate(sampled_points):
                progress = (i + 1) / num_images
                elapsed = time.time() - start_time
                remaining = (elapsed / progress - elapsed) if progress > 0 else 0
                
                progress_bar.progress(progress, text=f"Image {i+1}/{num_images}")
                status_text.text(f"⏱️ {elapsed:.0f}s elapsed | ~{remaining:.0f}s remaining | ✅ {successful_images}")
                
                image_data = fetch_street_view_image(
                    point["lat"], point["lng"], point["heading"],
                    fov=fov, pitch=pitch
                )
                
                if image_data:
                    # Add overlays if enabled
                    if add_overlays:
                        img = Image.open(BytesIO(image_data))
                        img = add_direction_overlay(img, point["heading"])
                        image_path = images_dir / f"frame_{i:05d}.jpg"
                        img.save(image_path, "JPEG")
                    else:
                        image_path = images_dir / f"frame_{i:05d}.jpg"
                        with open(image_path, "wb") as f:
                            f.write(image_data)
                    
                    successful_images += 1
            
            api_calls["streetview"] = successful_images
            actual_costs = calculate_costs(api_calls["geocoding"], api_calls["directions"], api_calls["streetview"])
            
            st.write(f"✅ Downloaded {successful_images}/{num_images} images")
            
            if successful_images < 5:
                st.error("❌ Not enough images downloaded")
                st.stop()
            
            # Step 5: Create video
            st.write("### 🎥 Rendering video...")
            
            # Save audio if provided
            audio_path = None
            if audio_file:
                audio_path = project_dir / "audio.mp3"
                with open(audio_path, "wb") as f:
                    f.write(audio_file.getbuffer())
            elif audio_preset_path and audio_preset_path.exists():
                audio_path = audio_preset_path
            
            video_path = project_dir / "video.mp4"
            success = create_video_from_images(images_dir, video_path, fps, audio_path)
            
            if success and video_path.exists():
                # Save metadata
                metadata = {
                    "route": {
                        "start": origin,
                        "end": destination,
                        "start_coords": origin_coords,
                        "end_coords": dest_coords,
                        "distance": route["distance"],
                        "duration": route["duration"]
                    },
                    "settings": {
                        "interval": interval,
                        "fps": fps,
                        "fov": fov,
                        "pitch": pitch,
                        "overlays": add_overlays,
                        "has_audio": audio_file is not None
                    },
                    "costs": actual_costs,
                    "images": {
                        "total": num_images,
                        "successful": successful_images,
                        "failed": num_images - successful_images
                    },
                    "video": {
                        "path": str(video_path.relative_to(PROJECTS_DIR)),
                        "duration_seconds": successful_images / fps,
                        "size_mb": round(video_path.stat().st_size / (1024 * 1024), 2)
                    },
                    "created_at": datetime.now().isoformat()
                }
                
                save_project_metadata(project_id, metadata)
                
                status.update(label="✅ Video created successfully!", state="complete")
                st.session_state.latest_project = project_id
                st.balloons()
                
                # Display video
                st.write("---")
                st.markdown("### 🎬 Your Video")
                
                col_video, col_info = st.columns([3, 1])
                
                with col_video:
                    # Read video as bytes to avoid caching issues
                    with open(video_path, "rb") as video_file:
                        st.video(video_file.read())
                
                with col_info:
                    st.markdown("#### 📊 Video Info")
                    st.metric("File Size", f"{metadata['video']['size_mb']} MB")
                    st.metric("Duration", f"{metadata['video']['duration_seconds']:.1f}s")
                    st.metric("Total Cost", f"${metadata['costs']['total']}")
                    
                    with open(video_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Video",
                            data=f,
                            file_name=f"{project_id}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
            else:
                st.error("❌ Failed to create video. Make sure FFmpeg is installed.")

# ============================================================================
# TAB 2: VIDEO GALLERY
# ============================================================================

with tab2:
    st.markdown("### 📁 Your Video Gallery")
    
    projects = get_all_projects()
    
    if not projects:
        st.info("No videos yet! Create your first video in the 'Create Video' tab.")
    else:
        # Summary stats
        total_cost = sum(p["costs"]["total"] for p in projects)
        total_videos = len(projects)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Videos", total_videos)
        with col2:
            st.metric("Total Cost", f"${total_cost:.2f}")
        with col3:
            free_tier_remaining = 200 - total_cost
            st.metric("Free Tier Remaining", f"${free_tier_remaining:.2f}")
        
        st.write("---")
        
        # Display videos in grid
        for i in range(0, len(projects), 2):
            cols = st.columns(2)
            
            for j, col in enumerate(cols):
                if i + j < len(projects):
                    project = projects[i + j]
                    
                    with col:
                        with st.container():
                            st.markdown(f"#### {project['route']['start']} → {project['route']['end']}")
                            
                            video_path = PROJECTS_DIR / project["project_id"] / "video.mp4"
                            
                            if video_path.exists():
                                # Read video as bytes to avoid caching issues
                                with open(video_path, "rb") as video_file:
                                    st.video(video_file.read())
                                
                                # Info
                                info_col1, info_col2 = st.columns(2)
                                with info_col1:
                                    st.caption(f"📏 {project['route']['distance']}")
                                    st.caption(f"⏱️ {project['route']['duration']}")
                                with info_col2:
                                    st.caption(f"💰 ${project['costs']['total']}")
                                    st.caption(f"🖼️ {project['images']['successful']} images")
                                
                                # Actions
                                action_col1, action_col2 = st.columns(2)
                                with action_col1:
                                    with open(video_path, "rb") as f:
                                        st.download_button(
                                            label="⬇️ Download",
                                            data=f,
                                            file_name=f"{project['project_id']}.mp4",
                                            mime="video/mp4",
                                            key=f"download_{project['project_id']}",
                                            use_container_width=True
                                        )
                                
                                with action_col2:
                                    if st.button("🗑️ Delete", key=f"delete_{project['project_id']}", use_container_width=True):
                                        project_dir = PROJECTS_DIR / project["project_id"]
                                        shutil.rmtree(project_dir)
                                        st.rerun()
                        
                        st.write("---")

# Footer
st.markdown("""
<div style="text-align: center; padding: 2rem 0; color: #94a3b8;">
    Made with ❤️ using Google Street View API & Streamlit
</div>
""", unsafe_allow_html=True)

