"""
Route Preview - Enhanced Version
With video history, cost tracking, and GPX route preview
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
from streamlit_searchbox import st_searchbox
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from gpx_import import parse_gpx, sample_gpx_segments

# Load environment variables
load_dotenv()

# Configuration - support both .env (local) and st.secrets (Streamlit Cloud)
def get_api_key():
    """Get API key from environment or Streamlit secrets."""
    # Try Streamlit secrets first (for cloud deployment)
    try:
        return st.secrets.get("GOOGLE_API_KEY")
    except:
        pass
    # Fall back to environment variable (local development)
    return os.getenv("GOOGLE_API_KEY")

GOOGLE_API_KEY = get_api_key()
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
        "description": "Classic NYC route through Midtown",
        "center": [40.7614, -73.9776], "zoom": 14
    },
    "🌉 Golden Gate Bridge Walk (SF)": {
        "start": "Golden Gate Bridge, San Francisco, CA",
        "end": "Sausalito, CA",
        "description": "Iconic bridge with bay views",
        "center": [37.8199, -122.4783], "zoom": 13
    },
    "🏖️ Santa Monica to Venice (LA)": {
        "start": "Santa Monica Pier, CA",
        "end": "Venice Beach Boardwalk, CA",
        "description": "Scenic Pacific Coast beach drive",
        "center": [33.9990, -118.4790], "zoom": 14
    },
    "🎡 London Eye → Big Ben": {
        "start": "London Eye, London, UK",
        "end": "Big Ben, Westminster, London, UK",
        "description": "Thames riverside landmarks",
        "center": [51.5007, -0.1246], "zoom": 15
    },
    "🗼 Eiffel Tower → Arc de Triomphe": {
        "start": "Eiffel Tower, Paris, France",
        "end": "Arc de Triomphe, Paris, France",
        "description": "Champs-Élysées iconic avenue",
        "center": [48.8656, 2.3100], "zoom": 14
    },
    "🏛️ Colosseum → Trevi Fountain": {
        "start": "Colosseum, Rome, Italy",
        "end": "Trevi Fountain, Rome, Italy",
        "description": "Ancient Rome to Baroque",
        "center": [41.8955, 12.4823], "zoom": 15
    },
    "🌸 Shibuya → Tokyo Tower": {
        "start": "Shibuya Crossing, Tokyo, Japan",
        "end": "Tokyo Tower, Tokyo, Japan",
        "description": "Modern Tokyo streets",
        "center": [35.6595, 139.7050], "zoom": 14
    },
    "🌁 Lombard St → Pier 39 (SF)": {
        "start": "Lombard Street, San Francisco, CA",
        "end": "Pier 39, San Francisco, CA",
        "description": "Crookedest street to waterfront",
        "center": [37.8050, -122.4180], "zoom": 14
    },
    "🏛️ Lincoln Memorial → Capitol": {
        "start": "Lincoln Memorial, Washington, DC",
        "end": "US Capitol, Washington, DC",
        "description": "National Mall monuments",
        "center": [38.8893, -77.0200], "zoom": 14
    },
    "🎰 Vegas Strip Experience": {
        "start": "Stratosphere Tower, Las Vegas, NV",
        "end": "Welcome to Las Vegas Sign, NV",
        "description": "Full Las Vegas Strip",
        "center": [36.1147, -115.1728], "zoom": 13
    },
    "🌴 Miami Ocean Drive": {
        "start": "Ocean Drive, Miami Beach, FL",
        "end": "South Pointe Park, Miami Beach, FL",
        "description": "Art Deco beachfront",
        "center": [25.7825, -80.1324], "zoom": 14
    },
    "🏖️ Bondi to Coogee (Sydney)": {
        "start": "Bondi Beach, Sydney, Australia",
        "end": "Coogee Beach, Sydney, Australia",
        "description": "Famous coastal walk",
        "center": [-33.8915, 151.2767], "zoom": 14
    },
    "🚶 Greenwich Village Walk (NYC)": {
        "start": "Washington Square Park, New York, NY",
        "end": "West Village, New York, NY",
        "description": "Charming neighborhood stroll",
        "center": [40.7308, -74.0020], "zoom": 15
    },
    "🌸 Cherry Blossom Walk (DC)": {
        "start": "Tidal Basin, Washington, DC",
        "end": "Jefferson Memorial, Washington, DC",
        "description": "Beautiful waterfront walk",
        "center": [38.8814, -77.0365], "zoom": 15
    },
    "🎨 Left Bank Paris Walk": {
        "start": "Notre-Dame Cathedral, Paris, France",
        "end": "Musée d'Orsay, Paris, France",
        "description": "Seine riverside art district",
        "center": [48.8530, 2.3400], "zoom": 15
    },
    "🏰 Prague Castle Walk": {
        "start": "Charles Bridge, Prague, Czech Republic",
        "end": "Prague Castle, Prague, Czech Republic",
        "description": "Historic Old Town to castle",
        "center": [50.0865, 14.4100], "zoom": 15
    },
    "🌳 Barcelona Gothic Quarter": {
        "start": "Las Ramblas, Barcelona, Spain",
        "end": "Barcelona Cathedral, Barcelona, Spain",
        "description": "Medieval streets exploration",
        "center": [41.3825, 2.1769], "zoom": 15
    },
    "🎭 Covent Garden Stroll (London)": {
        "start": "Covent Garden, London, UK",
        "end": "Trafalgar Square, London, UK",
        "description": "Theater district walk",
        "center": [51.5117, -0.1240], "zoom": 15
    },
    "🍜 Harajuku to Shibuya (Tokyo)": {
        "start": "Meiji Shrine, Tokyo, Japan",
        "end": "Shibuya Crossing, Tokyo, Japan",
        "description": "Youth culture to bustling crossing",
        "center": [35.6700, 139.7030], "zoom": 14
    },
    "🇩🇪 Brandenburg Gate → Checkpoint Charlie (Berlin)": {
        "start": "Brandenburg Gate, Berlin, Germany",
        "end": "Checkpoint Charlie, Berlin, Germany",
        "description": "Historic Cold War landmarks",
        "center": [52.5163, 13.3900], "zoom": 14
    },
    "🧱 East Side Gallery → Alexanderplatz (Berlin)": {
        "start": "East Side Gallery, Berlin, Germany",
        "end": "Alexanderplatz, Berlin, Germany",
        "description": "Berlin Wall art to iconic TV tower",
        "center": [52.5050, 13.4400], "zoom": 14
    },
    "Custom Route": {
        "start": "",
        "end": "",
        "description": "Enter your own locations",
        "center": [40.7128, -74.0060], "zoom": 12
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

def search_places(query: str) -> list[str]:
    """Search for places using Google Places Autocomplete API."""
    if not query or len(query) < 2:
        return []
    
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "key": GOOGLE_API_KEY,
        "types": "geocode|establishment",
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data.get("status") == "OK":
            predictions = data.get("predictions", [])
            return [p.get("description", "") for p in predictions[:5]]
        else:
            # Fallback: return the query itself
            return [query] if query else []
    except Exception as e:
        logger.warning(f"Places Autocomplete error: {e}")
        return [query] if query else []


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
    """Add direction compass and optional street name overlay to image.
    
    Shows a compass with:
    - Red arrow pointing to North (rotates based on heading)
    - Direction text (N, NE, E, SE, S, SW, W, NW)
    
    Heading: 0=North, 90=East, 180=South, 270=West
    """
    draw = ImageDraw.Draw(image)
    
    # Compass position
    compass_size = 35
    center_x, center_y = image.width - 55, 55
    
    # Draw circle background
    draw.ellipse(
        [(center_x - compass_size, center_y - compass_size), 
         (center_x + compass_size, center_y + compass_size)],
        fill=(0, 0, 0, 200),
        outline=(255, 255, 255, 200),
        width=2
    )
    
    # Calculate where North is relative to camera view
    # Camera faces 'heading' degrees from North
    # So North is at -heading degrees from straight ahead (up)
    # In image coords: up is -Y, right is +X
    # Rotation: 0 degrees = up, positive = clockwise
    
    north_angle_deg = -heading  # North is this many degrees from camera forward
    north_angle_rad = math.radians(north_angle_deg - 90)  # Convert to image coords (-90 because 0 deg = up)
    
    # Draw North arrow (red)
    arrow_length = 25
    arrow_tip_x = center_x + arrow_length * math.cos(north_angle_rad)
    arrow_tip_y = center_y + arrow_length * math.sin(north_angle_rad)
    
    # Arrow base (opposite direction)
    arrow_base_x = center_x - (arrow_length * 0.4) * math.cos(north_angle_rad)
    arrow_base_y = center_y - (arrow_length * 0.4) * math.sin(north_angle_rad)
    
    # Arrow head points
    head_angle1 = north_angle_rad + math.radians(150)
    head_angle2 = north_angle_rad - math.radians(150)
    head_len = 10
    
    head1_x = arrow_tip_x + head_len * math.cos(head_angle1)
    head1_y = arrow_tip_y + head_len * math.sin(head_angle1)
    head2_x = arrow_tip_x + head_len * math.cos(head_angle2)
    head2_y = arrow_tip_y + head_len * math.sin(head_angle2)
    
    # Draw arrow line
    draw.line([(arrow_base_x, arrow_base_y), (arrow_tip_x, arrow_tip_y)], fill=(255, 80, 80), width=3)
    # Draw arrow head
    draw.polygon([(arrow_tip_x, arrow_tip_y), (head1_x, head1_y), (head2_x, head2_y)], fill=(255, 80, 80))
    
    # Draw "N" at arrow tip
    try:
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except:
        font_small = ImageFont.load_default()
    
    n_offset_x = 8 * math.cos(north_angle_rad)
    n_offset_y = 8 * math.sin(north_angle_rad)
    draw.text((arrow_tip_x + n_offset_x - 4, arrow_tip_y + n_offset_y - 6), "N", fill=(255, 200, 200), font=font_small)
    
    # Show heading direction as text below compass
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    dir_index = int((heading + 22.5) % 360 / 45)
    direction_text = f"→ {directions[dir_index]} {int(heading)}°"
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except:
        font = ImageFont.load_default()
    
    # Draw heading text with background
    text_bbox = draw.textbbox((0, 0), direction_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = center_x - text_width // 2
    text_y = center_y + compass_size + 8
    
    draw.rectangle(
        [(text_x - 4, text_y - 2), (text_x + text_width + 4, text_y + 18)],
        fill=(0, 0, 0, 200)
    )
    draw.text((text_x, text_y), direction_text, fill=(255, 255, 255), font=font)
    
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


def create_video_from_images(image_dir: Path, output_path: Path, fps: int = 10) -> bool:
    """Create a silent video from the downloaded Street View images."""
    images = sorted(image_dir.glob("*.jpg"))
    if not images:
        return False
    list_file = image_dir / "images.txt"
    with open(list_file, "w") as f:
        for img in images:
            f.write(f"file '{img.absolute()}'\\n")
            f.write(f"duration {1/fps}\\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-vf", "scale=640:640:force_original_aspect_ratio=decrease,pad=640:640:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-an", str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg stderr: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        logger.error(f"FFmpeg error: {e}")
        return False



# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(
    page_title="Route Preview",
    page_icon="⛟",
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

# GPX inspection and map preview are available without a Google API key.

# Header
st.markdown("""
<div class="main-header">
    <h1>⛟ Route Preview</h1>
    <p>Transform any route into a Street View video</p>
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

        st.markdown("### 🔑 Google API key")
        if "google_api_key_input" not in st.session_state:
            st.session_state.google_api_key_input = get_api_key() or ""
        api_key_input = st.text_input(
            "Google API key",
            type="password",
            key="google_api_key_input",
            help="Facultative pour analyser et afficher un GPX. Nécessaire uniquement pour les appels Google (Street View et Directions)."
        )
        GOOGLE_API_KEY = api_key_input.strip() or None
        if GOOGLE_API_KEY:
            st.caption("✅ Clé renseignée — génération Street View disponible")
        else:
            st.caption("ℹ️ Sans clé : analyse GPX et carte disponibles ; génération Street View désactivée.")
        st.markdown("---")
        
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
            help="0° = level horizon. Use +10° to +20° to see more sky/buildings. Use -10° to -20° to see more road/ground."
        )
        
        st.markdown("### 🎨 Enhancements")
        add_overlays = st.checkbox("Add direction arrows", value=True, help="Shows a compass arrow and street name overlay")
        
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
        st.markdown("### 📍 Définir le tracé")
        route_mode = st.radio(
            "Source du parcours",
            ["Adresses (Google Directions)", "Fichier GPX (tracé exact)"],
            horizontal=True, key="route_source_mode",
            help="En mode GPX, le fichier fourni fait foi : aucun recalcul d'itinéraire n'est effectué."
        )
        gpx_data = None
        gpx_file_name = None
        uploaded_gpx = None
        origin = None
        destination = None

        if route_mode == "Fichier GPX (tracé exact)":
            uploaded_gpx = st.file_uploader("Importer un fichier GPX", type=["gpx"], key="gpx_upload")
            if uploaded_gpx is not None:
                gpx_file_name = uploaded_gpx.name
                try:
                    gpx_data = parse_gpx(uploaded_gpx.getvalue())
                    st.success(f"Fichier GPX analysé : {gpx_file_name}")
                    elevations = [
                        point["ele"]
                        for segment in gpx_data["segments"]
                        for point in segment
                        if "ele" in point
                    ]
                    elevation_gain = sum(
                        max(0.0, b["ele"] - a["ele"])
                        for segment in gpx_data["segments"]
                        for a, b in zip(segment, segment[1:])
                        if "ele" in a and "ele" in b
                    )
                    elevation_loss = sum(
                        max(0.0, a["ele"] - b["ele"])
                        for segment in gpx_data["segments"]
                        for a, b in zip(segment, segment[1:])
                        if "ele" in a and "ele" in b
                    )
                    st.markdown("#### 📊 Première analyse du tracé")
                    metric_cols = st.columns(4)
                    metric_cols[0].metric("Distance", f"{gpx_data['distance_m'] / 1000:.2f} km")
                    metric_cols[1].metric("Points", f"{gpx_data['point_count']:,}".replace(",", " "))
                    metric_cols[2].metric("Segments", len(gpx_data["segments"]))
                    metric_cols[3].metric("Waypoints", len(gpx_data["waypoints"]))
                    if elevations:
                        st.markdown("##### ⛰️ Profil altimétrique")
                        elevation_profile = []
                        profile_index = 0
                        for segment in gpx_data["segments"]:
                            for point in segment:
                                elevation_profile.append(point.get("ele"))
                                profile_index += 1
                            # Keep a visual break between disconnected GPX segments.
                            elevation_profile.append(None)
                        st.line_chart({"Altitude (m)": elevation_profile})
                        elevation_cols = st.columns(3)
                        elevation_cols[0].metric("Altitude min.", f"{min(elevations):.0f} m")
                        elevation_cols[1].metric("Altitude max.", f"{max(elevations):.0f} m")
                        elevation_cols[2].metric(
                            "Dénivelé + / −",
                            f"+{elevation_gain:.0f} m / −{elevation_loss:.0f} m"
                        )
                    else:
                        st.caption("Aucune altitude exploitable n'est renseignée dans ce fichier GPX.")
                    origin = f"{gpx_file_name} — départ"
                    destination = f"{gpx_file_name} — arrivée"
                except ValueError as exc:
                    st.error(str(exc))
            st.caption("Les segments disjoints restent séparés. L'ordre des points du GPX est conservé. Cette analyse et la carte ne nécessitent aucune clé API.")
        else:
            selected_example = st.selectbox(
                "Choisir un exemple ou créer un parcours",
                options=list(EXAMPLE_ROUTES.keys()), index=0,
                help="Parcours d'exemple ou adresses personnalisées", key="route_selector"
            )
            if "last_selected_route" not in st.session_state:
                st.session_state.last_selected_route = selected_example
            elif st.session_state.last_selected_route != selected_example:
                st.session_state.route_coords = None
                st.session_state.last_selected_route = selected_example
            route_desc = EXAMPLE_ROUTES[selected_example].get("description", "")
            if route_desc:
                st.caption(f"ℹ️ {route_desc}")
            default_start = EXAMPLE_ROUTES[selected_example]["start"]
            default_end = EXAMPLE_ROUTES[selected_example]["end"]
            route_key = selected_example.replace(" ", "_").replace(",", "").replace("→", "_")[:30]
            st.caption("📍 **Point de départ**")
            origin = st_searchbox(
                search_places, key=f"origin_search_{route_key}",
                placeholder="Saisir un lieu...", default=default_start if default_start else None,
                clear_on_submit=False,
            )
            st.caption("📍 **Destination**")
            destination = st_searchbox(
                search_places, key=f"destination_search_{route_key}",
                placeholder="Saisir un lieu...", default=default_end if default_end else None,
                clear_on_submit=False,
            )
            if origin:
                st.success(f"✅ Départ : {origin}")
            if destination:
                st.success(f"✅ Arrivée : {destination}")
        generate_btn = st.button(
            "🚀 Générer la vidéo" if GOOGLE_API_KEY else "🔒 Génération vidéo : clé API requise",
            type="primary",
            use_container_width=True,
            disabled=not bool(GOOGLE_API_KEY),
            help=None if GOOGLE_API_KEY else "Tu peux déjà analyser et visualiser ton GPX sans clé. Saisis une clé Google dans les paramètres pour créer la vidéo."
        )

    with col2:
        st.markdown("### 🗺️ Aperçu du tracé")
        if route_mode == "Fichier GPX (tracé exact)" and gpx_data:
            all_points = [point for segment in gpx_data["segments"] for point in segment]
            m = folium.Map(location=[all_points[0]["lat"], all_points[0]["lon"]], zoom_start=13, tiles="OpenStreetMap")
            bounds = []
            for segment_index, segment in enumerate(gpx_data["segments"]):
                line = [[point["lat"], point["lon"]] for point in segment]
                bounds.extend(line)
                folium.PolyLine(line, color="#22c55e", weight=4, opacity=0.9,
                                tooltip=f"Segment GPX {segment_index + 1}").add_to(m)
            first_point = gpx_data["segments"][0][0]
            last_point = gpx_data["segments"][-1][-1]
            folium.Marker([first_point["lat"], first_point["lon"]], popup="Départ GPX",
                          icon=folium.Icon(color="green", icon="play")).add_to(m)
            folium.Marker([last_point["lat"], last_point["lon"]], popup="Fin GPX",
                          icon=folium.Icon(color="red", icon="stop")).add_to(m)
            for waypoint in gpx_data["waypoints"]:
                point = waypoint["point"]
                folium.CircleMarker([point["lat"], point["lon"]], radius=5,
                                    color="#f59e0b", fill=True, popup=waypoint["name"]).add_to(m)
            m.fit_bounds(bounds)
            st_folium(m, width=None, height=400, use_container_width=True, key="gpx_route_map")
        elif route_mode == "Fichier GPX (tracé exact)":
            st.info("Importez un fichier GPX valide pour afficher son tracé.")
        else:
            route_info = EXAMPLE_ROUTES[selected_example]
            map_center = route_info.get("center", [40.7128, -74.0060])
            map_zoom = route_info.get("zoom", 12)
            m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="OpenStreetMap")
            if "route_coords" in st.session_state and st.session_state.route_coords:
                coords = st.session_state.route_coords
                folium.PolyLine(coords, color="#6366f1", weight=4, opacity=0.8).add_to(m)
                folium.Marker(coords[0], popup="Départ", icon=folium.Icon(color="green", icon="play")).add_to(m)
                folium.Marker(coords[-1], popup="Arrivée", icon=folium.Icon(color="red", icon="stop")).add_to(m)
                m.fit_bounds([coords[0], coords[-1]])
            else:
                folium.Marker(map_center,
                    popup=f"{route_info['start']} → {route_info['end']}" if route_info["start"] else "Choisir un parcours",
                    icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
            map_key = "map_" + selected_example.replace(" ", "_")
            st_folium(m, width=None, height=400, use_container_width=True, key=map_key)

    # Generate video
    if generate_btn and ((route_mode == "Fichier GPX (tracé exact)" and gpx_data is not None) or (route_mode != "Fichier GPX (tracé exact)" and origin and destination)):
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
            if route_mode == "Fichier GPX (tracé exact)":
                # GPX geometry is authoritative: no geocoding and no Directions request.
                st.write("📍 Lecture du tracé GPX fourni...")
                segments = gpx_data["segments"]
                first, last = segments[0][0], segments[-1][-1]
                origin_coords = (first["lat"], first["lon"])
                dest_coords = (last["lat"], last["lon"])
                route_coords = [(p["lat"], p["lon"]) for seg in segments for p in seg]
                st.session_state.route_coords = route_coords
                distance_label = f"{gpx_data['distance_m'] / 1000:.2f} km"
                route = {
                    "distance": distance_label,
                    "duration": "Non estimée (tracé GPX)",
                    "start_address": "Départ GPX",
                    "end_address": "Arrivée GPX",
                }
                st.write(f"✅ {gpx_data['point_count']} points · {len(segments)} segment(s) · {distance_label}")
                with open(project_dir / "route.gpx", "wb") as gpx_output:
                    gpx_output.write(uploaded_gpx.getvalue())
                sampled_points = sample_gpx_segments(segments, interval)
            else:
                # Keep the existing address-based workflow for backward compatibility.
                st.write("📍 Recherche des lieux...")
                origin_coords = geocode_address(origin)
                api_calls["geocoding"] += 1
                if not origin_coords:
                    st.error(f"❌ Impossible de trouver le départ : '{origin}'")
                    st.stop()
                dest_coords = geocode_address(destination)
                api_calls["geocoding"] += 1
                if not dest_coords:
                    st.error(f"❌ Impossible de trouver la destination : '{destination}'")
                    st.stop()
                st.write(f"✅ Départ : {origin_coords[0]:.6f}, {origin_coords[1]:.6f}")
                st.write(f"✅ Arrivée : {dest_coords[0]:.6f}, {dest_coords[1]:.6f}")
                st.write("🛣️ Calcul de l'itinéraire...")
                route = get_route(origin_coords, dest_coords)
                api_calls["directions"] += 1
                if not route:
                    st.error("❌ Aucun itinéraire trouvé")
                    st.stop()
                route_coords = decode_polyline(route["polyline"])
                st.session_state.route_coords = route_coords
                st.write(f"✅ Distance : {route['distance']}, durée : {route['duration']}")
                st.write("📸 Calcul des positions des images...")
                sampled_points = sample_points_along_route(route_coords, interval)

            num_images = len(sampled_points)
            if num_images == 0:
                st.error("❌ Aucun point exploitable dans ce tracé.")
                st.stop()

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
            
            video_path = project_dir / "video.mp4"
            success = create_video_from_images(images_dir, video_path, fps)
            
            if success and video_path.exists():
                # Save metadata
                metadata = {
                    "route": {
                        "start": origin,
                        "end": destination,
                        "start_coords": origin_coords,
                        "end_coords": dest_coords,
                        "distance": route["distance"],
                        "duration": route["duration"],
                        "source": "GPX" if route_mode == "Fichier GPX (tracé exact)" else "Google Directions",
                        "gpx_file": gpx_file_name if route_mode == "Fichier GPX (tracé exact)" else None,
                        "gpx_point_count": gpx_data["point_count"] if route_mode == "Fichier GPX (tracé exact)" else None
                    },
                    "settings": {
                        "interval": interval,
                        "fps": fps,
                        "fov": fov,
                        "pitch": pitch,
                        "overlays": add_overlays,
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
                    project_id = project["project_id"]
                    
                    with col:
                        with st.container():
                            st.markdown(f"#### {project['route']['start']} → {project['route']['end']}")
                            
                            # Find video file - try multiple possible names
                            video_path = None
                            project_dir = PROJECTS_DIR / project_id
                            
                            # Check for video files in order of preference
                            possible_videos = [
                                project_dir / "video.mp4",
                                project_dir / "video_regenerated.mp4",
                            ]
                            
                            for vp in possible_videos:
                                if vp.exists():
                                    video_path = vp
                                    break
                            
                            if video_path and video_path.exists():
                                logger.info(f"Gallery: Found video at {video_path}")
                                # Read video as bytes to avoid caching issues
                                try:
                                    with open(video_path, "rb") as video_file:
                                        st.video(video_file.read())
                                except Exception as e:
                                    logger.error(f"Gallery: Error reading video {video_path}: {e}")
                                    st.error(f"Error loading video: {e}")
                                
                                # Info
                                info_col1, info_col2 = st.columns(2)
                                with info_col1:
                                    st.caption(f"📏 {project['route']['distance']}")
                                    st.caption(f"⏱️ {project['route']['duration']}")
                                with info_col2:
                                    st.caption(f"💰 ${project['costs']['total']}")
                                    st.caption(f"🖼️ {project['images']['successful']} images")
                                
                                # Download button
                                with open(video_path, "rb") as f:
                                    st.download_button(
                                        label="⬇️ Download Video",
                                        data=f,
                                        file_name=f"{project_id}.mp4",
                                        mime="video/mp4",
                                        key=f"download_{project_id}",
                                        use_container_width=True
                                    )
                            else:
                                # No video found - show info about what we checked
                                logger.warning(f"Gallery: No video found for {project_id}")
                                logger.warning(f"Gallery: Checked paths: {[str(p) for p in possible_videos]}")
                                st.warning(f"⚠️ Video file not found")
                                st.caption(f"Checked: {', '.join([p.name for p in possible_videos])}")
                                
                                # Still show route info
                                st.caption(f"📏 {project['route']['distance']} | 💰 ${project['costs']['total']}")
                                
                                # Offer to regenerate
                                if st.button(f"🔄 Regenerate", key=f"regen_{project_id}"):
                                    st.info(f"Run: `python regenerate_video.py --project {project_id}`")
                        
                        st.write("---")

# Footer
st.markdown("""
<div style="text-align: center; padding: 2rem 0; color: #94a3b8;">
    Made with ❤️ using Google Street View API & Streamlit
</div>
""", unsafe_allow_html=True)

