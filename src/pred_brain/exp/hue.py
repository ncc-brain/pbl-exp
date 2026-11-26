"""
Minimal Philips Hue API client.

The bridge connection, light listing, and light control use API v2.
Light discovery uses the legacy API v1 endpoint because the v2 device
resource endpoint is not the light-search command.

Endpoints used:
- GET  /clip/v2/resource/bridge       -> verify bridge/API connection
- POST /api/<application_key>/lights  -> start light discovery (API v1)
- GET  /api/<application_key>/lights/new -> get the latest discovery result (API v1)
- GET  /clip/v2/resource/light        -> list lights (API v2)
"""

from __future__ import annotations

import json
import ssl
import time
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
        self.bridge_url = f"https://{bridge_ip.rstrip('/')}"
        self.base_url = f"{self.bridge_url}/clip/v2"
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

    def _request_v1(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Send a request to the legacy Hue API v1 endpoint.

        API v1 identifies the application in the URL rather than in the
        ``hue-application-key`` request header used by API v2.
        """
        url = f"{self.bridge_url}/api/{self.application_key}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}

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
                f"Hue API v1 returned HTTP {error.code}: {error_body}"
            ) from error

        except URLError as error:
            raise HueBridgeError(
                f"Could not reach Hue Bridge at {self.bridge_url}: {error.reason}"
            ) from error

        except TimeoutError as error:
            raise HueBridgeError(
                f"Timed out while connecting to Hue Bridge at {self.bridge_url}"
            ) from error

        try:
            result = json.loads(body) if body else {}
        except json.JSONDecodeError as error:
            raise HueBridgeError(
                f"Hue Bridge returned invalid API v1 JSON: {body!r}"
            ) from error

        # Hue API v1 often reports application-level errors in a JSON body
        # with HTTP 200, so check for those explicitly.
        if isinstance(result, list):
            errors = [
                item["error"]
                for item in result
                if isinstance(item, dict) and "error" in item
            ]
            if errors:
                raise HueBridgeError(f"Hue API v1 error: {errors}")
        elif isinstance(result, dict) and "error" in result:
            raise HueBridgeError(f"Hue API v1 error: {result['error']}")

        return result

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

    def start_device_discovery(self) -> Any:
        """Start searching for new lights using the Hue API v1 endpoint.

        The discovery command is POST /api/<application_key>/lights.
        Ensure that the bulbs are powered on and ready to be paired.
        """
        return self._request_v1("POST", "/lights")

    def get_new_lights(self) -> dict[str, Any]:
        """Return the most recent API v1 light-discovery result.

        While discovery is running, the response's ``lastscan`` field is
        usually ``"active"``. Once complete, it contains the scan timestamp
        and any newly discovered lights.
        """
        response = self._request_v1("GET", "/lights/new")
        if not isinstance(response, dict):
            raise HueBridgeError(f"Unexpected response from /lights/new: {response!r}")
        return response

    def wait_for_discovery(
        self,
        timeout: float = 100.0,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        """Wait until the bridge reports that the current scan has finished."""
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")

        deadline = time.monotonic() + timeout
        while True:
            result = self.get_new_lights()
            if result.get("lastscan") != "active":
                return result

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HueBridgeError(
                    f"Light discovery did not finish within {timeout:g} seconds"
                )
            time.sleep(min(poll_interval, remaining))

    # 3) List lights

    def list_lights(self) -> list[dict[str, Any]]:
        """
        Return all Hue v2 light resources currently known by the bridge.

        The returned list can include old/disconnected lights until those
        devices are explicitly deleted from the bridge.
        """
        response = self._request("GET", "/resource/light")
        return response.get("data", [])

    # 4) Control lights (turn on/off)

    def turn_light_on(self, light_id: str) -> dict[str, Any]:
        """Turn on a light by its resource ID."""
        return self._request(
            "PUT",
            f"/resource/light/{light_id}",
            payload={"on": {"on": True}},
        )

    def turn_light_off(self, light_id: str) -> dict[str, Any]:
        """Turn off a light by its resource ID."""
        return self._request(
            "PUT",
            f"/resource/light/{light_id}",
            payload={"on": {"on": False}},
        )


def load_hue_mapping(filepath: str) -> dict[str, str]:
    """Load hue mapping from CSV file."""
    import csv

    mapping = {}
    try:
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                location = row["location"].strip()
                resource_id = row[" resource_id"].strip()
                mapping[location] = resource_id
    except FileNotFoundError:
        print(f"Warning: {filepath} not found")
    return mapping


def save_hue_mapping(filepath: str, mapping: dict[str, str]) -> None:
    """Save hue mapping to CSV file."""
    import csv

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["location", " resource_id"])
        writer.writeheader()
        for location, resource_id in mapping.items():
            writer.writerow({"location": location, " resource_id": resource_id})


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

    # 2. Begin discovery and wait for the bridge to finish scanning
    print("\nStarting device discovery...")
    try:
        discovery_response = hue.start_device_discovery()
        print(json.dumps(discovery_response, indent=2))

        print("\nWaiting for the bridge to finish searching...")
        discovery_result = hue.wait_for_discovery()
        newly_found = {
            key: value for key, value in discovery_result.items() if key != "lastscan"
        }
        print(f"Discovery finished. Newly found lights: {len(newly_found)}")
        if newly_found:
            print(json.dumps(newly_found, indent=2))

    except HueBridgeError as error:
        print(f"Device discovery failed: {error}")
        return

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


def map_lights_interactive() -> None:
    """Interactive light mapping: turn off lights and ask user to identify them."""
    import os

    from psychopy import gui

    dlg = gui.Dlg(title="Hue Bridge Connection")
    dlg.addText("Click OK to start light mapping")
    dlg.addText(
        "Each time, one light will be turned off among all lights,\n"
        "and you will need to enter where the light is (according to Qian's map)"
    )
    dlg.show()

    if not dlg.OK:
        print("Cancelled by user")
        return

    hue = HueBridgeClient()

    # Verify connection
    print("Checking bridge connection...")
    try:
        hue.get_bridge()
        print("Connected to Hue Bridge.")
    except HueBridgeError as error:
        print(f"Connection failed: {error}")
        return

    # Get the CSV file path
    csv_filepath = os.path.join(os.path.dirname(__file__), "hue_mapping.csv")

    # Load existing mapping
    mapping = load_hue_mapping(csv_filepath)

    # List all lights
    print("\nListing lights...")
    try:
        lights = hue.list_lights()

        if not lights:
            print("No lights found.")
            return

        # Filter lights that are currently on
        lights_on = [light for light in lights if light.get("on", {}).get("on") is True]

        if not lights_on:
            print("No lights are currently on.")
            return

        print(f"Found {len(lights_on)} lights that are on.")

        # Process each light that is on
        for idx, light in enumerate(lights_on, 1):
            metadata = light.get("metadata", {})
            name = metadata.get("name", "Unnamed light")
            resource_id = light.get("id")

            print(f"\n[{idx}/{len(lights_on)}] Processing light: {name}")
            print(f"  Resource ID: {resource_id}")

            # Turn off the light
            print("  Turning off...")
            try:
                hue.turn_light_off(resource_id)
            except HueBridgeError as error:
                print(f"  Error turning off light: {error}")
                continue

            # Ask user for the light ID
            dlg_input = gui.Dlg(title=f"Light {idx}/{len(lights_on)}: {name}")
            dlg_input.addText(f"Light '{name}' (ID: {resource_id}) is now OFF")
            dlg_input.addText("What is the location ID for this light?")
            dlg_input.addText("(e.g., G1, G2, H1, etc.)")
            dlg_input.addField("Location ID:", "")
            dlg_input.show()

            if not dlg_input.OK:
                print("  User cancelled. Turning light back on...")
                try:
                    hue.turn_light_on(resource_id)
                except HueBridgeError as error:
                    print(f"  Error turning on light: {error}")
                continue

            location_id = dlg_input.data[0].strip().upper()

            # Update the mapping
            if location_id in mapping:
                mapping[location_id] = resource_id
                print(f"  Updated mapping: {location_id} -> {resource_id}")
            else:
                print(f"  Warning: Location ID '{location_id}' not found in mapping")
                # Still update it
                mapping[location_id] = resource_id

            # Save the updated mapping
            save_hue_mapping(csv_filepath, mapping)
            print(f"  Mapping saved to {csv_filepath}")

            # Turn the light back on
            print("  Turning light back on...")
            try:
                hue.turn_light_on(resource_id)
            except HueBridgeError as error:
                print(f"  Error turning on light: {error}")

        print("\n✓ Light mapping completed!")

    except HueBridgeError as error:
        print(f"Could not list lights: {error}")
        return


if __name__ == "__main__":
    map_lights_interactive()
