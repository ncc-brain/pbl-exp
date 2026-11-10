"""Helpers for launching LabRecorder and controlling its LSL recording state."""

import re
import socket
import subprocess
import time
from pathlib import Path

import pylsl
from psychopy import logging


def create_markers_outlet(
    name: str = "ExperimentMarkers",
    source_id: str | None = None,
    channel_label="ExperimentMarker",
) -> pylsl.StreamOutlet:
    """Create an LSL outlet for experiment markers.

    Parameters
    ----------
    name : str, default="ExperimentMarkers"
        Name of the LSL stream.
    source_id : str or None, default=None
        Source ID for the LSL stream. If None, a default ID based on the hostname is used.
    channel_label : str, default="ExperimentMarker"
        Label for the single channel in the LSL stream.

    Returns
    -------
    pylsl.StreamOutlet
        The created LSL outlet for sending experiment markers.
    """
    if source_id is None:
        source_id = f"{name}_{socket.gethostname()}"
    stream_info = pylsl.StreamInfo(
        name=name,
        type="Markers",
        channel_count=1,
        channel_format="string",
        source_id=source_id,
    )
    channels = stream_info.desc().append_child("channels")
    channel = channels.append_child("channel")
    channel.append_child_value("label", channel_label)
    channel.append_child_value("type", "Markers")
    channel.append_child_value("unit", "")
    logging.info(
        f"Created LSL markers outlet with name '{name}' and source_id '{source_id}'"
    )
    return pylsl.StreamOutlet(stream_info)


def check_lsl_streams(
    stream_criteria: dict[str, str] | list[dict[str, str]],
    wait_time: float = 3.0,
):
    """
    Check if the specified LSL stream(s) are available within the given wait time.

    Parameters
    ----------
    stream_criteria : dict or list of dict
        Information about the LSL stream(s) to check for availability.
        Each dict specifies the attributes that a stream must have to be considered a match.
        Values without regular-expression syntax are compared exactly. Values
        containing regular-expression syntax are searched against string-valued
        attributes.
        Keys are the attributes of the LSL stream, such as "name", "type", "source_id", etc.
    wait_time : float, default=3.0
        Maximum number of seconds to wait for the stream(s) to become available.

    Returns
    -------
    all_active : bool
        True only if every requested criteria dict matches at least one
        available stream within the wait time, False otherwise. All keys in a
        criteria dict must match the same stream.
    active_streams : list of StreamInfo
        List of currently active LSL streams as returned by ``pylsl.resolve_streams``.

    Examples
    --------
    # Check for a stream with an exact name and type
    >>> check_lsl_streams({"name": "MyEvents", "type": "Markers"})
    # Check for a stream with an exact type
    >>> check_lsl_streams({"type": "Gaze"})
    # Check for a stream whose name ends with "Neon Gaze"
    >>> check_lsl_streams({"name": r"Neon Gaze$"})
    True
    """
    active_streams = pylsl.resolve_streams(wait_time=wait_time)
    if isinstance(stream_criteria, dict):
        stream_criteria = [stream_criteria]

    for criteria in stream_criteria:
        found = False
        for stream in active_streams:
            for key, value in criteria.items():
                attribute = getattr(stream, key)
                actual_value = attribute() if callable(attribute) else attribute
                if re.escape(value) != value:
                    if (
                        not isinstance(actual_value, str)
                        or re.search(value, actual_value) is None
                    ):
                        break
                    continue
                if actual_value != value:
                    break
            else:
                found = True
                break
        if not found:
            logging.warning(f"LSL stream matching criteria {criteria} not found.")
            return False, active_streams
    logging.info("All requested LSL streams are active.")
    return True, active_streams


