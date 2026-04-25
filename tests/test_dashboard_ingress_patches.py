"""Regression tests for Home Assistant Ingress dashboard routing patches."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN_SH = ROOT / "hermes_agent" / "run.sh"
NGINX_TEMPLATE = ROOT / "hermes_agent" / "nginx.conf.tpl"


class DashboardIngressPatchTests(unittest.TestCase):
    def test_dashboard_router_uses_runtime_base_as_basename(self) -> None:
        """React Router must generate /dashboard/* links behind HA Ingress.

        The add-on serves the SPA below /dashboard/. API/assets were already
        base-aware, but BrowserRouter without a basename still emitted top-level
        links like /logs. Those work for in-app navigation but 404 on frame
        reload because nginx only proxies dashboard traffic below /dashboard/.
        """
        run_sh = RUN_SH.read_text()

        self.assertIn("HA-ADDON-ROUTER-BASENAME-PATCHED", run_sh)
        self.assertIn('import { BASE } from "@/lib/api";', run_sh)
        self.assertIn('basename={BASE || "/"}', run_sh)

    def test_nginx_keeps_dashboard_deep_links_under_dashboard_prefix(self) -> None:
        """Direct /dashboard/<route> reloads must keep proxying to the SPA."""
        nginx_conf = NGINX_TEMPLATE.read_text()

        self.assertIn("location = /dashboard { return 302 /dashboard/; }", nginx_conf)
        self.assertIn("location /dashboard/api/", nginx_conf)
        self.assertIn("location /dashboard/", nginx_conf)
        self.assertIn("proxy_pass http://hermes_dashboard/;", nginx_conf)

    def test_direct_port_dashboard_api_accepts_spa_session_header(self) -> None:
        """Direct-port nginx guard must match the SPA's current token header.

        The React dashboard sends X-Hermes-Session-Token, not Authorization.
        Direct LAN ports turn basic auth off for /dashboard/api/* and rely on
        nginx to verify the SPA token before proxying, so checking only
        $http_authorization rejects the legitimate dashboard with 401.
        """
        nginx_ports = (ROOT / "hermes_agent" / "nginx-ports.conf.tpl").read_text()

        self.assertIn("$http_x_hermes_session_token", nginx_ports)
        self.assertIn("map_hash_bucket_size 128;", nginx_ports)
        self.assertIn("$dashboard_token_ok", nginx_ports)
        self.assertIn("~^%%DASHBOARD_TOKEN%%\\|", nginx_ports)
        self.assertIn("~^\\|Bearer\\ %%DASHBOARD_TOKEN%%$", nginx_ports)
        self.assertNotIn("$http_authorization != \"Bearer %%DASHBOARD_TOKEN%%\"", nginx_ports)


if __name__ == "__main__":
    unittest.main()
