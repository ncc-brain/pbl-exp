"""
Minimal Philips Hue API v2 client.

Endpoints used:
- GET  /clip/v2/resource/bridge   -> verify bridge/API connection
- POST /clip/v2/resource/device   -> start device discovery
- GET  /clip/v2/resource/light    -> list lights
"""

from __future__ import annotations

import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APPLICATION_KEY = "193x0n5CVFz5E1FaYdaMFlZoFzf78vx5fI0klDEa"
BRIDGE_IP = "192.168.0.100"
VERIFY_TLS = False
REQUEST_TIMEOUT_SECONDS = 10


class HueBridgeError(RuntimeError):
    """Raised when the Hue Bridge cannot be contacted or rejects a request."""


class HueBridgeClient:
    def __init__(
        self,
        bridge_ip: str = BRIDGE_IP,
        application_key: str = APPLICATION_KEY,
        verify_tls: bool = VERIFY_TLS,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        # Supports either "192.168.0.100" or "https://192.168.0.100"
        bridge_ip = bridge_ip.removeprefix("https://").removeprefix("http://")
        self.base_url = f"https://{bridge_ip.rstrip('/')}/clip/v2"
        self.application_key = application_key
        self.timeout = timeout

        # Hue Bridge certificates are usually not publicly trusted.
        self.ssl_context = (
            ssl.create_default_context()
            if verify_tls
            else ssl._create_unverified_context()
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one request to the Hue v2 API and return its JSON response."""

        url = f"{self.base_url}/{path.lstrip('/')}"

        headers = {
            "hue-application-key": self.application_key,
            "Accept": "application/json",
        }

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            url,
            data=data,
            headers=headers,
            method=method.upper(),
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
                context=self.ssl_context,
            ) as response:
                body = response.read().decode("utf-8")

        except HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise HueBridgeError(
                f"Hue API returned HTTP {error.code}: {error_body}"
            ) from error

        except URLError as error:
            raise HueBridgeError(
                f"Could not reach Hue Bridge at {self.base_url}: {error.reason}"
            ) from error

        except TimeoutError as error:
            raise HueBridgeError(
                f"Timed out while connecting to Hue Bridge at {self.base_url}"
            ) from error

        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError as error:
            raise HueBridgeError(
                f"Hue Bridge returned invalid JSON: {body!r}"
            ) from error

    # 1) Connect / verify connectivity

    def get_bridge(self) -> dict[str, Any]:
        """
        Request the bridge resource.

        If this returns successfully, the bridge is reachable and the
        application key was accepted.
        """
        return self._request("GET", "/resource/bridge")

    def is_connected(self) -> bool:
        """Return True only if the bridge is reachable and accepts the key."""
        try:
            self.get_bridge()
            return True
        except HueBridgeError:
            return False

    # 2) Discover new devices/lights

    def start_device_discovery(self) -> dict[str, Any]:
        """
        Tell the bridge to begin searching for new Zigbee devices.

        Ensure the new bulbs are powered on. Bulbs paired to another bridge
        generally need a factory reset first.
        """
        return self._request("POST", "/resource/device")

    # 3) List lights

    def list_lights(self) -> list[dict[str, Any]]:
        """
        Return all Hue v2 light resources currently known by the bridge.

        The returned list can include old/disconnected lights until those
        devices are explicitly deleted from the bridge.
        """
        response = self._request("GET", "/resource/light")
        return response.get("data", [])


def main() -> None:
    hue = HueBridgeClient()

    # 1. Confirm connection
    print("Checking bridge connection...")
    try:
        bridge_response = hue.get_bridge()
        bridge_data = bridge_response.get("data", [])
        print("Connected to Hue Bridge.")

        if bridge_data:
            print(f"Bridge ID: {bridge_data[0].get('id')}")
    except HueBridgeError as error:
        print(f"Connection failed: {error}")
        return

    # 2. Begin discovery
    print("\nStarting device discovery...")
    try:
        discovery_response = hue.start_device_discovery()
        print(json.dumps(discovery_response, indent=2))
        print(
            "\nDiscovery was started. Wait a little while, then call "
            "list_lights() to see newly added lights."
        )
    except HueBridgeError as error:
        print(f"Could not start discovery: {error}")

    # 3. List all lights currently known
    print("\nListing lights...")
    try:
        lights = hue.list_lights()

        if not lights:
            print("No lights found.")
            return

        for light in lights:
            metadata = light.get("metadata", {})
            name = metadata.get("name", "Unnamed light")
            light_id = light.get("id")
            is_on = light.get("on", {}).get("on")

            print(f"- {name}")
            print(f"  Light resource ID: {light_id}")
            print(f"  On: {is_on}")

    except HueBridgeError as error:
        print(f"Could not list lights: {error}")


if __name__ == "__main__":
    main()
