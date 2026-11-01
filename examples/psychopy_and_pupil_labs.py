"""Example PsychoPy experiment with LSL and Pupil Labs event markers."""

import os
import socket

from psychopy import core, logging, visual
from psychopy.hardware import keyboard
from pylsl import StreamInfo, StreamOutlet

from PBL.exp import (
    create_fiducial_marker_stimuli,
    get_pupil_labs_device,
    send_event_to_pupil_labs,
)

# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------

N_TRIALS = 5
FLASH_DURATION_SECONDS = 0.5
INTER_FLASH_INTERVAL_SECONDS = 3.0
PUPIL_RECORDING_STARTUP_SECONDS = 3.0

LOG_DIRECTORY = "examples_logs"
LOG_FILE = os.path.join(
    LOG_DIRECTORY,
    "psychopy_and_pupil_labs.log",
)


# ---------------------------------------------------------------------------
# PsychoPy logging
# ---------------------------------------------------------------------------

# Create the log directory if it does not already exist.
os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Keep a reference to the LogFile object for the duration of the experiment.
log_file = logging.LogFile(
    LOG_FILE,
    level=logging.INFO,
    filemode="w",
)

logging.info("Experiment initialization started")


# ---------------------------------------------------------------------------
# LSL event stream
# ---------------------------------------------------------------------------

# Create an LSL marker stream containing one string channel. The source ID
# should uniquely identify this outlet among the streams on the network.
event_stream_info = StreamInfo(
    name="experiment_events",
    type="Markers",
    channel_count=1,
    channel_format="string",
    source_id=f"experiment-events-{socket.gethostname()}",
)

event_outlet = StreamOutlet(event_stream_info)

logging.info("Experiment-event LSL stream initialized")


# ---------------------------------------------------------------------------
# Pupil Labs connection
# ---------------------------------------------------------------------------

# Ask whether to connect to a Pupil Labs eye tracker. If the user declines,
# both values will be None and the experiment will continue without it.
device, clock_offset_ns = get_pupil_labs_device()


def send_event_to_outputs(event_string: str) -> None:
    """
    Send an event marker to the active external outputs.

    The event is always sent to the experiment's LSL marker stream. It is also
    sent to the Pupil Labs eye tracker when a device is connected and a clock
    offset is available.

    Parameters
    ----------
    event_string : str
        Description or label of the event.

    Returns
    -------
    None
    """
    event_outlet.push_sample([event_string])

    if device is not None and clock_offset_ns is not None:
        send_event_to_pupil_labs(
            event_string=event_string,
            device=device,
            clock_offset_ns=clock_offset_ns,
        )


# ---------------------------------------------------------------------------
# PsychoPy display and input objects
# ---------------------------------------------------------------------------

win = visual.Window(fullscr=True)
win.mouseVisible = False

square = visual.Rect(
    win=win,
    width=1,
    height=1,
    fillColor="white",
    units="norm",
)

instruction_text = visual.TextStim(
    win=win,
    text="Press the space bar to start",
    height=0.05,
    units="height",
)

markers = create_fiducial_marker_stimuli(
    win=win,
    marker_family="36h11",
    marker_ids=range(6),
    marker_size_pixels=200,
    auto_layout=True,
    margin=50,
)
for marker in markers:
    marker.autoDraw = True

# Create a keyboard device for starting and interrupting the experiment.
kb = keyboard.KeyboardDevice()


def end_experiment(interrupted: bool = False) -> None:
    """
    End the experiment and release its resources.

    An experiment-end marker is written to the PsychoPy log and the LSL event
    stream. If a Pupil Labs recording is active, the marker is also sent to
    the eye tracker before its recording is stopped and saved.

    Parameters
    ----------
    interrupted : bool, default=False
        Whether the experiment was interrupted before normal completion.

    Returns
    -------
    None
        The function terminates the PsychoPy experiment by calling
        ``core.quit()``.
    """
    event_string = "experiment end (interrupted)" if interrupted else "experiment end"

    # Record the final marker in the PsychoPy log and LSL stream.
    logging.exp(event_string)
    event_outlet.push_sample([event_string])

    if device is not None:
        if clock_offset_ns is not None:
            send_event_to_pupil_labs(
                event_string=event_string,
                device=device,
                clock_offset_ns=clock_offset_ns,
            )

        device.recording_stop_and_save()
        logging.info("Pupil Labs recording stopped and saved")
        device.close()

    # Flush pending messages before closing the window and terminating.
    logging.flush()
    win.close()
    core.quit()


# Register Escape as the experiment-interruption key. The callback is processed
# when keyboard events are checked.
kb.registerCallback(
    response="escape",
    func=end_experiment,
    args=[True],
)


# ---------------------------------------------------------------------------
# Start screen
# ---------------------------------------------------------------------------

instruction_text.draw()
win.flip()

# Wait until the participant presses the space bar.
kb.waitKeys(keyList=["space"])

# Clear the instruction screen.
win.flip()


# ---------------------------------------------------------------------------
# Start the external recording and experiment
# ---------------------------------------------------------------------------

if device is not None:
    device.recording_start()
    logging.info("Pupil Labs recording started")
    # Allow the recording to initialize before sending experiment markers.
    core.wait(PUPIL_RECORDING_STARTUP_SECONDS)

experiment_start_event = "experiment start"

send_event_to_outputs(experiment_start_event)
logging.exp(experiment_start_event)
logging.flush()


# ---------------------------------------------------------------------------
# Trial loop
# ---------------------------------------------------------------------------

for trial_index in range(N_TRIALS):
    trial_number = trial_index + 1
    flash_onset_event = f"flash onset trial={trial_number}"

    # Prepare the flash in the back buffer.
    square.draw()

    # callOnFlip executes the function immediately after the window flip call.
    # This places the LSL and Pupil Labs markers close to the visual onset.
    # logOnFlip similarly timestamps the event in PsychoPy's logging system.
    win.callOnFlip(
        send_event_to_outputs,
        flash_onset_event,
    )
    win.logOnFlip(
        level=logging.EXP,
        msg=flash_onset_event,
    )

    # Display the prepared flash and invoke the registered flip callbacks.
    win.flip()

    # Keep the flash visible for the configured duration.
    core.wait(FLASH_DURATION_SECONDS)

    # Present a blank frame to remove the flash.
    win.flip()

    # Wait before beginning the next trial.
    core.wait(INTER_FLASH_INTERVAL_SECONDS)

    # Write queued log messages to disk after every trial.
    logging.flush()

    # Process keyboard input, including the registered Escape callback.
    kb.getKeys()


# ---------------------------------------------------------------------------
# Normal experiment completion
# ---------------------------------------------------------------------------

# Leave a short period after the final trial before stopping the recording.
core.wait(1.0)

end_experiment(interrupted=False)
