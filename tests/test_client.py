import io
import json
import os
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import nuasense
from nuasense import client as mod


class FakeResponse(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body.encode("utf-8"))
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def answering(*replies):
    """Patch urlopen; each reply is (status, body) or an exception. Records the requests."""
    calls = []
    queue = list(replies)

    def fake(req, timeout=None):
        calls.append(req)
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        text = body if isinstance(body, str) else json.dumps(body)
        if status >= 400:
            raise HTTPError(req.full_url, status, "error", {"Retry-After": "30"}, io.BytesIO(text.encode()))
        return FakeResponse(text, status)

    return mock.patch.object(mod, "urlopen", side_effect=fake), calls


def query(req):
    return {k: v[0] for k, v in parse_qs(urlparse(req.full_url).query).items()}


class SendReadingTest(unittest.TestCase):
    def test_posts_the_ecowitt_form_without_a_key(self):
        patch, calls = answering((200, "OK"))
        with patch:
            out = nuasense.send_reading("abcd-efgh-ijkl", device_id="shed", temperature=20, rain_total=1.5)
        req = calls[0]
        self.assertEqual(req.full_url, "https://api.nuasense.com/station/abcd-efgh-ijkl")
        self.assertEqual(req.get_method(), "POST")
        self.assertIsNone(req.get_header("Authorization"))
        self.assertEqual(req.get_header("X-nuasense-client"), "python/" + nuasense.__version__)
        form = parse_qs(req.data.decode())
        self.assertEqual(form["tempf"], ["68"])
        self.assertEqual(form["PASSKEY"], [nuasense.ecowitt.passkey_for("shed")])
        self.assertEqual(form["stationtype"], ["python_" + nuasense.__version__])
        self.assertTrue(out["sent"])

    def test_unknown_token_is_explained(self):
        patch, _ = answering((404, "not found"))
        with patch, self.assertRaisesRegex(nuasense.NuaSenseError, "does not know this station token"):
            nuasense.send_reading("abcd-efgh-ijkl", temperature=1)

    def test_nothing_to_send_is_refused_before_any_call(self):
        patch, calls = answering()
        with patch, self.assertRaisesRegex(ValueError, "at least one value"):
            nuasense.send_reading("abcd-efgh-ijkl")
        self.assertEqual(calls, [])

    def test_offline_is_a_nuasense_error(self):
        patch, _ = answering(URLError("no route"))
        with patch, self.assertRaisesRegex(nuasense.NuaSenseError, "Could not reach"):
            nuasense.send_reading("abcd-efgh-ijkl", temperature=1)


class ClientTest(unittest.TestCase):
    def test_key_from_the_environment(self):
        with mock.patch.dict(os.environ, {"NUASENSE_API_KEY": " nsk_test "}):
            self.assertEqual(nuasense.Client().api_key, "nsk_test")
        self.assertNotIn("nsk", repr(nuasense.Client("nsk_secret")))

    def test_first_look(self):
        patch, calls = answering((200, {"tonight": {"frost": "none"}}))
        with patch:
            out = nuasense.Client("k").first_look("st-1")
        self.assertEqual(out["tonight"]["frost"], "none")
        self.assertTrue(calls[0].full_url.startswith("https://api.nuasense.com/api/nuasense/v1/ingest/first-look?"))
        self.assertEqual(query(calls[0]), {"station_id": "st-1"})
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer k")

    def test_dataset_params_and_rows(self):
        body = {"dataset": "market/prices", "rows": [{"price": 52}]}
        patch, calls = answering((200, body), (200, body))
        ns = nuasense.Client("k")
        with patch:
            ns.dataset("market/prices", start="-14d", every="1d", oldest_first=True, county="nakuru", end=None)
            rows = ns.rows("/market/prices")
        self.assertEqual(urlparse(calls[0].full_url).path, "/api/nuasense/v1/market/prices")
        self.assertEqual(query(calls[0]), {"start": "-14d", "limit": "50", "every": "1d", "agg": "mean",
                                           "order": "asc", "county": "nakuru"})
        self.assertEqual(rows, [{"price": 52}])

    def test_analysis_path(self):
        patch, calls = answering((200, {"ok": True}))
        with patch:
            nuasense.Client("k").analysis("/fertilizer/rank", county="nakuru")
        self.assertEqual(urlparse(calls[0].full_url).path, "/api/partner/v1/market/fertilizer/rank")

    def test_refusal_carries_status_body_and_hint(self):
        patch, _ = answering((429, {"error": "daily unit budget spent"}))
        with patch, self.assertRaises(nuasense.NuaSenseError) as caught:
            nuasense.Client("k").catalog()
        err = caught.exception
        self.assertEqual(err.status, 429)
        self.assertEqual(err.retry_after, "30")
        self.assertIn("daily unit budget spent", str(err))
        self.assertIn("Retry-After", str(err))

    def test_key_never_leaves_for_another_host(self):
        patch, calls = answering()
        ns = nuasense.Client("k")
        with patch:
            for url in ("https://evil.example/x", "http://api.nuasense.com/api/nuasense/v1/catalog",
                        "https://api.nuasense.com.evil.example/x"):
                with self.assertRaisesRegex(ValueError, "only talks to"):
                    ns.get(url)
        self.assertEqual(calls, [])

    def test_redirects_are_answers_not_followed(self):
        self.assertIsNone(mod._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.example/"))
        patch, _ = answering((301, ""))
        with patch, self.assertRaises(nuasense.NuaSenseError) as caught:
            nuasense.Client("k").catalog()
        self.assertEqual(caught.exception.status, 301)

    def test_missing_key_says_where_to_get_one(self):
        patch, _ = answering((401, {"error": "missing key"}))
        with mock.patch.dict(os.environ, {}, clear=True), patch, \
                self.assertRaisesRegex(nuasense.NuaSenseError, "platform.nuasense.com"):
            nuasense.Client().stations()


if __name__ == "__main__":
    unittest.main()
