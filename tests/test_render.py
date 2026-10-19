import unittest

from glu_webdev_mcp.notion import Raw
from glu_webdev_mcp.refs import REFS
from glu_webdev_mcp.render import Renderer, parse_assignments


def uid(n: int) -> str:
    return f"00000000-0000-0000-0000-{n:012d}"


def rec(n: int, type_: str, **kw) -> dict:
    """Eén record in het formaat van de Notion API ({"value": {"value": .., "role": ..}})."""
    return {uid(n): {"spaceId": "s", "value": {"value": {"id": uid(n), "type": type_, **kw}, "role": "reader"}}}


def title(*segs) -> dict:
    return {"title": [list(s) if isinstance(s, tuple) else [s] for s in segs]}


def raw_of(*records) -> Raw:
    blocks = {}
    for r in records:
        blocks.update(r)
    raw = Raw()
    raw.merge({"block": blocks})
    return raw


class RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_of(
            rec(1, "page", properties=title("Opdracht"), content=[uid(n) for n in range(2, 16)]),
            rec(2, "header", properties=title("Intro")),
            rec(3, "text", properties=title("Lees ", ("de docs", [["a", "https://developer.mozilla.org/"]]),
                                            " en ", ("dit", [["b"]]), " en ", ("‣", [["p", uid(11)]]))),
            rec(4, "bulleted_list", properties=title("item"), content=[uid(20)]),
            rec(5, "numbered_list", properties=title("een")),
            rec(6, "numbered_list", properties=title("twee")),
            rec(7, "to_do", properties={**title("klaar"), "checked": [["Yes"]]}),
            rec(8, "code", properties={**title("echo 1;"), "language": [["PHP"]]}),
            rec(9, "table", content=[uid(21), uid(22)], format={"table_block_column_order": ["x", "y"]}),
            rec(10, "divider"),
            rec(11, "page", properties=title("Subpagina")),
            rec(12, "image", properties={"source": [["attachment:abc:foto.png"]]}),
            rec(13, "bookmark", properties={"link": [["https://github.com/glu/repo"]], **title("Repo")}),
            rec(14, "callout", properties=title("Let op"), format={"page_icon": "💡"}, content=[uid(23)]),
            rec(15, "alias", format={"alias_pointer": {"id": uid(24)}}),
            rec(20, "bulleted_list", properties=title("sub")),
            rec(21, "table_row", properties={"x": [["a"]], "y": [["b|c"]]}),
            rec(22, "table_row", properties={"x": [["1"]], "y": [["regel 1\nregel 2"]]}),
            rec(23, "text", properties=title("in de callout")),
            rec(24, "page", properties=title("Stage bij CSD")),
        )
        r = Renderer(cls.raw, uid(1))
        cls.title, cls.md = r.run()
        cls.links = r.links

    def test_title_and_heading(self):
        self.assertEqual(self.title, "Opdracht")
        self.assertTrue(self.md.startswith("# Opdracht\n## Intro"))

    def test_rich_text(self):
        self.assertIn("Lees [de docs](https://developer.mozilla.org/) en **dit** en [Subpagina](@", self.md)

    def test_lists(self):
        self.assertIn("- item\n  - sub", self.md)
        self.assertIn("1. een\n2. twee", self.md)
        self.assertIn("- [x] klaar", self.md)

    def test_code_and_table(self):
        self.assertIn("```php\necho 1;\n```", self.md)
        self.assertIn("|a|b\\|c|\n|-|-|\n|1|regel 1 / regel 2|", self.md)

    def test_media_callout_and_skips(self):
        self.assertIn("[img: foto.png](@", self.md)
        self.assertIn("[Repo](https://github.com/glu/repo)", self.md)
        self.assertIn("> 💡 Let op\n> in de callout", self.md)
        self.assertNotIn("---", self.md)

    def test_links_to_subpages(self):
        self.assertEqual(set(self.links), {uid(11), uid(24)})
        self.assertIn(f"[Stage bij CSD](@{REFS.short(uid(24))})", self.md)


class AssignmentsTest(unittest.TestCase):
    def test_parse_assignments(self):
        raw = raw_of(
            rec(1, "page", properties=title("Web Development"), content=[uid(2), uid(3), uid(4)]),
            rec(2, "column_list", content=[uid(10)]),
            rec(10, "column", content=[uid(11), uid(12), uid(13)]),
            rec(11, "text", properties=title("Leerjaar 1")),
            rec(12, "page", properties=title("3.1 - Module - Webshop (Front-end Statisch)")),
            rec(13, "page", properties=title("3.1 - Ontwikkelweek - CSS animaties")),
            rec(3, "header", properties=title("Stage")),
            rec(4, "alias", format={"alias_pointer": {"id": uid(20)}}),
            rec(20, "page", properties=title("Stage bij CSD")),
        )
        groups = parse_assignments(raw, uid(1))
        self.assertEqual([g["groep"] for g in groups], ["Leerjaar 1", "Stage"])
        module, week = groups[0]["items"]
        self.assertEqual((module["periode"], module["type"], module["naam"]),
                         ("3.1", "module", "Webshop (Front-end Statisch)"))
        self.assertEqual((week["type"], week["naam"]), ("ontwikkelweek", "CSS animaties"))
        self.assertEqual(groups[1]["items"][0]["id"], uid(20))


if __name__ == "__main__":
    unittest.main()
