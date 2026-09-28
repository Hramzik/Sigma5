import unittest
from unittest.mock import patch

from waifu_client import parse_images, parse_tags, _request_json


class WaifuClientTests(unittest.TestCase):
    def test_parse_images_reads_url_fields(self):
        images = parse_images({"items": [
            {"id": 42, "urls": {"full": "https://cdn.test/full.jpg", "small": "https://cdn.test/preview.jpg"}},
            {"id": 43, "url": "https://cdn.test/other.jpg"},
            {"id": 44},
        ]})
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0].image_id, "42")
        self.assertEqual(images[0].image_url, "https://cdn.test/full.jpg")
        self.assertEqual(images[0].preview_url, "https://cdn.test/preview.jpg")
        self.assertEqual(images[1].preview_url, images[1].image_url)

    @patch("waifu_client.urllib.request.urlopen")
    def test_sfw_and_nsfw_modes_are_sent_as_query_parameters(self, urlopen):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"items": []}'

        urlopen.return_value = Response()
        _request_json(False)
        sfw_request = urlopen.call_args.args[0]
        self.assertIn("IsNsfw=False", sfw_request.full_url)
        self.assertNotIn("IncludedTags", sfw_request.full_url)
        _request_json(True, "waifu")
        nsfw_request = urlopen.call_args.args[0]
        self.assertIn("IsNsfw=True", nsfw_request.full_url)
        self.assertIn("IncludedTags=waifu", nsfw_request.full_url)

    def test_parse_tags_returns_names_and_slugs(self):
        tags = parse_tags({"items": [
            {"name": "Waifu", "slug": "waifu"},
            {"slug": "maid"},
            {"name": "Missing slug"},
        ]})
        self.assertEqual(tags, [("Waifu", "waifu"), ("maid", "maid")])


if __name__ == "__main__":
    unittest.main()
