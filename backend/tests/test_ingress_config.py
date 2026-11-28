"""Ingress (nginx) configuration guards.

These tests assert the shipped reverse-proxy configuration actually applies the
controls documented in docs/PUBLIC-EXPOSURE-HARDENING.md: perimeter rate limits,
connection limits, 429 rejection, security headers and trusted proxy headers.
They parse the files; they do not start nginx.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


class IngressRateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limits = (FRONTEND / "nginx-limits.conf").read_text(encoding="utf-8")
        cls.server = (FRONTEND / "nginx.conf").read_text(encoding="utf-8")

    def test_zones_declared_with_documented_rates(self):
        self.assertIn("limit_req_zone $binary_remote_addr zone=market_mind_api:10m rate=30r/m", self.limits)
        self.assertIn("limit_req_zone $binary_remote_addr zone=market_mind_static:10m rate=120r/m", self.limits)
        self.assertIn("limit_conn_zone $binary_remote_addr zone=market_mind_conn:10m", self.limits)

    def test_excess_traffic_returns_429(self):
        self.assertIn("limit_req_status 429", self.limits)
        self.assertIn("limit_conn_status 429", self.limits)
        self.assertNotIn("limit_req_status 503", self.limits)
        self.assertNotIn("limit_conn_status 503", self.limits)

    def test_server_tokens_disabled(self):
        self.assertIn("server_tokens off", self.limits)

    def test_api_and_static_locations_apply_limits(self):
        api_block = re.search(r"location /api/ \{(.*?)\n    \}", self.server, re.S)
        self.assertIsNotNone(api_block, "location /api/ block not found")
        self.assertIn("limit_req zone=market_mind_api burst=20 nodelay", api_block.group(1))

        static_block = re.search(r"location / \{(.*?)\n    \}", self.server, re.S)
        self.assertIsNotNone(static_block, "location / block not found")
        self.assertIn("limit_req zone=market_mind_static burst=40 nodelay", static_block.group(1))

    def test_connection_limit_applied_to_server(self):
        self.assertIn("limit_conn market_mind_conn 20", self.server)

    def test_trusted_proxy_headers_are_forwarded(self):
        for header in ("Host $host", "X-Real-IP $remote_addr",
                       "X-Forwarded-For $proxy_add_x_forwarded_for",
                       "X-Forwarded-Proto $mm_forwarded_proto"):
            self.assertIn(f"proxy_set_header {header}", self.server)

    def test_security_headers_and_csp_present(self):
        self.assertIn("add_header X-Content-Type-Options nosniff always", self.server)
        self.assertIn("add_header X-Frame-Options DENY always", self.server)
        self.assertIn("add_header Referrer-Policy strict-origin-when-cross-origin always", self.server)
        csp = re.search(r'add_header Content-Security-Policy "(.*?)" always', self.server, re.S)
        self.assertIsNotNone(csp, "Content-Security-Policy header missing")
        policy = csp.group(1)
        for directive in ("default-src 'self'", "script-src 'self'",
                          "frame-ancestors 'none'", "object-src 'none'"):
            self.assertIn(directive, policy)
        self.assertNotIn("script-src 'unsafe-inline'", policy)

    def test_healthz_not_rate_limited(self):
        health = re.search(r"location = /healthz \{(.*?)\n    \}", self.server, re.S)
        self.assertIsNotNone(health)
        self.assertNotIn("limit_req", health.group(1))

    def test_backend_probes_are_exempt_from_perimeter_limits(self):
        for probe in ("/api/ready", "/api/health"):
            block = re.search(
                r"location = " + re.escape(probe) + r" \{(.*?)\n    \}", self.server, re.S
            )
            self.assertIsNotNone(block, f"{probe} exact location missing")
            self.assertNotIn("limit_req", block.group(1))
            self.assertIn(f"proxy_pass http://backend:8000{probe}", block.group(1))

    def test_container_copies_limits_before_default_server(self):
        dockerfile = (FRONTEND / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY nginx-limits.conf /etc/nginx/conf.d/00-ingress-limits.conf", dockerfile)
        self.assertIn("COPY nginx.conf /etc/nginx/conf.d/default.conf", dockerfile)
        self.assertLess(
            dockerfile.index("00-ingress-limits.conf"),
            dockerfile.index("/etc/nginx/conf.d/default.conf"),
            "limits file must be copied so that it sorts before default.conf",
        )

    def test_plaintext_http_redirects_to_https_in_tls_template(self):
        tls_example = (ROOT / "deploy/tls/nginx-tls.conf.example").read_text(encoding="utf-8")
        self.assertIn("return 301 https://", tls_example)
        self.assertIn("Strict-Transport-Security", tls_example)

    def test_tls_chain_preserves_the_outer_forwarded_proto(self):
        tls_example = (ROOT / "deploy/tls/nginx-tls.conf.example").read_text(encoding="utf-8")
        self.assertIn("proxy_set_header X-Forwarded-Proto https", tls_example)
        self.assertIn("map $http_x_forwarded_proto $mm_forwarded_proto", self.limits)
        self.assertNotIn("proxy_set_header X-Forwarded-Proto $scheme", self.server)
        self.assertEqual(self.server.count("X-Forwarded-Proto $mm_forwarded_proto"), 3)

    def test_compose_keeps_backend_off_host_and_all_services_unprivileged(self):
        import yaml
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
        services = compose["services"]
        self.assertNotIn("ports", services["backend"])
        self.assertNotIn("ports", services["agent-supervisor"])
        for name, service in services.items():
            self.assertEqual(service.get("security_opt"), ["no-new-privileges:true"], name)
            self.assertEqual(service.get("cap_drop"), ["ALL"], name)
            for port in service.get("ports", []):
                self.assertTrue(str(port).startswith("127.0.0.1:"), (name, port))

    def test_nginx_accepts_the_configuration_when_available(self):
        nginx = shutil.which("nginx")
        if not nginx:
            self.skipTest("nginx binary not installed")
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            (prefix / "conf.d").mkdir()
            (prefix / "mime.types").write_text("", encoding="utf-8")
            (prefix / "logs").mkdir()
            (prefix / "conf.d/00-ingress-limits.conf").write_text(self.limits, encoding="utf-8")
            server = self.server.replace("http://backend:8000", "http://127.0.0.1:8000")
            (prefix / "conf.d/default.conf").write_text(server, encoding="utf-8")
            (prefix / "nginx.conf").write_text(
                "worker_processes 1;\n"
                f"pid {prefix}/nginx.pid;\n"
                "error_log stderr;\n"
                "events { worker_connections 64; }\n"
                "http {\n"
                f"    access_log off;\n    client_body_temp_path {prefix}/body;\n"
                f"    proxy_temp_path {prefix}/proxy;\n    fastcgi_temp_path {prefix}/fcgi;\n"
                f"    uwsgi_temp_path {prefix}/uwsgi;\n    scgi_temp_path {prefix}/scgi;\n"
                "    include conf.d/*.conf;\n"
                "}\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [nginx, "-t", "-p", str(prefix), "-c", str(prefix / "nginx.conf")],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
