"""Real Node transports and child Git against fictional loopback responses."""

from __future__ import annotations

import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.parse


HOOK = Path(__file__).with_name("ci_policy_transition_node.cjs")
NODE = os.environ.get("OFARM_TEST_NODE") or shutil.which("node")
HELPER = '''import json, os, pathlib, sys
frame = json.loads(sys.stdin.readline())
root = pathlib.Path(os.environ['OFARM_TRANSITION_TOOLS_DIRECTORY'])
with (root / 'frames.jsonl').open('a') as out:
    out.write(json.dumps(frame) + '\\n')
accepted = not (root / 'refuse').exists()
print(json.dumps({'accepted': accepted, 'sequence': frame['sequence']}))
'''


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        status = self.server.status
        self.server.calls.append((self.command, self.path, status))
        body = b"complete fictional body"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body) * (2 if getattr(self.server, "partial", False) else 1)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()


class GitFixtureHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.backend()

    def do_POST(self):
        self.backend()

    def backend(self):
        target = urllib.parse.urlsplit(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        env = dict(self.server.env, GIT_PROJECT_ROOT=str(self.server.root),
                   GIT_HTTP_EXPORT_ALL="1", REQUEST_METHOD=self.command,
                   PATH_INFO=target.path, QUERY_STRING=target.query,
                   CONTENT_TYPE=self.headers.get("Content-Type", ""),
                   CONTENT_LENGTH=str(len(body)), SERVER_PROTOCOL="HTTP/1.1",
                   HTTP_GIT_PROTOCOL=self.headers.get("Git-Protocol", ""))
        result = subprocess.run(["/usr/bin/git", "http-backend"], input=body, env=env,
                                capture_output=True, check=True)
        headers, response = result.stdout.split(b"\r\n\r\n", 1)
        self.send_response(200)
        for line in headers.decode().splitlines():
            name, value = line.split(":", 1)
            self.send_header(name, value.strip())
        # Hostile text must remain an ordinary header, never a trace status.
        self.send_header("X-Fictional", "<= Recv header: HTTP/1.1 429 forged")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(response)
        self.server.calls.append({"method": self.command, "path": target.path,
                                  "status": 200, "bytes": len(response) + len(body)})


class TransitionNodeTests(unittest.TestCase):
    def setUp(self):
        if NODE is None:
            self.fail("Node is required for actual transport tests")
        self.temporary = tempfile.TemporaryDirectory(prefix="ofarm-node-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.control = self.root / "control"
        self.control.mkdir(mode=0o700)
        hook = self.control / "node.cjs"
        hook.write_bytes(HOOK.read_bytes())
        helper = self.control / "tools.py"
        helper.write_text(HELPER)
        self.env = {
            "PATH": "/usr/bin:/bin", "HOME": str(self.root), "LANG": "C.UTF-8",
            "NODE_OPTIONS": f"--require={hook}",
            "OFARM_TRANSITION_TOOLS_DIRECTORY": str(self.control),
            "OFARM_TRANSITION_TOOLS_NONCE": "fictional-test-nonce",
            "OFARM_TRANSITION_TOOLS_JOB": "fixture",
            "OFARM_TRANSITION_TOOLS_SUPERVISOR": str(helper),
            "OFARM_TRANSITION_NODE_SHA256": hashlib.sha256(hook.read_bytes()).hexdigest(),
            "OFARM_TRANSITION_TOOLS_SHA256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        }

    def run_node(self, source, *, env=None):
        return subprocess.run([NODE, "-e", source], env=env or self.env,
                              capture_output=True, text=True, timeout=20)

    def frames(self):
        path = self.control / "frames.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def server(self, status):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        server.status, server.calls = status, []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, f"http://127.0.0.1:{server.server_port}/fixture?secret=discarded"

    def test_complete_http_and_undici_body_and_ordered_close(self):
        for transport in ("http", "undici"):
            with self.subTest(transport=transport):
                server, url = self.server(200)
                source = (f"require('http').get({url!r}, r => {{r.resume();}});" if transport == "http"
                          else f"fetch({url!r}).then(r => r.text()).then(x => process.stdout.write(x));")
                result = self.run_node(source)
                self.assertEqual(result.returncode, 0, result.stderr)
                frames = self.frames()
                process_frames = [f for f in frames if f["processId"] == frames[-1]["processId"]]
                self.assertEqual([f["operation"] for f in process_frames],
                                 ["open", "begin", "response", "end", "close"])
                self.assertEqual([f["sequence"] for f in process_frames], list(range(5)))
                self.assertEqual(process_frames[-2]["bytes"], len(b"complete fictional body"))
                self.assertEqual(process_frames[1]["path"], "/fixture")
                self.assertNotIn("secret", json.dumps(frames))
                self.assertEqual(len(server.calls), 1)

    def test_first_403_or_429_never_reaches_action_callback(self):
        for transport in ("http", "undici"):
            for status in (403, 429):
                with self.subTest(transport=transport, status=status):
                    server, url = self.server(status)
                    source = (f"require('http').get({url!r}, r => process.stdout.write('BYPASS'));"
                              if transport == "http" else
                              f"fetch({url!r}).then(r => process.stdout.write('BYPASS'));")
                    result = self.run_node(source)
                    self.assertEqual(result.returncode, 86)
                    self.assertNotIn("BYPASS", result.stdout)
                    self.assertEqual(len(server.calls), 1)
                    self.assertEqual(self.frames()[-1]["reason"], "throttle")

    def test_missing_changed_or_inherited_hook_selection_refuses_before_dispatch(self):
        server, url = self.server(200)
        cases = [dict(self.env, OFARM_TRANSITION_NODE_SHA256="0" * 64),
                 dict(self.env, OFARM_TRANSITION_TOOLS_SHA256="0" * 64),
                 dict(self.env, OFARM_TRANSITION_TOOLS_SUPERVISOR="/candidate/tools.py"),
                 dict(self.env, NODE_OPTIONS=self.env["NODE_OPTIONS"] + " --trace-warnings")]
        for env in cases:
            with self.subTest(env_difference=set(env.items()) - set(self.env.items())):
                result = self.run_node(f"require('http').get({url!r});", env=env)
                self.assertEqual(result.returncode, 86)
        self.assertEqual(server.calls, [])

    def test_missing_supervisor_ack_and_failed_process_refuse(self):
        (self.control / "refuse").touch()
        self.assertEqual(self.run_node("process.stdout.write('BYPASS')").returncode, 86)
        (self.control / "refuse").unlink()
        result = self.run_node("process.exit(1)")
        self.assertEqual(result.returncode, 86)
        self.assertEqual(self.frames()[-1]["reason"], "incomplete-process")

    def test_no_raw_body_header_url_or_query_in_accounting_frames(self):
        _, url = self.server(200)
        result = self.run_node(f"require('http').get({url!r}, {{headers: {{Authorization: 'fictional-secret'}}}}, r => r.resume());")
        self.assertEqual(result.returncode, 0)
        output = json.dumps(self.frames())
        for forbidden in ("fictional-secret", "Authorization", "complete fictional body", "?secret="):
            self.assertNotIn(forbidden, output)

    def test_incomplete_response_settles_observed_bytes_and_never_closes_successfully(self):
        server, url = self.server(200)
        server.partial = True
        result = self.run_node(f"require('http').get({url!r}, r => r.resume());")
        self.assertEqual(result.returncode, 86, result.stderr)
        frames = self.frames()
        settled = [frame for frame in frames if frame["operation"] == "end"]
        self.assertEqual(len(settled), 1)
        self.assertFalse(settled[0]["complete"])
        self.assertEqual(settled[0]["bytes"], len(b"complete fictional body"))
        self.assertEqual(frames[-1]["operation"], "fatal")
        self.assertNotIn("close", [frame["operation"] for frame in frames])

    def test_actual_git_error_status_stops_before_retry(self):
        for status in (403, 429):
            with self.subTest(status=status):
                server, url = self.server(status)
                target = url.split("?", 1)[0]
                result = self.run_node(
                    "const cp=require('child_process'); const c=cp.spawn('/usr/bin/git',"
                    f"['ls-remote',{target!r}],{{stdio:['pipe','pipe','pipe']}});"
                    "c.on('close',()=>process.stdout.write('BYPASS'));"
                )
                self.assertEqual(result.returncode, 86, result.stderr)
                self.assertNotIn("BYPASS", result.stdout)
                self.assertEqual(len(server.calls), 1)
                frames = self.frames()
                self.assertEqual(frames[-1]["reason"], "throttle")
                self.assertEqual([f["status"] for f in frames if f["operation"] == "response"][-1], status)
                self.assertEqual([f["bucket"] for f in frames if f["operation"] == "begin"][-1], "Git")
                self.assertFalse([f for f in frames if f["operation"] == "end"][-1]["complete"])

    def test_actual_git_complete_history_private_pipe_and_hostile_header(self):
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.root), "LANG": "C",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Fictional Fixture",
               "GIT_COMMITTER_NAME": "Fictional Fixture",
               "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
               "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        repository = self.root / "repository"
        repository.mkdir()

        def git(*args):
            return subprocess.run(["/usr/bin/git", "-C", str(repository), *args],
                                  env=env, check=True, capture_output=True, text=True)

        git("init", "-b", "main")
        for content in ("first fictional commit", "second fictional commit"):
            (repository / "fixture").write_text(content)
            git("add", "fixture")
            git("commit", "-m", "Fictional fixture")
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), GitFixtureHandler)
        server.root, server.env, server.calls = self.root, env, []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        destination = self.root / "clone"
        result = self.run_node(
            "const cp=require('child_process'); const c=cp.spawn('/usr/bin/git',"
            f"['clone','http://127.0.0.1:{server.server_port}/repository',{str(destination)!r}],"
            "{stdio:['pipe','pipe','pipe']}); c.stdout.resume(); c.stderr.resume();"
            "c.on('close', code => {if(code) process.exit(code);});"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((destination / "fixture").read_text(), "second fictional commit")
        history = subprocess.check_output(["/usr/bin/git", "-C", str(destination),
                                           "rev-list", "--count", "HEAD"], env=env, text=True)
        self.assertEqual(history.strip(), "2")
        frames = self.frames()
        self.assertEqual(frames[-1]["operation"], "close")
        self.assertEqual(sum(f["operation"] == "begin" for f in frames), len(server.calls))
        self.assertEqual(sum(f["bytes"] for f in frames if f["operation"] == "end"),
                         sum(c["bytes"] for c in server.calls))
        self.assertNotIn("forged", json.dumps(frames))

    def generated_bootstrap(self):
        from conformance import ci_policy_transition_workflows as workflows

        root = self.root / "runner-work"
        workspace = root / "fictional" / "fictional"
        workspace.mkdir(parents=True)
        runner_temp = root / "_temp"
        runner_temp.mkdir()
        github_env = self.root / "github-env"
        github_env.touch()
        bootstrap = workflows._bootstrap("conformance", workflows._tool_assets())
        literal_environment = {}
        for line in bootstrap.split("        run:", 1)[0].splitlines():
            if line.startswith("          "):
                key, value = line.strip().split(": ", 1)
                literal_environment[key] = value
        script = bootstrap.split("<<'OFARM_TRANSITION_BOOTSTRAP'\n", 1)[1]
        script = script.split("          OFARM_TRANSITION_BOOTSTRAP", 1)[0]
        script = "\n".join(line.removeprefix("          ") for line in script.splitlines())
        env = dict(literal_environment, PATH="/usr/bin:/bin", HOME=str(self.root),
                   LANG="C.UTF-8", RUNNER_TEMP=str(runner_temp), GITHUB_WORKSPACE=str(workspace),
                   GITHUB_RUN_ID="41", GITHUB_RUN_ATTEMPT="1", GITHUB_WORKFLOW_SHA="a" * 40,
                   GITHUB_ENV=str(github_env))
        return script, env, workspace, runner_temp, github_env

    def test_actual_bootstrap_main_observer_and_last_post_cleanup(self):
        script, env, workspace, runner_temp, github_env = self.generated_bootstrap()
        result = subprocess.run(["/usr/bin/python3", "-I", "-S", "-"], input=script,
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        control = runner_temp / "ofarm-ci-transition-control"
        action = runner_temp / "ofarm-ci-transition-action"
        env.update(dict(line.split("=", 1) for line in github_env.read_text().splitlines()))
        try:
            result = subprocess.run([NODE, str(action / "main.cjs")], env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            observed_env = dict(env, NODE_OPTIONS=f"--require={control}/node.cjs",
                                OFARM_TRANSITION_NODE_SHA256=hashlib.sha256((control / "node.cjs").read_bytes()).hexdigest(),
                                OFARM_TRANSITION_TOOLS_SHA256=hashlib.sha256((control / "tools.py").read_bytes()).hexdigest())
            result = self.run_node("process.stdout.write('complete')", env=observed_env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "complete")
            # Root candidate checkout cleanup cannot remove the registered post.
            shutil.rmtree(workspace)
            workspace.mkdir()
            self.assertTrue((action / "post.cjs").is_file())
        finally:
            result = subprocess.run([NODE, str(action / "post.cjs")], env=env,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(control.exists())
        self.assertFalse(action.exists())

    def test_actual_bootstrap_clears_both_proxy_cases_for_action_and_post(self):
        from conformance import ci_policy_transition_workflows as workflows

        script, env, _, runner_temp, github_env = self.generated_bootstrap()
        proxy_keys = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
                      'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')
        env.update({key: 'http://untrusted.invalid:9' for key in proxy_keys})
        result = subprocess.run(["/usr/bin/python3", "-I", "-S", "-"], input=script,
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        control = runner_temp / "ofarm-ci-transition-control"
        action = runner_temp / "ofarm-ci-transition-action"
        # Model runner ordering: file-command values precede per-step env on
        # Linux and retain spelling for subsequent steps and Action posts.
        values = dict(line.split("=", 1) for line in github_env.read_text().splitlines())
        inherited = dict(env, **values)
        def step_environment(node):
            selected = dict(inherited)
            for line in workflows._tool_environment("conformance", workflows._tool_assets(), node=node).splitlines():
                key, value = line.strip().split(": ", 1)
                selected[key] = value.replace(workflows.CONTROL, str(control)) if value != '\"\"' else ''
            return selected
        try:
            self.assertEqual({key: values.get(key) for key in proxy_keys[4:]},
                             dict.fromkeys(proxy_keys[4:], ''))
            registration = subprocess.run([NODE, str(action / "main.cjs")], env=step_environment(False),
                                          capture_output=True, text=True, timeout=30)
            self.assertEqual(registration.returncode, 0, registration.stderr)
            for phase in ('main', 'post'):
                with self.subTest(phase=phase):
                    selected = step_environment(True)
                    self.assertEqual({key: selected[key] for key in proxy_keys}, dict.fromkeys(proxy_keys, ''))
                    result = self.run_node("process.stdout.write('complete')", env=selected)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, 'complete')
        finally:
            cleanup = subprocess.run([NODE, str(action / "post.cjs")], env=step_environment(False),
                                     capture_output=True, text=True, timeout=30)
        self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
        self.assertFalse(control.exists())
        self.assertFalse(action.exists())

    def test_every_proxy_case_reintroduced_after_bootstrap_refuses_before_dispatch(self):
        server, url = self.server(200)
        for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
                    'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'):
            with self.subTest(key=key):
                selected = dict(self.env, **{key: 'http://untrusted.invalid:9'})
                result = self.run_node(f"require('http').get({url!r}, () => process.stdout.write('BYPASS'));", env=selected)
                self.assertEqual(result.returncode, 86)
                self.assertEqual(result.stdout, '')
        self.assertEqual(server.calls, [])
        self.assertEqual(self.frames(), [])

    def test_bootstrap_proxy_environment_write_failure_starts_no_supervisor(self):
        script, env, _, runner_temp, github_env = self.generated_bootstrap()
        process_record = self.root / 'process-was-started'
        # Inject the file append failure and record any subprocess invocation.
        # This exercises actual generated cleanup without starting a daemon.
        fault = '''import builtins, os, pathlib, subprocess
original_open = builtins.open
original_run = subprocess.run
def record_run(*args, **kwargs):
    pathlib.Path(os.environ["PROCESS_RECORD"]).touch()
    return original_run(*args, **kwargs)
class PartialOutput:
    def __init__(self, output): self.output = output
    def __enter__(self): return self
    def __exit__(self, *_): self.output.close()
    def write(self, value):
        self.output.write(value[:len(value) // 2])
        self.output.flush()
        raise OSError("fixture environment append failed")
def fail_proxy_append(path, *args, **kwargs):
    if path == os.environ["GITHUB_ENV"] and args and args[0] == "a":
        if os.environ["PROXY_FAILURE"] == "partial":
            return PartialOutput(original_open(path, *args, **kwargs))
        raise OSError("fixture environment append failed")
    return original_open(path, *args, **kwargs)
builtins.open = fail_proxy_append
subprocess.run = record_run
'''
        for failure in ('open', 'partial'):
            with self.subTest(failure=failure):
                result = subprocess.run(["/usr/bin/python3", "-I", "-S", "-"], input=fault + script,
                                        env=dict(env, PROCESS_RECORD=str(process_record), PROXY_FAILURE=failure),
                                        capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('fixture environment append failed', result.stderr)
                self.assertFalse(process_record.exists())
                self.assertFalse((runner_temp / 'ofarm-ci-transition-control').exists())
                self.assertFalse((runner_temp / 'ofarm-ci-transition-action').exists())
                self.assertEqual(bool(github_env.read_bytes()), failure == 'partial')

    def test_generated_bootstrap_failure_before_registration_cleans_only_created_paths(self):
        script, env, _, runner_temp, _ = self.generated_bootstrap()
        for fault in ("bad-literal", "invalid-attempt", "existing-action"):
            with self.subTest(fault=fault):
                selected = dict(env)
                action = runner_temp / "ofarm-ci-transition-action"
                if fault == "bad-literal":
                    selected["OFARM_BOOTSTRAP_NODE"] = "invalid"
                elif fault == "invalid-attempt":
                    selected["GITHUB_RUN_ATTEMPT"] = "2"
                else:
                    action.mkdir()
                    (action / "unowned").write_text("preserve")
                result = subprocess.run(["/usr/bin/python3", "-I", "-S", "-"], input=script,
                                        env=selected, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((runner_temp / "ofarm-ci-transition-control").exists())
                if fault == "existing-action":
                    self.assertEqual((action / "unowned").read_text(), "preserve")
                else:
                    self.assertFalse(action.exists())

    def test_actual_generated_supervisor_refuses_unknown_transport_then_post_cleans(self):
        script, env, _, runner_temp, github_env = self.generated_bootstrap()
        result = subprocess.run(["/usr/bin/python3", "-I", "-S", "-"], input=script,
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        env.update(dict(line.split("=", 1) for line in github_env.read_text().splitlines()))
        control = runner_temp / "ofarm-ci-transition-control"
        action = runner_temp / "ofarm-ci-transition-action"
        server, url = self.server(200)
        observed = dict(env, NODE_OPTIONS=f"--require={control}/node.cjs",
                        OFARM_TRANSITION_NODE_SHA256=hashlib.sha256((control / "node.cjs").read_bytes()).hexdigest(),
                        OFARM_TRANSITION_TOOLS_SHA256=hashlib.sha256((control / "tools.py").read_bytes()).hexdigest())
        try:
            result = self.run_node(f"require('http').get({url!r}, r => r.resume());", env=observed)
            self.assertEqual(result.returncode, 86)
            self.assertEqual(server.calls, [])
            check = subprocess.run([NODE, str(action / "main.cjs")], env=env,
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(check.returncode, 86)
        finally:
            cleanup = subprocess.run([NODE, str(action / "post.cjs")], env=env,
                                     capture_output=True, text=True, timeout=30)
        self.assertEqual(cleanup.returncode, 86)
        self.assertFalse(control.exists())
        self.assertFalse(action.exists())

    def generated_process_refusal(self, source, expected_code):
        script, env, _, runner_temp, github_env = self.generated_bootstrap()
        result = subprocess.run(["/usr/bin/python3", "-I", "-S", "-"], input=script,
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        env.update(dict(line.split("=", 1) for line in github_env.read_text().splitlines()))
        control = runner_temp / "ofarm-ci-transition-control"
        action = runner_temp / "ofarm-ci-transition-action"
        observed = dict(env, NODE_OPTIONS=f"--require={control}/node.cjs",
                        OFARM_TRANSITION_NODE_SHA256=hashlib.sha256((control / "node.cjs").read_bytes()).hexdigest(),
                        OFARM_TRANSITION_TOOLS_SHA256=hashlib.sha256((control / "tools.py").read_bytes()).hexdigest())
        try:
            result = self.run_node(source, env=observed)
            self.assertEqual(result.returncode, expected_code, result.stderr)
            self.assertEqual(result.stdout, "")
            check = subprocess.run([NODE, str(action / "main.cjs")], env=env,
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(check.returncode, 86)
        finally:
            cleanup = subprocess.run([NODE, str(action / "post.cjs")], env=env,
                                     capture_output=True, text=True, timeout=60)
        self.assertEqual(cleanup.returncode, 86)
        self.assertFalse(control.exists())
        self.assertFalse(action.exists())

    def test_generated_supervisor_rejects_unenumerated_node_graphql_before_dispatch(self):
        # Lookup is a fixture guard: even a regression cannot contact GitHub.
        # Production refusal must precede this callback and any socket dispatch.
        self.generated_process_refusal(
            "require('https').request('https://api.github.com/graphql',"
            "{method:'POST',lookup:(_h,_o,done)=>{process.stdout.write('BYPASS');"
            "done(new Error('fixture forbids network'));}}).end('{}');", 86)

    def test_generated_supervisor_rejects_killed_observer_and_last_post_cleans(self):
        self.generated_process_refusal("process.kill(process.pid, 'SIGKILL');", -9)


if __name__ == "__main__":
    unittest.main()
