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
from roadbook import parse_kml, analyze_directions, fetch_osm_road_context, fetch_google_route_instructions

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


def add_gps_overlay(image: Image.Image, lat: float, lng: float) -> Image.Image:
    """Add the GPS coordinates corresponding to this frame in the lower-left corner."""
    draw = ImageDraw.Draw(image)
    coordinate_text = f"GPS  {lat:.6f}, {lng:.6f}"

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    padding_x, padding_y = 10, 7
    bbox = draw.textbbox((0, 0), coordinate_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x, y = 12, image.height - text_height - 2 * padding_y - 12

    draw.rectangle(
        (x, y, x + text_width + 2 * padding_x, y + text_height + 2 * padding_y),
        fill=(0, 0, 0),
    )
    draw.text(
        (x + padding_x, y + padding_y - bbox[1]),
        coordinate_text,
        fill=(255, 255, 255),
        font=font,
    )
    return image


def create_video_from_images(image_dir: Path, output_path: Path, fps: int = 10) -> bool:
    """Create a silent video from the downloaded Street View images."""
    images = sorted(image_dir.glob("*.jpg"))
    if not images:
        return False
    list_file = image_dir / "images.txt"
    with open(list_file, "w") as f:
        for img in images:
            f.write(f"file '{img.absolute()}'\n")
            f.write(f"duration {1/fps}\n")
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
tab1, tab2, tab3 = st.tabs(["🎬 Create Video", "📁 Video Gallery", "🧭 Roadbook"])

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
            calls = cost_data.get("calls", {})
            total_requests = sum(calls.values())
            st.metric("Estimated Cost", f"${cost_data['total']}")
            st.metric("Google Maps API requests", f"{total_requests:,}".replace(",", " "))
            with st.expander("Cost & request breakdown", expanded=True):
                st.write(f"Geocoding: {calls.get('geocoding', 0)} request(s) — ${cost_data['geocoding']}")
                st.write(f"Directions: {calls.get('directions', 0)} request(s) — ${cost_data['directions']}")
                st.write(f"Street View: {calls.get('streetview', 0)} request(s) — ${cost_data['streetview']}")
                st.caption("Places Autocomplete requests made while typing are separate and vary with your searches; they are not included in this generation estimate.")
    
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
            st.caption("Saisissez un départ et une destination, ou importez directement un fichier GPX.")
            origin = st_searchbox(
                search_places, key="origin_search",
                placeholder="Saisir le lieu de départ...",
                clear_on_submit=False,
            )
            destination = st_searchbox(
                search_places, key="destination_search",
                placeholder="Saisir le lieu d'arrivée...",
                clear_on_submit=False,
            )
            if origin:
                st.success(f"✅ Départ : {origin}")
            if destination:
                st.success(f"✅ Destination : {destination}")
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
            # Generic initial view; the map recenters on the route when available.
            map_center = [46.603354, 1.888334]
            m = folium.Map(location=map_center, zoom_start=6, tiles="OpenStreetMap")
            if "route_coords" in st.session_state and st.session_state.route_coords:
                coords = st.session_state.route_coords
                folium.PolyLine(coords, color="#6366f1", weight=4, opacity=0.8).add_to(m)
                folium.Marker(coords[0], popup="Départ", icon=folium.Icon(color="green", icon="play")).add_to(m)
                folium.Marker(coords[-1], popup="Arrivée", icon=folium.Icon(color="red", icon="stop")).add_to(m)
                m.fit_bounds([coords[0], coords[-1]])
            else:
                folium.Marker(
                    map_center,
                    popup="Saisissez un départ et une destination pour afficher le tracé.",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)
            st_folium(m, width=None, height=400, use_container_width=True, key="route_map")

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

            # Estimate the Google Maps requests before downloading any Street View images.
            planned_calls = {
                "geocoding": api_calls["geocoding"],
                "directions": api_calls["directions"],
                "streetview": num_images,
            }
            costs = calculate_costs(
                planned_calls["geocoding"],
                planned_calls["directions"],
                planned_calls["streetview"],
            )
            st.session_state.estimated_cost = costs

            total_planned_requests = sum(planned_calls.values())
            st.write(f"✅ Will capture {num_images} images")
            st.markdown("#### 📡 Google Maps API request estimate")
            request_cols = st.columns(4)
            request_cols[0].metric("Total requests", total_planned_requests)
            request_cols[1].metric("Geocoding", planned_calls["geocoding"])
            request_cols[2].metric("Directions", planned_calls["directions"])
            request_cols[3].metric("Street View", planned_calls["streetview"])
            if route_mode == "Fichier GPX (tracé exact)":
                st.caption("GPX mode: no Geocoding or Directions requests. One Street View request is planned per sampled image.")
            else:
                st.caption("Address mode: 2 Geocoding requests + 1 Directions request + 1 Street View request per sampled image. Places Autocomplete requests made while typing are not included.")
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
                    # Every frame gets its exact sampled GPS coordinates.
                    img = Image.open(BytesIO(image_data)).convert("RGB")
                    img = add_gps_overlay(img, point["lat"], point["lng"])
                    # The compass remains optional; GPS coordinates are always shown.
                    if add_overlays:
                        img = add_direction_overlay(img, point["heading"])
                    image_path = images_dir / f"frame_{i:05d}.jpg"
                    img.save(image_path, "JPEG", quality=92)
                    
                    successful_images += 1
            
            # Count every Street View HTTP request attempted, including failed image responses.
            api_calls["streetview"] = num_images
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
                
            else:
                st.error("❌ Failed to create video. Make sure FFmpeg is installed.")

    # Keep the latest generated video visible across Streamlit reruns.
    latest_project_id = st.session_state.get("latest_project")
    if latest_project_id:
        latest_metadata = load_project_metadata(latest_project_id)
        latest_video_path = PROJECTS_DIR / latest_project_id / "video.mp4"

        if latest_metadata and latest_video_path.exists():
            st.write("---")
            st.markdown("### 🎬 Your Video")
            col_video, col_info = st.columns([3, 1])

            with col_video:
                with open(latest_video_path, "rb") as video_file:
                    st.video(video_file.read())

            with col_info:
                st.markdown("#### 📊 Video Info")
                video_info = latest_metadata.get("video", {})
                costs_info = latest_metadata.get("costs", {})
                st.metric("File Size", f"{video_info.get('size_mb', 0)} MB")
                st.metric("Duration", f"{video_info.get('duration_seconds', 0):.1f}s")
                st.metric("Total Cost", f"${costs_info.get('total', 0)}")

                with open(latest_video_path, "rb") as video_file:
                    st.download_button(
                        label="⬇️ Download Video",
                        data=video_file.read(),
                        file_name=f"{latest_project_id}.mp4",
                        mime="video/mp4",
                        use_container_width=True,
                        key=f"download_latest_{latest_project_id}",
                    )
        else:
            st.session_state.pop("latest_project", None)


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


# ============================================================================
# TAB 3: ROADBOOK - IMPORT, ROUTE MAPPING, MILEAGE AND DIRECTIONS
# ============================================================================

with tab3:
    st.markdown("### 🧭 Générateur de roadbook")
    st.caption("Importe une trace GPX ou KML. La géométrie importée reste la référence : aucune route alternative n'est calculée.")

    roadbook_file = st.file_uploader(
        "Importer une trace GPX ou KML",
        type=["gpx", "kml"],
        key="roadbook_route_file",
        help="GPX (track/route) et KML (LineString, MultiGeometry et gx:Track) sont acceptés."
    )

    if roadbook_file is not None:
        try:
            raw_route = roadbook_file.getvalue()
            if roadbook_file.name.lower().endswith(".kml"):
                roadbook_data = parse_kml(raw_route)
                route_format = "KML"
            else:
                roadbook_data = parse_gpx(raw_route)
                route_format = "GPX"

            st.session_state["roadbook_data"] = roadbook_data
            st.session_state["roadbook_file_name"] = roadbook_file.name
            st.session_state["roadbook_format"] = route_format
            st.session_state["roadbook_directions"] = analyze_directions(roadbook_data["segments"])
            st.session_state.pop("roadbook_osm_error", None)
            st.session_state.pop("roadbook_google_guidance", None)
            st.session_state.pop("roadbook_google_error", None)
        except ValueError as exc:
            st.error(str(exc))
            st.session_state.pop("roadbook_data", None)

    roadbook_data = st.session_state.get("roadbook_data")
    if roadbook_data:
        segments = roadbook_data["segments"]
        directions = st.session_state.get("roadbook_directions", [])
        distance_km = roadbook_data["distance_m"] / 1000
        file_name = st.session_state.get("roadbook_file_name", "Trace importée")
        route_format = st.session_state.get("roadbook_format", "GPX")

        st.success(f"{route_format} chargé : {file_name}")
        metric_cols = st.columns(4)
        metric_cols[0].metric("Kilométrage total", f"{distance_km:.3f} km")
        metric_cols[1].metric("Points GPS", f"{roadbook_data['point_count']:,}".replace(",", " "))
        metric_cols[2].metric("Segments", len(segments))
        metric_cols[3].metric("Changements de direction", len(directions))

        st.markdown("#### 🗺️ Cartographie du parcours")
        all_points = [point for segment in segments for point in segment]
        center = [all_points[0]["lat"], all_points[0]["lon"]]
        route_map = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap")
        bounds = []
        for index, segment in enumerate(segments):
            line = [[point["lat"], point["lon"]] for point in segment]
            bounds.extend(line)
            folium.PolyLine(
                line, color="#16a34a", weight=5, opacity=0.9,
                tooltip=f"Trace {route_format} — segment {index + 1}"
            ).add_to(route_map)

        first_point = segments[0][0]
        last_point = segments[-1][-1]
        folium.Marker(
            [first_point["lat"], first_point["lon"]], tooltip="Départ",
            icon=folium.Icon(color="green", icon="play")
        ).add_to(route_map)
        folium.Marker(
            [last_point["lat"], last_point["lon"]], tooltip="Arrivée",
            icon=folium.Icon(color="red", icon="flag")
        ).add_to(route_map)

        for index, item in enumerate(directions):
            popup = (
                f"PK {item['pk_km']:.3f} — {item['instruction']} "
                f"({item['angle_deg']:+.0f}°)"
            )
            if item.get("road_name"):
                popup += f" — {item['road_name']}"
            folium.CircleMarker(
                [item["lat"], item["lon"]], radius=6, color="#f59e0b",
                fill=True, fill_opacity=0.95, tooltip=popup, popup=popup
            ).add_to(route_map)

        for waypoint in roadbook_data.get("waypoints", []):
            point = waypoint["point"]
            folium.CircleMarker(
                [point["lat"], point["lon"]], radius=5, color="#3b82f6",
                fill=True, tooltip=waypoint["name"]
            ).add_to(route_map)

        route_map.fit_bounds(bounds)
        st_folium(
            route_map, width=None, height=520, use_container_width=True,
            key=f"roadbook_map_{file_name}"
        )

        st.markdown("#### 🧭 Directions calculées depuis la trace")
        st.caption("Les changements de direction sont estimés à partir des angles entre segments GPS. Ils constituent une aide à la lecture, pas un guidage routier certifié.")
        if directions:
            direction_rows = []
            for item in directions:
                direction_rows.append({
                    "PK (km)": round(item["pk_km"], 3),
                    "Instruction": item["instruction"],
                    "Angle": f"{item['angle_deg']:+.0f}°",
                    "Latitude": round(item["lat"], 6),
                    "Longitude": round(item["lon"], 6),
                    "Voie OSM": item.get("road_name", "Non renseignée"),
                    "Type OSM": item.get("road_type", ""),
                    "Vitesse max. OSM": item.get("maxspeed", ""),
                    "Voies OSM": item.get("lanes", ""),
                    "Surface OSM": item.get("surface", ""),
                })
            st.dataframe(direction_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun changement de direction significatif détecté avec le seuil actuel (28°). La trace reste consultable sur la carte.")

        st.markdown("#### 🛣️ Informations routières OpenStreetMap")
        st.caption("Recherche facultative des voies proches des changements de direction : nom, catégorie, vitesse maximale, nombre de voies et surface lorsque ces attributs sont renseignés dans OpenStreetMap.")
        if st.button(
            "Récupérer les informations routières OSM",
            key="roadbook_fetch_osm",
            disabled=not bool(directions),
            help="Interroge le service public Overpass d'OpenStreetMap pour les points de changement de direction."
        ):
            with st.spinner("Recherche des informations routières OpenStreetMap…"):
                enriched, osm_error = fetch_osm_road_context(directions)
                st.session_state["roadbook_directions"] = enriched
                st.session_state["roadbook_osm_error"] = osm_error
            st.rerun()

        osm_error = st.session_state.get("roadbook_osm_error")
        if osm_error:
            st.warning(osm_error)
        elif any(item.get("road_name") or item.get("road_type") for item in directions):
            st.success("Informations routières OpenStreetMap récupérées pour les points où des voies ont été trouvées.")
        else:
            st.info("Les informations routières ne sont pas encore chargées. La disponibilité dépend de la couverture et des attributs OpenStreetMap.")

        st.markdown("#### 🧭 Directions Google Maps (Routes API)")
        st.caption(
            "Google fournit des consignes et estimations en suivant des points de passage issus de la trace. "
            "La ligne verte et les PK restent calculés exclusivement depuis le GPX/KML."
        )
        if not GOOGLE_API_KEY:
            st.info("Renseigne une clé Google API dans les paramètres pour activer Routes API.")
        else:
            google_col1, google_col2 = st.columns([1, 1])
            with google_col1:
                anchor_spacing = st.select_slider(
                    "Espacement des points de passage Google",
                    options=[250, 500, 750, 1000, 1500, 2000],
                    value=1000,
                    format_func=lambda value: f"{value} m",
                    help="Plus l'espacement est faible, plus Google est contraint de suivre la trace, mais le nombre de requêtes peut augmenter."
                )
            with google_col2:
                max_deviation = st.select_slider(
                    "Écart maximal indicatif",
                    options=[25, 50, 75, 100, 150],
                    value=75,
                    format_func=lambda value: f"{value} m",
                    help="Les étapes dont la géométrie Google s'écarte davantage de la trace sont signalées."
                )
            if st.button(
                "Récupérer les directions Google",
                key="roadbook_fetch_google",
                help="Appelle Google Routes API. Les réponses ne remplacent jamais la trace importée."
            ):
                try:
                    with st.spinner("Interrogation de Google Routes API…"):
                        guidance = fetch_google_route_instructions(
                            segments,
                            GOOGLE_API_KEY,
                            anchor_spacing_m=float(anchor_spacing),
                            max_deviation_m=float(max_deviation),
                        )
                    st.session_state["roadbook_google_guidance"] = guidance
                    st.session_state.pop("roadbook_google_error", None)
                except Exception as exc:
                    st.session_state.pop("roadbook_google_guidance", None)
                    st.session_state["roadbook_google_error"] = str(exc)
            google_error = st.session_state.get("roadbook_google_error")
            if google_error:
                st.error(google_error)
                st.caption("Vérifie que Routes API est activée sur le projet Google Cloud, que la facturation est configurée et que la clé autorise cette API.")
            guidance = st.session_state.get("roadbook_google_guidance")
            if guidance:
                google_steps = guidance.get("steps", [])
                google_metrics = st.columns(3)
                google_metrics[0].metric("Requêtes Google", guidance.get("request_count", 0))
                google_metrics[1].metric("Instructions", len(google_steps))
                flagged = sum(1 for item in google_steps if item["google_match_status"] == "Écart à vérifier")
                google_metrics[2].metric("Écarts à vérifier", flagged)
                if guidance.get("warnings"):
                    for warning in guidance["warnings"]:
                        st.warning(warning)
                if google_steps:
                    google_rows = [{
                        "PK trace (km)": round(item["google_pk_km"], 3),
                        "Instruction Google": item["google_instruction"],
                        "Manœuvre": item.get("google_maneuver", ""),
                        "Distance Google (m)": item.get("google_distance_m"),
                        "Durée estimée (s)": round(item["google_duration_s"], 1) if item.get("google_duration_s") is not None else None,
                        "Écart max. (m)": item.get("google_max_deviation_m"),
                        "Correspondance": item["google_match_status"],
                    } for item in google_steps]
                    st.dataframe(google_rows, use_container_width=True, hide_index=True)
                st.caption(
                    "Le PK est projeté sur la trace importée. La distance et la durée sont celles estimées par Google pour l'étape calculée ; "
                    "elles peuvent différer du kilométrage GPS. Les étapes signalées comme écartées doivent être contrôlées."
                )
        st.warning(
            "Important pour les études de transport exceptionnel : Routes API en mode DRIVE ne valide pas les contraintes "
            "de hauteur, largeur, longueur, masse, rayon de giration, ouvrages ou autorisations. Les informations doivent être "
            "vérifiées séparément auprès des sources et autorités compétentes."
        )

        st.markdown("#### 📌 Waypoints présents dans le fichier")
        waypoints = roadbook_data.get("waypoints", [])
        if waypoints:
            waypoint_rows = [{
                "Nom": item["name"],
                "Latitude": round(item["point"]["lat"], 6),
                "Longitude": round(item["point"]["lon"], 6),
            } for item in waypoints]
            st.dataframe(waypoint_rows, use_container_width=True, hide_index=True)
        else:
            st.caption("Aucun waypoint distinct n'est présent dans le fichier importé.")

        st.caption("Le kilométrage est calculé en distance géodésique entre les points successifs. Les segments GPX/KML disjoints ne sont jamais reliés artificiellement. Les données OSM peuvent être incomplètes et doivent être vérifiées sur le terrain.")
    else:
        st.info("Importe un fichier GPX ou KML pour afficher le parcours, calculer son kilométrage et analyser les changements de direction.")

# Footer
st.markdown("""
<div style="text-align: center; padding: 2rem 0; color: #94a3b8;">
    Made with ❤️ using Google Street View API & Streamlit
</div>
""", unsafe_allow_html=True)

