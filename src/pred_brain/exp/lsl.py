"""Helpers for launching LabRecorder and controlling its LSL recording state."""

import subprocess
import socket

from pathlib import Path
from psychopy import core


def launch_lab_recorder(
    path_to_lab_recorder: Path | str, path_cfg: Path | str | None = None
):
    """Launch LabRecorder, optionally loading a configuration file.

    The process is started asynchronously; this function does not wait for it
    to finish or return its process handle.

    Parameters
    ----------
    path_to_lab_recorder : pathlib.Path or str
        Path to the LabRecorder executable.
    path_cfg : pathlib.Path or str, optional
        Path to a LabRecorder configuration file. When provided, it is passed
        to the executable with the ``-c`` option.

    Raises
    ------
    OSError
        If the operating system cannot start the executable.
    """
    if path_cfg is not None:
        subprocess.Popen([str(path_to_lab_recorder), "-c", str(path_cfg)])
    else:
        subprocess.Popen([str(path_to_lab_recorder)])


def start_recording_lab_recorder(port: int = 22345, select_all: bool = True):
    """Start an LSL recording through LabRecorder's remote-control server.

    When ``select_all`` is true, the function first sends ``update`` and
    ``select_all`` commands so that all available streams are selected.

    Parameters
    ----------
    port : int, default=22345
        TCP port of the LabRecorder remote-control server on localhost.
    select_all : bool, default=True
        Whether to refresh the stream list and select every available stream
        before starting the recording.

    Raises
    ------
    OSError
        If a connection to the server cannot be established or a command
        cannot be sent.
    """
    with socket.create_connection(("localhost", port)) as sock:
        if select_all:
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
    with socket.create_connection(("localhost", port)) as sock:
        sock.sendall(b"stop\n")


if __name__ == "__main__":
    # launch_lab_recorder(
    #     r"Z:\01 Projects\2026-0004-MemoryTour\99_SharedSoftware\LabRecorder-1.18.0-Win_amd64\LabRecorder.exe"
    # )
    with socket.create_connection(("localhost", 22345), timeout=5) as sock:
        sock.sendall(
            b"filename {root:Z:\\01 Projects\\2026-0004-MemoryTour\\02_Data\\tests\\} "
            b"{template:sub-%p\ses-%s\%m\sub-%p_ses-%s_task-%b_run-%n_%m.xdf}"
            b"{run:2} {participant:lsltest} {task:memory} {session:2} {modality:beh}\n"
        )

    start_recording_lab_recorder()
    core.wait(5)  # Wait for 5 seconds before stopping the recording
    stop_recording_lab_recorder()
