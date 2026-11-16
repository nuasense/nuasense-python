import json
import unittest
from pathlib import Path

import nuasense
from nuasense import reading

from test_client import answering

MONOREPO_SCHEMA = Path(__file__).resolve().parents[2] / "station-schema" / "nuasense-reading.schema.json"
PACKAGED_SCHEMA = Path(reading.__file__).with_name("reading.schema.json")


class CheckTest(unittest.TestCase):
    def test_known_fields_and_channels(self):
        clean, skipped = reading.check({"temperature": 21.4, "soil_moisture": 34, "soil_moisture_2": "41.5",
                                        "hive_weight": 42.6, "door_open": False})
        self.assertEqual(clean, {"temperature": 21.4, "soil_moisture": 34, "soil_moisture_2": 41.5,
                                 "hive_weight": 42.6, "door_open": 0})
        self.assertEqual(skipped, {})

    def test_unknown_name_raises_with_a_suggestion(self):
        with self.assertRaisesRegex(ValueError, 'no field "soil_moistur".*soil_moisture'):
            reading.check({"soil_moistur": 30})
        with self.assertRaises(ValueError):
            reading.check({"soil_moisture_9": 30})  # channels go to 8

    def test_sensor_faults_are_left_out_not_raised(self):
        clean, skipped = reading.check({"temperature": -127, "humidity": 55, "soil_moisture": None,
                                        "soil_ec": float("nan"), "pressure": "err"})
        self.assertEqual(clean, {"humidity": 55})
        self.assertIn("-127 outside", skipped["temperature"])
        self.assertIn("not a number", skipped["pressure"])
        self.assertNotIn("soil_moisture", skipped)

    def test_at_most_40_values(self):
        many = {f"{f}_{i}": 1 for f in ("soil_moisture", "soil_ec", "soil_ph", "water_ph", "co2") for i in range(1, 9)}
        many = {k: (500 if k.startswith("co2") else 1) for k in many}
        many["temperature"] = 20
        with self.assertRaisesRegex(ValueError, "At most 40"):
            reading.check(many)

    @unittest.skipUnless(MONOREPO_SCHEMA.exists(), "only inside the NuaSense monorepo")
    def test_packaged_schema_matches_station_schema(self):
        self.assertEqual(json.loads(PACKAGED_SCHEMA.read_text()), json.loads(MONOREPO_SCHEMA.read_text()))


class SendTest(unittest.TestCase):
    def test_posts_json_with_device_and_software(self):
        patch, calls = answering((200, "OK"))
        with patch:
            out = nuasense.send("abcd-efgh-ijkl", "garden-pi", {"soil_moisture": 34}, temperature=21.4)
        req = calls[0]
        self.assertEqual(req.full_url, "https://api.nuasense.com/station/abcd-efgh-ijkl")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertIsNone(req.get_header("Authorization"))
        self.assertEqual(json.loads(req.data), {"device_id": "garden-pi", "software": "nuasense-python/" + nuasense.__version__,
                                                "soil_moisture": 34, "temperature": 21.4})
        self.assertTrue(out["sent"])

    def test_nothing_left_is_not_sent(self):
        patch, calls = answering()
        with patch:
            out = nuasense.send("abcd-efgh-ijkl", "garden-pi", temperature=-127)
        self.assertFalse(out["sent"])
        self.assertIn("temperature", out["skipped"])
        self.assertEqual(calls, [])

    def test_device_id_is_required(self):
        for bad in ("", "pi", "garden pi", "x" * 49):
            with self.assertRaisesRegex(ValueError, "device_id"):
                nuasense.send("abcd-efgh-ijkl", bad, temperature=20)

    def test_answers_are_explained(self):
        for status, text in ((404, "does not know this station token"), (409, "belongs to another device"),
                             (429, "Too many uploads"), (500, r"refused the reading \(500\)")):
            patch, _ = answering((status, "x"))
            with patch, self.assertRaisesRegex(nuasense.NuaSenseError, text):
                nuasense.send("abcd-efgh-ijkl", "garden-pi", temperature=20)


if __name__ == "__main__":
    unittest.main()
