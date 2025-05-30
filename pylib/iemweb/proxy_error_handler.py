"""Handle Apache proxy errors."""

from http.client import responses as HTTP_RESPONSES

from pyiem.webutil import TELEMETRY, write_telemetry

from iemweb import error_log


def application(environ, start_response):
    """Handle Apache proxy errors."""
    status_code = int(environ.get("REDIRECT_STATUS", 200))
    error_log(environ, f"{status_code} {environ.get('REQUEST_URI')}")
    ip = environ.get("X-Forwarded-For", environ.get("REMOTE_ADDR"))
    if ip is not None:
        ip = ip.split(",")[0].strip()
    write_telemetry(
        TELEMETRY(
            0,
            status_code,
            ip,
            environ.get("REDIRECT_SCRIPT_URL"),
            environ.get("REQUEST_URI"),
            environ.get("HTTP_HOST"),
        )
    )

    status = f"{status_code} {HTTP_RESPONSES.get(status_code, 'Unknown')}"
    headers = [("Content-type", "text/plain")]
    start_response(status, headers)
    return [b"An error occurred, please try again later."]
