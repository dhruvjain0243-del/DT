from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "streamlit_app.py"


def test_login_and_register_pages_render_without_exceptions():
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert not app.exception
    assert app.title[0].value == "Login"

    app.switch_page("app_pages/register.py").run()
    assert not app.exception
    assert app.title[0].value == "Register"


def test_dashboard_accepts_scanned_ticket_qr_for_exit():
    class FakeClient:
        exit_request = None

        def get(self, path):
            if path == "/api/availability":
                return []
            if path in {"/api/vehicles/mine", "/api/facilities"}:
                return []
            raise AssertionError(f"Unexpected GET {path}")

        def post(self, path, *, json):
            if path == "/api/parking/exit":
                self.exit_request = json
                return {
                    "ticket_id": json["ticket_id"],
                    "status": "COMPLETED",
                    "registration_number": "TEST12345",
                    "vehicle_type": "CAR",
                    "slot_id": 1,
                    "slot_code": "A-1",
                    "entry_time": "2026-09-24T10:00:00Z",
                    "exit_time": "2026-09-24T11:00:00Z",
                    "duration_minutes": 60,
                    "message": "Vehicle exit recorded successfully",
                }
            raise AssertionError(f"Unexpected POST {path}")

    fake_client = FakeClient()
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.session_state["access_token"] = "test-access-token"
    app.session_state["refresh_token"] = "test-refresh-token"
    app.session_state["user"] = {"full_name": "Test Driver", "role": "STUDENT"}
    with patch("frontend.components.auth.get_client", return_value=fake_client):
        app.run()
        assert not app.exception
        app.text_input(key="exit_ticket_id").set_value("PW-TESTTICKET")
        app.text_input(key="exit_qr_token").set_value("signed-ticket-qr-token-value").run()
        app.button(key="qr_exit_submit").click().run()

    assert not app.exception
    assert fake_client.exit_request == {
        "ticket_id": "PW-TESTTICKET",
        "qr_token": "signed-ticket-qr-token-value",
    }
    assert any("Vehicle exit recorded successfully" in item.value for item in app.success)
