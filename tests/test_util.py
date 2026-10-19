import tempfile
import unittest
from pathlib import Path

from glu_webdev_mcp.refs import Refs
from glu_webdev_mcp.util import clean_url, dashed, file_name, norm, notion_id_from_url, plain

PAGE = "3f169bb8-092d-8006-b102-ff79ad8ff7d6"


class UtilTest(unittest.TestCase):
    def test_dashed(self):
        self.assertEqual(dashed(PAGE.replace("-", "").upper()), PAGE)

    def test_plain(self):
        self.assertEqual(plain([["Hallo "], ["wereld", [["b"]]]]), "Hallo wereld")
        self.assertEqual(plain(None), "")

    def test_norm_keeps_length(self):
        s = "Één Café — Ünïcode"
        self.assertEqual(len(norm(s)), len(s))
        self.assertEqual(norm("Café"), "cafe")

    def test_notion_id_from_url(self):
        raw = PAGE.replace("-", "")
        self.assertEqual(notion_id_from_url(f"https://gluwebdev.notion.site/Berlins-Best-{raw}"), PAGE)
        self.assertEqual(notion_id_from_url(f"/{raw}"), PAGE)
        self.assertEqual(notion_id_from_url(f"https://www.notion.so/x?p={raw}&pm=s"), PAGE)
        # Het id van de pagina, niet van het blok in het #anker
        anchor = "a" * 32
        self.assertEqual(notion_id_from_url(f"https://www.notion.so/Pagina-{raw}#{anchor}"), PAGE)
        self.assertIsNone(notion_id_from_url("https://github.com/" + raw))

    def test_clean_url(self):
        self.assertEqual(clean_url("https://a.nl/p?utm_source=x&id=3&si=y"), "https://a.nl/p?id=3")
        safelink = ("https://eur02.safelinks.protection.outlook.com/?url=https%3A%2F%2Fglu.nl%2Fx"
                    "&data=abc&reserved=0")
        self.assertEqual(clean_url(safelink), "https://glu.nl/x")

    def test_file_name(self):
        self.assertEqual(file_name("attachment:5067e302:berlins-best.png"), "berlins-best.png")
        self.assertEqual(file_name("https://s3.example.com/a/b/foto%201.jpg?x=1"), "foto 1.jpg")


class RefsTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "refs.json"

    def test_short_and_resolve(self):
        refs = Refs(self.path)
        s = refs.short(PAGE)
        self.assertEqual(s, "ad8ff7d6")
        self.assertEqual(refs.resolve(s)["id"], PAGE)
        self.assertEqual(refs.short(PAGE), s)  # stabiel

    def test_collision_gets_longer_ref(self):
        refs = Refs(self.path)
        other = "11111111-2222-3333-4444-5555ad8ff7d6"  # zelfde laatste 8 tekens
        a, b = refs.short(PAGE), refs.short(other)
        self.assertNotEqual(a, b)
        self.assertEqual(refs.resolve(b)["id"], other)

    def test_url_refs_and_persistence(self):
        refs = Refs(self.path)
        s = refs.url("https://example.com/docs")
        img = refs.short(PAGE, src="attachment:x:foto.png")
        refs.save()
        again = Refs(self.path)  # bv. een tweede serverproces
        self.assertEqual(again.resolve(s)["url"], "https://example.com/docs")
        self.assertEqual(again.resolve(img)["src"], "attachment:x:foto.png")


if __name__ == "__main__":
    unittest.main()
