"""Roadbook route import and analysis helpers (GPX/KML)."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from typing import Any

from gpx_import import haversine, bearing


def parse_kml(data: bytes | str) -> dict[str, Any]:
    """Read KML LineString/MultiGeometry/ gx:Track and Point placemarks."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Fichier KML illisible : {exc}") from exc

    segments: list[list[dict[str, float]]] = []
    waypoints: list[dict[str, Any]] = []
    names: list[str] = []

    def descendants(element: ET.Element, wanted: str):
        return [node for node in element.iter() if node.tag.rsplit("}", 1)[-1].lower() == wanted.lower()]

    for placemark in descendants(root, "Placemark"):
        name_node = next((n for n in placemark if n.tag.rsplit("}", 1)[-1] == "name"), None)
        name = (name_node.text or "").strip() if name_node is not None else ""
        if name:
            names.append(name)

        for line in descendants(placemark, "LineString"):
            coord_node = next((n for n in line if n.tag.rsplit("}", 1)[-1] == "coordinates"), None)
            if coord_node is None or not coord_node.text:
                continue
            points = []
            for token in coord_node.text.split():
                values = token.split(",")
                try:
                    lon, lat = float(values[0]), float(values[1])
                except (ValueError, IndexError):
                    continue
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    point = {"lat": lat, "lon": lon}
                    if len(values) > 2 and values[2]:
                        try:
                            point["ele"] = float(values[2])
                        except ValueError:
                            pass
                    points.append(point)
            if len(points) >= 2:
                segments.append(points)

        # Google Earth gx:Track uses one <coord>lon lat alt</coord> per point.
        for track in descendants(placemark, "Track"):
            points = []
            for node in descendants(track, "coord"):
                try:
                    values = (node.text or "").split()
                    lon, lat = float(values[0]), float(values[1])
                except (ValueError, IndexError):
                    continue
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    point = {"lat": lat, "lon": lon}
                    if len(values) > 2:
                        try:
                            point["ele"] = float(values[2])
                        except ValueError:
                            pass
                    points.append(point)
            if len(points) >= 2:
                segments.append(points)

        for node in descendants(placemark, "Point"):
            coord = next((n for n in node if n.tag.rsplit("}", 1)[-1] == "coordinates"), None)
            if coord is None or not coord.text:
                continue
            try:
                values = coord.text.strip().split(",")
                lon, lat = float(values[0]), float(values[1])
            except (ValueError, IndexError):
                continue
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                waypoints.append({"point": {"lat": lat, "lon": lon}, "name": name or "Point KML"})

    if not segments:
        raise ValueError("Aucune géométrie KML exploitable (LineString ou gx:Track) n'a été trouvée.")

    distance_m = sum(
        haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
        for segment in segments for a, b in zip(segment, segment[1:])
    )
    return {
        "name": names[0] if names else "Tracé KML",
        "segments": segments,
        "waypoints": waypoints,
        "point_count": sum(len(s) for s in segments),
        "distance_m": distance_m,
    }


def analyze_directions(segments: list[list[dict[str, float]]], threshold_deg: float = 28.0) -> list[dict[str, Any]]:
    """Find meaningful heading changes and calculate cumulative chainage."""
    directions: list[dict[str, Any]] = []
    total_before = 0.0
    for segment_index, points in enumerate(segments):
        if len(points) < 3:
            total_before += sum(haversine((a["lat"], a["lon"]), (b["lat"], b["lon"])) for a, b in zip(points, points[1:]))
            continue
        local_distance = 0.0
        for i in range(1, len(points) - 1):
            prev, current, nxt = points[i - 1], points[i], points[i + 1]
            incoming = bearing((prev["lat"], prev["lon"]), (current["lat"], current["lon"]))
            outgoing = bearing((current["lat"], current["lon"]), (nxt["lat"], nxt["lon"]))
            delta = (outgoing - incoming + 540) % 360 - 180
            step_in = haversine((prev["lat"], prev["lon"]), (current["lat"], current["lon"]))
            if abs(delta) >= threshold_deg and step_in >= 3:
                if abs(delta) >= 150:
                    instruction = "Demi-tour / changement de sens"
                    category = "demi-tour"
                elif delta > 0:
                    instruction = "Tourner à droite"
                    category = "droite"
                else:
                    instruction = "Tourner à gauche"
                    category = "gauche"
                directions.append({
                    "pk_km": (total_before + local_distance + step_in) / 1000,
                    "lat": current["lat"], "lon": current["lon"],
                    "angle_deg": round(delta, 1), "instruction": instruction,
                    "category": category, "segment": segment_index + 1,
                })
            local_distance += step_in
        local_distance += haversine((points[-2]["lat"], points[-2]["lon"]), (points[-1]["lat"], points[-1]["lon"]))
        total_before += local_distance
    return directions


def fetch_osm_road_context(directions: list[dict[str, Any]], timeout: int = 20) -> tuple[list[dict[str, Any]], str | None]:
    """Enrich turn locations with nearby OSM highway tags via public Overpass API."""
    if not directions:
        return directions, None
    # Limit one batch to avoid excessive load on the public Overpass service.
    selected = directions[:35]
    clauses = [
        f'way(around:35,{item["lat"]:.6f},{item["lon"]:.6f})["highway"];'
        for item in selected
    ]
    query = "[out:json][timeout:15];(" + "".join(clauses) + ");out tags center;"
    try:
        import requests
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers={"User-Agent": "RoutePreview-Roadbook/1.0 (route analysis)"},
            timeout=timeout,
        )
        response.raise_for_status()
        elements = response.json().get("elements", [])
        roads = []
        for element in elements:
            tags = element.get("tags", {})
            center = element.get("center", {})
            if not center or not tags.get("highway"):
                continue
            roads.append((center.get("lat"), center.get("lon"), tags))
        for item in selected:
            candidates = []
            for lat, lon, tags in roads:
                if lat is None or lon is None:
                    continue
                distance = haversine((item["lat"], item["lon"]), (lat, lon))
                if distance <= 50:
                    candidates.append((distance, tags))
            if candidates:
                tags = min(candidates, key=lambda pair: pair[0])[1]
                item["road_name"] = tags.get("name", "Voie sans nom")
                item["road_type"] = tags.get("highway", "")
                item["maxspeed"] = tags.get("maxspeed", "")
                item["lanes"] = tags.get("lanes", "")
                item["surface"] = tags.get("surface", "")
                item["bridge"] = tags.get("bridge", "")
                item["tunnel"] = tags.get("tunnel", "")
        return directions, None
    except Exception as exc:
        return directions, f"Informations OpenStreetMap indisponibles : {exc}"
