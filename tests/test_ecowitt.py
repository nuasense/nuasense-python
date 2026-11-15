import unittest
from datetime import datetime, timezone

from nuasense import ecowitt

# Reference values produced by the JavaScript packages (n8n-nodes-nuasense 0.1.1,
# lib ecowitt.js): one device must keep one PASSKEY whichever package sends.
JS_PASSKEYS = {
    "shed": "985FCC5F91BFEB59B5C3D0E404026E73",
    "pi-garden": "31512E4C3FD643BA6868A5B58E0A41D0",
    "Gärtchen": "42F9C46C3FAECFC243B71173B1F8D088",
    "🌧": "D22F55545B1470AE66FD13E3825DBDE8",
}

JS_FIELDS = {
    "PASSKEY": "985FCC5F91BFEB59B5C3D0E404026E73",
    "stationtype": "python_0.1.0",
    "dateutc": "2026-11-16 08:30:00",
    "tempf": "70.52",
    "humidity": "63",
    "baromabsin": "29.92",
    "windspeedmph": "6.21",
    "windgustmph": "3.11",
    "winddir": "270",
    "yearlyrainin": "0.48",
    "solarradiation": "500",
}


class PasskeyTest(unittest.TestCase):
    def test_matches_the_javascript_packages(self):
        for name, expected in JS_PASSKEYS.items():
            self.assertEqual(ecowitt.passkey_for(name), expected, name)

    def test_stable_and_distinct(self):
        self.assertRegex(ecowitt.passkey_for("shed"), r"^[0-9A-F]{32}$")
        self.assertNotEqual(ecowitt.passkey_for("shed"), ecowitt.passkey_for("roof"))


class FieldsTest(unittest.TestCase):
    def test_same_form_as_the_javascript_packages(self):
        fields = ecowitt.to_ecowitt_fields(
            device_id="shed", station_type="python_0.1.0",
            temperature=21.4, humidity=63.4, pressure=1013.2,
            wind_speed=10, wind_unit="kmh", wind_gusts=5, wind_direction=-90,
            rain_total=12.2, lux=60000, time="2026-11-16T08:30:00Z",
        )
        self.assertEqual(list(fields.items()), list(JS_FIELDS.items()))

    def test_solar_wins_over_lux_and_empty_values_are_left_out(self):
        fields = ecowitt.to_ecowitt_fields(device_id="x", station_type="t", solar=412.345, lux=1,
                                           humidity="", pressure=None, temperature=float("nan"))
        self.assertEqual(fields["solarradiation"], "412.35")
        for key in ("humidity", "baromabsin", "tempf"):
            self.assertNotIn(key, fields)

    def test_zero_is_a_value(self):
        fields = ecowitt.to_ecowitt_fields(device_id="x", station_type="t", rain_total=0, temperature=-17.7778)
        self.assertEqual(fields["yearlyrainin"], "0")
        self.assertEqual(fields["tempf"], "0")
        self.assertTrue(ecowitt.has_values(fields))

    def test_half_rounds_up_like_javascript(self):
        fields = ecowitt.to_ecowitt_fields(device_id="x", station_type="t", humidity=62.5, wind_direction=359.6)
        self.assertEqual(fields["humidity"], "63")
        self.assertEqual(fields["winddir"], "360")

    def test_nothing_measured(self):
        self.assertFalse(ecowitt.has_values(ecowitt.to_ecowitt_fields(device_id="x", station_type="t")))


class TimeTest(unittest.TestCase):
    def test_datetime_and_offsets(self):
        self.assertEqual(ecowitt.date_utc(datetime(2026, 11, 16, 11, 30, tzinfo=timezone.utc)), "2026-11-16 11:30:00")
        self.assertEqual(ecowitt.date_utc("2026-11-16T11:30:00+03:00"), "2026-11-16 08:30:00")

    def test_unreadable_time_becomes_now(self):
        self.assertRegex(ecowitt.date_utc("yesterday"), r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")


class UrlTest(unittest.TestCase):
    def test_token(self):
        self.assertEqual(ecowitt.upload_url("  KW7N-4hpd-x2vt "), "https://api.nuasense.com/station/kw7n-4hpd-x2vt")
        for bad in ("", "short", "kw7n/4hpd/x2vt", "a" * 30):
            with self.assertRaises(ValueError):
                ecowitt.upload_url(bad)

    def test_form(self):
        self.assertEqual(ecowitt.encode_form({"dateutc": "2026-11-16 08:30:00", "a": "1"}),
                         "dateutc=2026-11-16%2008%3A30%3A00&a=1")


if __name__ == "__main__":
    unittest.main()
