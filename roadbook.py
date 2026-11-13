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


def _sample_route_anchors(points: list[dict[str, float]], spacing_m: float) -> list[dict[str, float]]:
    """Create pass-through anchors along one imported segment, retaining its PK."""
    if spacing_m <= 0:
        raise ValueError("L'espacement des points de référence doit être positif.")
    if len(points) < 2:
        return []

    anchors = [{"lat": points[0]["lat"], "lon": points[0]["lon"], "pk_m": 0.0}]
    cumulative = 0.0
    next_target = spacing_m

    for a, b in zip(points, points[1:]):
        length = haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
        if length <= 0:
            continue
        while next_target < cumulative + length:
            ratio = (next_target - cumulative) / length
            anchors.append({
                "lat": a["lat"] + ratio * (b["lat"] - a["lat"]),
                "lon": a["lon"] + ratio * (b["lon"] - a["lon"]),
                "pk_m": next_target,
            })
            next_target += spacing_m
        cumulative += length

    last = points[-1]
    if haversine((anchors[-1]["lat"], anchors[-1]["lon"]), (last["lat"], last["lon"])) > 0.5:
        anchors.append({"lat": last["lat"], "lon": last["lon"], "pk_m": cumulative})
    else:
        anchors[-1]["pk_m"] = cumulative
    return anchors


def _nearest_chainage(point: tuple[float, float], points: list[dict[str, float]]) -> tuple[float, float]:
    """Return (distance to imported trace in metres, local chainage in metres)."""
    if len(points) < 2:
        return float("inf"), 0.0

    target_lat, target_lon = point
    radius = 6_371_000.0
    best_distance = float("inf")
    best_chainage = 0.0
    cumulative = 0.0

    for a, b in zip(points, points[1:]):
        segment_length = haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
        if segment_length <= 0:
            continue
        mean_lat = math.radians((a["lat"] + b["lat"] + target_lat) / 3.0)
        ax = math.radians(a["lon"] - target_lon) * radius * math.cos(mean_lat)
        ay = math.radians(a["lat"] - target_lat) * radius
        bx = math.radians(b["lon"] - target_lon) * radius * math.cos(mean_lat)
        by = math.radians(b["lat"] - target_lat) * radius
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        ratio = 0.0 if denom == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / denom))
        distance = math.hypot(ax + ratio * dx, ay + ratio * dy)
        if distance < best_distance:
            best_distance = distance
            best_chainage = cumulative + ratio * segment_length
        cumulative += segment_length

    return best_distance, best_chainage


def _duration_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value[:-1]) if value.endswith("s") else float(value)
    except (TypeError, ValueError):
        return None


