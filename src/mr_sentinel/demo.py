"""Run the public workflow with a deterministic local provider for CI and demos."""

import json

from .providers.base import T

SAMPLE = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -0,0 +1,2 @@
+DEFAULT_MODE = "preview"
+API_TOKEN = "synthetic-placeholder"
"""


class FixtureProvider:
    name = "fixture"

    async def complete(self, system: str, user: str, schema: type[T]) -> T:
        # The fixture uses schema names to exercise routing without a remote API.
        responses: dict[str, object] = {
            "SecurityFindings": {
                "findings": [
                    {
                        "path": "app.py",
                        "line": 2,
                        "severity": "high",
                        "explanation": "Move the credential-like constant into runtime configuration.",
                        "cwe": "CWE-798",
                    }
                ]
                if "API_TOKEN" in json.loads(user)["diff"]
                else []
            }
            if schema.__name__ == "SecurityFindings"
            else {},
            "TestAssessment": {"missing_tests": ["Test that configuration is read at runtime."]},
            "Summary": {"summary": "Update application configuration."},
            "Judgment": {"risk_score": 15, "rationale": "Fixture judgment before evidence floor."},
        }
        return schema.model_validate(responses[schema.__name__])


async def main() -> None:
    from .config import load_settings
    from .gitlab import render
    from .orchestrator import review

    settings = load_settings()
    result = await review(SAMPLE, "", FixtureProvider(), settings)
    print(render(result, settings.risk_threshold))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
