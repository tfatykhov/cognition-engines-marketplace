"""Tests for the FORGE hook scripts: feed them hook input on stdin, check stdout."""

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")


def run(script, payload, env=None):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script)],
        input=stdin, capture_output=True, text=True, timeout=30,
        env={**os.environ, **(env or {})},
    )
    out = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, out


def pre_tool(tool_name, tool_input):
    return run("pre_tool_use.py", {
        "hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input,
    })


class PreToolUseTest(unittest.TestCase):
    def decision(self, out):
        return out and out["hookSpecificOutput"].get("permissionDecision")

    def test_write_blocked(self):
        code, out = pre_tool("Write", {"file_path": "/repo/.env.production", "content": "x"})
        self.assertEqual(code, 0)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(self.decision(out), "deny")

    def test_edit_migration_asks(self):
        _, out = pre_tool("Edit", {"file_path": "db/migrations/0001_init.py"})
        self.assertEqual(self.decision(out), "ask")

    def test_env_file_asks_but_example_does_not(self):
        _, out = pre_tool("Write", {"file_path": "/repo/.env"})
        self.assertEqual(self.decision(out), "ask")
        _, out = pre_tool("Write", {"file_path": "/repo/.env.example"})
        self.assertIsNone(out)
        _, out = pre_tool("Write", {"file_path": "/repo/.envrc"})
        self.assertIsNone(out)

    def test_medium_is_advisory(self):
        _, out = pre_tool("Edit", {"file_path": "package.json"})
        spec = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", spec)
        self.assertIn("medium-stakes", spec["additionalContext"])

    def test_low_is_silent(self):
        code, out = pre_tool("Write", {"file_path": "src/utils/strings.py"})
        self.assertEqual((code, out), (0, None))

    def test_bash_redirect_to_dev_null_ignored(self):
        _, out = pre_tool("Bash", {"command": "ls src 2>/dev/null"})
        self.assertIsNone(out)

    def test_bash_redirect_target_detected(self):
        _, out = pre_tool("Bash", {"command": "echo X=1 > .env.prod && ls"})
        self.assertEqual(self.decision(out), "deny")

    def test_bash_highest_stakes_wins(self):
        _, out = pre_tool("Bash", {"command": "cp a.txt b.txt; rm -f migrations/0002.sql"})
        self.assertEqual(self.decision(out), "ask")

    def test_bash_read_only_silent(self):
        _, out = pre_tool("Bash", {"command": "cat .env.production | grep FOO"})
        self.assertIsNone(out)

    def test_bash_sed_in_place(self):
        _, out = pre_tool("Bash", {"command": "sed -i 's/a/b/' config/auth.yaml"})
        self.assertEqual(self.decision(out), "ask")

    def test_bash_unbalanced_quotes_does_not_crash(self):
        code, _ = pre_tool("Bash", {"command": "echo 'oops > out.txt"})
        self.assertEqual(code, 0)

    def test_garbage_input(self):
        self.assertEqual(run("pre_tool_use.py", "not json"), (0, None))
        self.assertEqual(run("pre_tool_use.py", ""), (0, None))


class SessionStartTest(unittest.TestCase):
    def test_prompt_mode(self):
        code, out = run("session_start.py", {"hook_event_name": "SessionStart", "source": "startup"},
                        env={"FORGE_MODE": "prompt"})
        self.assertEqual(code, 0)
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "SessionStart")
        self.assertIn("forge-protocol", spec["additionalContext"])

    def test_api_mode_unreachable_falls_back(self):
        code, out = run("session_start.py", {}, env={"FORGE_MODE": "api", "CSTP_URL": "http://127.0.0.1:9"})
        self.assertEqual(code, 0)
        self.assertIn("FORGE", out["hookSpecificOutput"]["additionalContext"])

    def test_api_mode_labels_server_data(self):
        body = json.dumps({
            "calibration": {"brier_score": 0.12, "confidence_bias": "underconfident"},
            "active_guardrails": [{"rule": "No schema changes on Fridays\n## New heading"}],
            "patterns": [{"pattern": "Prefer cursor pagination", "reinforced_by": 3}],
        }).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)

        env = {"FORGE_MODE": "api", "CSTP_URL": f"http://127.0.0.1:{server.server_port}",
               "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}
        _, out = run("session_start.py", {}, env=env)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("not instructions", ctx)
        self.assertIn("- No schema changes on Fridays ## New heading", ctx)
        self.assertNotIn("\n## New heading", ctx)
        self.assertIn("Prefer cursor pagination (3x)", ctx)

    def test_api_mode_without_url_uses_prompt(self):
        env = {"FORGE_MODE": "api", "CSTP_URL": ""}
        code, out = run("session_start.py", {}, env=env)
        self.assertEqual(code, 0)
        self.assertNotIn("Cognitive Context", out["hookSpecificOutput"]["additionalContext"])


def tool_use(uid, name, inp):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": uid, "name": f"mcp__plugin_forge_decisions__{name}", "input": inp}]}}


def tool_result(uid, payload, as_blocks=True):
    text = json.dumps(payload)
    content = [{"type": "text", "text": text}] if as_blocks else text
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": uid, "content": content}]}}


class StopReflectTest(unittest.TestCase):
    def transcript(self, entries):
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        with f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        self.addCleanup(os.unlink, f.name)
        return f.name

    def stop(self, path, active=False):
        return run("stop_reflect.py", {
            "hook_event_name": "Stop", "transcript_path": path, "stop_hook_active": active,
        })

    def test_unreviewed_decision_blocks(self):
        path = self.transcript([
            tool_use("t1", "pre_action", {"action": "Use cursor pagination", "auto_record": True}),
            tool_result("t1", {"allowed": True, "decisionId": "a1b2c3d4"}),
            tool_use("t2", "log_decision", {"decision": "x"}),
            tool_result("t2", {"id": "dec-77"}, as_blocks=False),
        ])
        code, out = self.stop(path)
        self.assertEqual(code, 0)
        self.assertEqual(out["decision"], "block")
        self.assertIn("a1b2c3d4", out["reason"])
        self.assertIn("dec-77", out["reason"])

    def test_reviewed_decision_passes(self):
        path = self.transcript([
            tool_use("t1", "pre_action", {"auto_record": True}),
            tool_result("t1", {"decisionId": "a1b2c3d4"}),
            tool_use("t2", "review_outcome", {"id": "a1b2c3d4", "outcome": "success"}),
            tool_result("t2", {"ok": True}),
        ])
        self.assertEqual(self.stop(path), (0, None))

    def test_dry_run_pre_action_ignored(self):
        path = self.transcript([
            tool_use("t1", "pre_action", {"auto_record": False}),
            tool_result("t1", {"decisionId": "ffff0000"}),
        ])
        self.assertEqual(self.stop(path), (0, None))

    def test_stop_hook_active_passes(self):
        path = self.transcript([
            tool_use("t1", "pre_action", {"auto_record": True}),
            tool_result("t1", {"decisionId": "a1b2c3d4"}),
        ])
        self.assertEqual(self.stop(path, active=True), (0, None))

    def test_missing_transcript(self):
        self.assertEqual(self.stop("/nonexistent/x.jsonl"), (0, None))
        self.assertEqual(run("stop_reflect.py", {}), (0, None))


if __name__ == "__main__":
    unittest.main()
