from __future__ import annotations

import unittest

from next_mcp.src.law_gateway import LawGateway


class FakeLawSearchApi:
    def __init__(self, payload):
        self.payload = payload

    def search_law(self, _query):
        return self.payload


class LawGatewayTests(unittest.TestCase):
    def test_resolve_law_family_returns_none_for_zero_score_match(self):
        gateway = LawGateway(
            api=FakeLawSearchApi(
                {
                    "LawSearch": {
                        "law": [
                            {
                                "법령ID": "999999",
                                "법령명한글": "표시ㆍ광고의 공정화에 관한 법률",
                            }
                        ]
                    }
                }
            )
        )

        self.assertIsNone(gateway.resolve_law_family("개인정보 보호법"))

    def test_resolve_law_family_prefers_exact_match(self):
        gateway = LawGateway(
            api=FakeLawSearchApi(
                {
                    "LawSearch": {
                        "law": [
                            {
                                "법령ID": "011357-S",
                                "법령명한글": "개인정보 보호법 시행령",
                            },
                            {
                                "법령ID": "011357",
                                "법령명한글": "개인정보 보호법",
                            },
                        ]
                    }
                }
            )
        )

        resolved = gateway.resolve_law_family("개인정보 보호법")

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.law_id, "011357")


if __name__ == "__main__":
    unittest.main()
