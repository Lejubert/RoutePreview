"""GPX parsing and route geometry helpers.

The imported GPX geometry is treated as authoritative: no routing service is
called, point order is preserved, and disconnected track segments stay separate.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from typing import Any


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _point(element: ET.Element) -> dict[str, float] | None:
    try:
        lat = float(element.attrib["lat"])
        lon = float(element.attrib["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    result = {"lat": lat, "lon": lon}
    ele = next((child for child in element if _local_name(child.tag) == "ele"), None)
    if ele is not None and ele.text:
        try:
            result["ele"] = float(ele.text)
        except ValueError:
            pass
    return result


def parse_gpx(data: bytes | str) -> dict[str, Any]:
    """Parse GPX 1.0/1.1 bytes or text into ordered track/route segments."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Fichier GPX illisible : {exc}") from exc

    if _local_name(root.tag) != "gpx":
        raise ValueError("Le fichier fourni n'est pas un document GPX.")

    segments: list[list[dict[str, float]]] = []
    # Track segments are kept distinct. Never join the end of one to the next.
    for track in (node for node in root.iter() if _local_name(node.tag) == "trk"):
        for segment in (node for node in track if _local_name(node.tag) == "trkseg"):
            points = [_point(node) for node in segment if _local_name(node.tag) == "trkpt"]
            points = [point for point in points if point is not None]
            if len(points) >= 2:
                segments.append(points)

    # Some GPX files contain routes but no track logs.
    if not segments:
        for route in (node for node in root.iter() if _local_name(node.tag) == "rte"):
            points = [_point(node) for node in route if _local_name(node.tag) == "rtept"]
            points = [point for point in points if point is not None]
            if len(points) >= 2:
                segments.append(points)

    waypoints = []
    for node in (item for item in root.iter() if _local_name(item.tag) == "wpt"):
        point = _point(node)
        if point:
            name = next((child.text for child in node if _local_name(child.tag) == "name"), None)
            waypoints.append({"point": point, "name": name or "Point de passage"})

    if not segments:
        raise ValueError("Aucune trace ou route GPX exploitable (au moins 2 points par segment) n'a été trouvée.")

    name_node = next((node for node in root.iter() if _local_name(node.tag) == "name"), None)
    name = name_node.text.strip() if name_node is not None and name_node.text else "Tracé GPX"
    total_points = sum(len(segment) for segment in segments)
    distance_m = sum(
        haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
        for segment in segments for a, b in zip(segment, segment[1:])
    )
    return {
        "name": name,
        "segments": segments,
        "waypoints": waypoints,
        "point_count": total_points,
        "distance_m": distance_m,
    }


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6_371_000
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def sample_gpx_segments(segments: list[list[dict[str, float]]], interval_meters: float) -> list[dict[str, float]]:
    """Interpolate image positions along each GPX segment without bridging gaps."""
    if interval_meters <= 0:
        raise ValueError("L'intervalle d'échantillonnage doit être positif.")

    samples: list[dict[str, float]] = []
    for points in segments:
        if len(points) < 2:
            continue
        next_distance = 0.0
        traversed = 0.0
        for a, b in zip(points, points[1:]):
            start = (a["lat"], a["lon"])
            end = (b["lat"], b["lon"])
            length = haversine(start, end)
            if length <= 0:
                continue
            direction = bearing(start, end)
            while next_distance <= traversed + length:
                ratio = max(0.0, min(1.0, (next_distance - traversed) / length))
                samples.append({
                    "lat": a["lat"] + ratio * (b["lat"] - a["lat"]),
                    "lng": a["lon"] + ratio * (b["lon"] - a["lon"]),
                    "heading": direction,
                })
                next_distance += interval_meters
            traversed += length

        last = points[-1]
        samples.append({
            "lat": last["lat"],
            "lng": last["lon"],
            "heading": bearing((points[-2]["lat"], points[-2]["lon"]), (last["lat"], last["lon"])),
        })
    return samples
