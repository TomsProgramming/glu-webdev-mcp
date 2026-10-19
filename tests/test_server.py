import unittest

from glu_webdev_mcp import __version__, server, tools


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self._send = server.send
        server.send = self.sent.append

    def tearDown(self):
        server.send = self._send

    def request(self, method, params=None, id_=1):
        server.handle({"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})
        return self.sent[-1]

    def test_initialize(self):
        res = self.request("initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertEqual(res["protocolVersion"], "2025-06-18")
        self.assertEqual(res["serverInfo"], {"name": "glu-webdev", "version": __version__})
        self.assertIn("tools", res["capabilities"])

    def test_notifications_get_no_answer(self):
        server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(self.sent, [])

    def test_tools_list(self):
        names = [t["name"] for t in self.request("tools/list")["result"]["tools"]]
        self.assertEqual(names, ["list_assignments", "read", "search"])

    def test_unknown_method(self):
        self.assertEqual(self.request("foo/bar")["error"]["code"], -32601)

    def test_tool_errors_are_reported_not_raised(self):
        res = self.request("tools/call", {"name": "bestaat_niet", "arguments": {}})["result"]
        self.assertTrue(res["isError"])

        def boom(**_):
            raise LookupError("kapot")

        original = tools.HANDLERS["search"]
        tools.HANDLERS["search"] = boom
        try:
            res = self.request("tools/call", {"name": "search", "arguments": {"query": "x"}})["result"]
        finally:
            tools.HANDLERS["search"] = original
        self.assertTrue(res["isError"])
        self.assertEqual(res["content"][0]["text"], "Fout: kapot")

    def test_tool_definitions_stay_small(self):
        import json
        size = len(json.dumps(tools.TOOLS))
        self.assertLess(size, 2000, "tooldefinities kosten in elk gesprek tokens")


if __name__ == "__main__":
    unittest.main()
