import re
import unittest

from glu_webdev_mcp.paging import paginate, section_of
from glu_webdev_mcp.refs import REFS
from glu_webdev_mcp.web import html_to_markdown

HTML = """<html><head><title>PHP Connect | Docs</title><script>var x = 1;</script></head><body>
<nav><a href="/a">Home</a> <a href="/b">HTML</a> <a href="/c">CSS</a></nav>
<div id="sidebar"><a href="/1">Een</a></div>
<div id="main">
  <h1>PHP Connect</h1>
  <p>Gebruik <code>mysqli</code> of <a href="/pdo">PDO</a> om te verbinden met een database.
     Hier staat genoeg tekst zodat dit blok als hoofdinhoud herkend wordt door de parser.
     En nog een zin, en nog een zin, zodat de drempel van driehonderd tekens gehaald wordt.</p>
  <ul><li>MySQLi</li><li>PDO</li></ul>
  <pre>$conn = new PDO($dsn);</pre>
  <p><a href="/x">Een</a> | <a href="/y">Twee</a> | <a href="/z">Drie</a></p>
</div>
<footer>© 2026</footer></body></html>"""


class HtmlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = html_to_markdown(HTML, "https://docs.example.com/php/connect")

    def test_main_content_only(self):
        self.assertTrue(self.md.startswith("# PHP Connect | Docs\n"))
        self.assertIn("# PHP Connect", self.md)
        for junk in ("Home", "var x", "© 2026", "Een"):
            self.assertNotIn(junk, self.md)

    def test_markup(self):
        self.assertIn("Gebruik `mysqli` of [PDO](@", self.md)
        self.assertIn("- MySQLi\n- PDO", self.md)
        self.assertIn("```\n$conn = new PDO($dsn);\n```", self.md)

    def test_links_become_refs(self):
        ref = re.search(r"\[PDO\]\(@([0-9a-f]+)\)", self.md).group(1)
        self.assertEqual(REFS.resolve(ref)["url"], "https://docs.example.com/pdo")


MD = "# Pagina\nintro\n## Opdracht\nmaak iets\n### Eisen\n- eis\n## Beoordeling\nrubric"


class PagingTest(unittest.TestCase):
    def test_short_page_unchanged(self):
        self.assertEqual(paginate(MD), MD)

    def test_section(self):
        self.assertEqual(section_of(MD, "opdracht"), "## Opdracht\nmaak iets\n### Eisen\n- eis")
        self.assertIn("Koppen:\n# Pagina", paginate(MD, section="bestaat niet"))

    def test_parts(self):
        long = "\n".join(f"## Kop {i}\n" + "tekst " * 40 for i in range(20))
        first = paginate(long, limit=1000)
        self.assertTrue(first.startswith("[deel 1/"))
        self.assertIn("[koppen → deel:", first)
        self.assertIn("[vervolg: part=2]", first)
        last_n = int(re.search(r"deel 1/(\d+)", first).group(1))
        last = paginate(long, part=last_n, limit=1000)
        self.assertIn("## Kop 19", last)
        self.assertNotIn("[vervolg", last)


if __name__ == "__main__":
    unittest.main()