def fetch_google_route_instructions(
    segments: list[list[dict[str, float]]],
    api_key: str,
    anchor_spacing_m: float = 1000.0,
    max_deviation_m: float = 75.0,
    timeout: int = 25,
) -> dict[str, Any]:
    """Fetch Google navigation steps constrained by pass-through points from the source trace.

    The imported geometry is never replaced by Google's computed route. Each API response
    is used only for textual steps and estimates. Step geometry is compared with the source
    trace and flagged when its maximum sampled offset exceeds max_deviation_m.
    """
    if not api_key:
        raise ValueError("Renseigne une clé Google API pour utiliser Routes API.")
    if not segments:
        raise ValueError("La trace ne contient aucun segment exploitable.")

    import requests

    endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"
    field_mask = ",".join([
        "routes.legs.steps.navigationInstruction.instructions",
        "routes.legs.steps.navigationInstruction.maneuver",
        "routes.legs.steps.distanceMeters",
        "routes.legs.steps.staticDuration",
        "routes.legs.steps.startLocation",
        "routes.legs.steps.polyline.encodedPolyline",
    ])
    all_steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    request_count = 0
    global_offset_m = 0.0
    max_intermediates = 10  # Avoid the higher-priced 11-25 waypoint request tier.

    for segment_index, points in enumerate(segments):
        if len(points) < 2:
            continue
        anchors = _sample_route_anchors(points, anchor_spacing_m)
        if len(anchors) < 2:
            continue

        start_index = 0
        while start_index < len(anchors) - 1:
            end_index = min(start_index + max_intermediates + 1, len(anchors) - 1)
            origin = anchors[start_index]
            destination = anchors[end_index]
            intermediates = anchors[start_index + 1:end_index]

            body = {
                "origin": {"location": {"latLng": {
                    "latitude": origin["lat"], "longitude": origin["lon"]
                }}},
                "destination": {"location": {"latLng": {
                    "latitude": destination["lat"], "longitude": destination["lon"]
                }}},
                "intermediates": [
                    {"location": {"latLng": {
                        "latitude": item["lat"], "longitude": item["lon"]
                    }}, "via": True}
                    for item in intermediates
                ],
                "travelMode": "DRIVE",
                "languageCode": "fr-FR",
                "units": "METRIC",
                "optimizeWaypointOrder": False,
            }

            try:
                response = requests.post(
                    endpoint,
                    json=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": api_key,
                        "X-Goog-FieldMask": field_mask,
                    },
                    timeout=timeout,
                )
                if response.status_code >= 400:
                    try:
                        detail = response.json().get("error", {}).get("message", response.text)
                    except Exception:
                        detail = response.text
                    raise RuntimeError(f"Google Routes API ({response.status_code}) : {detail}")
                payload = response.json()
            except Exception as exc:
                raise RuntimeError(
                    f"Échec de la requête Google Routes API sur le segment {segment_index + 1} "
                    f"(portion {start_index + 1}) : {exc}"
                ) from exc

            request_count += 1
            routes = payload.get("routes", [])
            if not routes:
                warnings.append(
                    f"Aucune instruction Google retournée pour le segment {segment_index + 1}, "
                    f"portion {start_index + 1}."
                )
                start_index = end_index
                continue

            for leg in routes[0].get("legs", []):
                for step in leg.get("steps", []):
                    nav = step.get("navigationInstruction", {})
                    instruction = nav.get("instructions")
                    if not instruction:
                        continue

                    encoded = step.get("polyline", {}).get("encodedPolyline", "")
                    try:
                        step_geometry = polyline.decode(encoded) if encoded else []
                    except Exception:
                        step_geometry = []

                    deviations = [
                        _nearest_chainage((lat, lon), points)[0]
                        for lat, lon in step_geometry
                    ]
                    max_offset = max(deviations) if deviations else None

                    start_location = step.get("startLocation", {}).get("latLng", {})
                    if "latitude" in start_location and "longitude" in start_location:
                        step_start = (start_location["latitude"], start_location["longitude"])
                    elif step_geometry:
                        step_start = step_geometry[0]
                    else:
                        step_start = (origin["lat"], origin["lon"])

                    _, local_pk_m = _nearest_chainage(step_start, points)
                    if max_offset is None:
                        match_status = "Non vérifiable"
                    elif max_offset <= max_deviation_m:
                        match_status = "Proche de la trace"
                    else:
                        match_status = "Écart à vérifier"

                    all_steps.append({
                        "segment": segment_index + 1,
                        "google_pk_km": (global_offset_m + local_pk_m) / 1000.0,
                        "google_instruction": instruction,
                        "google_maneuver": nav.get("maneuver", ""),
                        "google_distance_m": step.get("distanceMeters"),
                        "google_duration_s": _duration_seconds(step.get("staticDuration")),
                        "google_max_deviation_m": round(max_offset, 1) if max_offset is not None else None,
                        "google_match_status": match_status,
                    })

            start_index = end_index

        global_offset_m += sum(
            haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            for a, b in zip(points, points[1:])
        )

    if not all_steps:
        warnings.append("Google Routes API n'a fourni aucune instruction exploitable.")
    return {
        "steps": all_steps,
        "request_count": request_count,
        "warnings": warnings,
        "anchor_spacing_m": anchor_spacing_m,
        "max_deviation_m": max_deviation_m,
    }
