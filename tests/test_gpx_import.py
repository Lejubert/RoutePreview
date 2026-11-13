import unittest

from gpx_import import parse_gpx, sample_gpx_segments


class GpxImportTests(unittest.TestCase):
    def test_namespaced_gpx_preserves_disconnected_segments_and_waypoints(self):
        xml = b"""<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
          <metadata><name>Test trace</name></metadata>
          <wpt lat="48.2" lon="2.2"><name>Waypoint A</name></wpt>
          <trk><name>Track</name>
            <trkseg><trkpt lat="48.0" lon="2.0"><ele>100</ele></trkpt>
                    <trkpt lat="48.001" lon="2.001"/></trkseg>
            <trkseg><trkpt lat="48.1" lon="2.1"/>
                    <trkpt lat="48.101" lon="2.101"/></trkseg>
          </trk>
        </gpx>"""
        parsed = parse_gpx(xml)
        self.assertEqual(parsed["name"], "Test trace")
        self.assertEqual(len(parsed["segments"]), 2)
        self.assertEqual(parsed["point_count"], 4)
        self.assertEqual(parsed["segments"][0][0]["ele"], 100.0)
        self.assertEqual(parsed["waypoints"][0]["name"], "Waypoint A")
        samples = sample_gpx_segments(parsed["segments"], 20)
        self.assertTrue(any(p["lat"] < 48.01 for p in samples))
        self.assertTrue(any(p["lat"] > 48.09 for p in samples))
        self.assertGreater(parsed["distance_m"], 0)

    def test_route_points_are_supported_without_tracks(self):
        xml = b"""<gpx version="1.0"><rte>
          <rtept lat="45" lon="1"/><rtept lat="45.01" lon="1.01"/>
        </rte></gpx>"""
        parsed = parse_gpx(xml)
        self.assertEqual(len(parsed["segments"]), 1)
        self.assertEqual(parsed["point_count"], 2)

    def test_invalid_document_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_gpx(b"<not-gpx/>")

    def test_empty_gpx_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_gpx(b"<gpx version='1.1'/>")


if __name__ == "__main__":
    unittest.main()
