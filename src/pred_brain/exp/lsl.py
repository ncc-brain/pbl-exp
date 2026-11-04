"""Helpers for launching LabRecorder and controlling its LSL recording state."""

import socket
import subprocess
import time
from pathlib import Path

import pylsl


def check_lsl_streams(
    stream_info: dict | list[dict],
    wait_time: float = 3.0,
):
    """
    Check if the specified LSL stream(s) are available within the given wait time.

    Parameters
    ----------
    stream_info : dict or list of dict
        Information about the LSL stream(s) to check for availability.
        Keys are the attributes of the LSL stream, such as "name", "type", "source_id", etc.
    wait_time : float, default=3.0
        Maximum number of seconds to wait for the stream(s) to become available.

    Returns
    -------
    bool
        True only if every requested criteria dict matches at least one
        available stream within the wait time, False otherwise. All keys in a
        criteria dict must match the same stream.

    Examples
    --------
    # Check for a stream with known name and type
    >>> check_lsl_streams({"name": "MyEvents", "type": "Markers"})
    # Check for a stream with only a known type
    >>> check_lsl_streams({"type": "Gaze"})
    True
    """
    streams = pylsl.resolve_streams(wait_time=wait_time)
    if isinstance(stream_info, dict):
        stream_info = [stream_info]

    for stream_criteria in stream_info:
        found = False
        for stream in streams:
            for key, value in stream_criteria.items():
                attribute = getattr(stream, key)
                actual_value = attribute() if callable(attribute) else attribute
                if actual_value != value:
                    break
            else:
                found = True
                break
        if not found:
            return False
    return True


def launch_lab_recorder(
    lab_recorder_path: Path | str,
    config_path: Path | str | None = None,
    port: int = 22345,
    timeout: float = 60.0,
) -> subprocess.Popen:
    """Launch LabRecorder and wait until its remote-control server is available.

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

    Returns
    -------
    subprocess.Popen
        The process object for the launched LabRecorder instance.

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
    command = [str(lab_recorder_path)]
    if config_path is not None:
        command.extend(["-c", str(config_path)])

    recorder_process = subprocess.Popen(command)

    deadline = time.monotonic() + timeout

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
                return recorder_process
        except OSError:
            time.sleep(0.1)

    raise TimeoutError(
        f"LabRecorder did not become available on localhost:{port} "
        f"within {timeout} seconds."
    )


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


def start_recording_lab_recorder(
    port: int = 22345, select_all_streams: bool = True
):
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
    with socket.create_connection(("localhost", port)) as sock:
        if select_all_streams:
            sock.sendall(b"update\n")
            sock.sendall(b"select_all\n")
        sock.sendall(b"start\n")


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


if __name__ == "__main__":
    from psychopy import core

    launch_lab_recorder(
        r"Z:\01 Projects\2026-0004-MemoryTour\99_SharedSoftware\LabRecorder-1.18.0-Win_amd64\LabRecorder.exe"
    )
    set_lab_recorder_filename(
        filename=r"sub-test\ses-2\beh\sub-test_ses-2_task-memory_run-1_beh.xdf",
    )
    start_recording_lab_recorder()
    core.wait(10)  # Wait for 10 seconds before stopping the recording
    stop_recording_lab_recorder()