def launch_lab_recorder(
    lab_recorder_path: Path | str,
    config_path: Path | str | None = None,
    port: int = 22345,
    timeout: float = 60.0,
) -> None:
    """Launch LabRecorder and wait until its remote-control server is available.

    If a remote-control server is already available on ``localhost:port``,
    this function does not launch another instance.

    LabRecorder is considered ready once its remote-control TCP server accepts
    a connection on ``localhost:port``.

    Parameters
    ----------
    lab_recorder_path : pathlib.Path or str
        Path to the LabRecorder executable.
    config_path : pathlib.Path or str, optional
        Path to a LabRecorder configuration file. When provided, it is passed
        to the executable with the ``-c`` option.
    port : int, default=22345
        TCP port configured for LabRecorder's remote-control server.
    timeout : float, default=60.0
        Maximum number of seconds to wait for LabRecorder to become available.

    Raises
    ------
    RuntimeError
        If LabRecorder exits before its remote-control server becomes available.
    TimeoutError
        If LabRecorder does not become available within ``timeout`` seconds.

    Notes
    -----
    The LabRecorder configuration must enable the remote-control server on the
    specified port. Otherwise this function will time out.
    """
    server_available = False
    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            server_available = True
    except OSError:
        pass

    if not server_available:
        command = [str(lab_recorder_path)]
        if config_path is not None:
            command.extend(["-c", str(config_path)])

        recorder_process = subprocess.Popen(command)
        logging.info(f"Launching LabRecorder with command: {' '.join(command)}")

        deadline = time.monotonic() + timeout
        server_available = False

        while time.monotonic() < deadline:
            # Detect an immediate startup failure, e.g. an invalid configuration.
            if recorder_process.poll() is not None:
                raise RuntimeError(
                    f"LabRecorder exited during startup with return code "
                    f"{recorder_process.returncode}."
                )

            try:
                with socket.create_connection(
                    ("localhost", port),
                    timeout=0.25,
                ):
                    server_available = True
                    break
            except OSError:
                time.sleep(0.1)

        if not server_available:
            raise TimeoutError(
                f"LabRecorder did not become available on localhost:{port} "
                f"within {timeout} seconds."
            )
        else:
            logging.info(f"LabRecorder launched and is available on localhost:{port}.")


def _send_lab_recorder_command(port: int, command: str) -> None:
    if command:
        with socket.create_connection(("localhost", port)) as sock:
            sock.sendall(command.encode())


def set_lab_recorder_filename(
    port: int = 22345,
    root: str | Path | None = None,
    filename: str | None = None,
):
    """Configure LabRecorder's filename template through its remote-control server.

    Parameters
    ----------
    port : int, default=22345
        TCP port of the LabRecorder remote-control server on localhost.
    root : str or pathlib.Path, optional
        Root directory for the recording files.
    filename : str, optional
        Filename or filename template. Leave as None to keep the default BIDS template.
    """
    filename_command = ""
    if root is not None:
        filename_command += f" {{root:{root}}}"
    if filename is not None:
        filename_command += f" {{template:{filename}}}"
    if filename_command != "":
        _send_lab_recorder_command(port, f"filename{filename_command}\n")
        logging.info(
            f"Set LabRecorder filename with command: filename{filename_command}"
        )


def start_recording_lab_recorder(port: int = 22345, select_all_streams: bool = True):
    """Start an LSL recording through LabRecorder's remote-control server.

    When ``select_all_streams`` is true, the function first sends ``update`` and
    ``select_all`` commands so that all available streams are selected.

    Parameters
    ----------
    port : int, default=22345
        TCP port of the LabRecorder remote-control server on localhost.
    select_all_streams : bool, default=True
        Whether to refresh the stream list and select every available stream
        before starting the recording.

    Raises
    ------
    OSError
        If a connection to the server cannot be established or a command
        cannot be sent.
    """
    update_lab_recorder(port)
    with socket.create_connection(("localhost", port)) as sock:
        if select_all_streams:
            sock.sendall(b"select_all\n")
        sock.sendall(b"start\n")
        logging.info("Sent start command to LabRecorder.")


def update_lab_recorder(port: int = 22345):
    """Send an update command to LabRecorder's remote-control server to refresh the stream list.

    Parameters
    ----------
    port : int, default=22345
        TCP port of the LabRecorder remote-control server on localhost.

    Raises
    ------
    OSError
        If a connection to the server cannot be established or the command
        cannot be sent.
    """
    _send_lab_recorder_command(port, "update\n")


def stop_recording_lab_recorder(port: int = 22345):
    """Stop the active LSL recording through LabRecorder's remote-control server.

    Parameters
    ----------
    port : int, default=22345
        TCP port of the LabRecorder remote-control server on localhost.

    Raises
    ------
    OSError
        If a connection to the server cannot be established or the command
        cannot be sent.
    """
    _send_lab_recorder_command(port, "stop\n")
    logging.info("Sent stop command to LabRecorder.")
