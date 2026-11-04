"""Example PsychoPy experiment with LSL and Pupil Labs event markers."""

import os
import socket

from psychopy import core, gui, logging, visual
from psychopy.hardware import keyboard
from pylsl import StreamInfo, StreamOutlet

from pred_brain.exp import (
    configure_pupil_labs_template,
    create_fiducial_marker_stimuli,
    get_pupil_labs_device,
    send_event_to_pupil_labs,
)
from pred_brain.exp.lsl import (
    check_lsl_streams,
    launch_lab_recorder,
    set_lab_recorder_filename,
    start_recording_lab_recorder,
    stop_recording_lab_recorder,
    update_lab_recorder,
)

# Get participant and run information
dlg = gui.Dlg(title="Participant Information")
dlg.addField("Participant ID:")
dlg.addField("Run:")
dlg.show()  # Show the dialog and wait for user input
if dlg.OK:
    participant_id = dlg.data[0]
    run = int(dlg.data[1])
else:
    core.quit()  # User pressed cancel

# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------
TASK = "WatchFlash"
N_TRIALS = 5
FLASH_DURATION_SECONDS = 0.5
INTER_FLASH_INTERVAL_SECONDS = 3.0
STARTUP_SECONDS = 3.0

LOG_DIRECTORY = "examples_logs_and_data"

bids_file_stem = f"sub-{participant_id}_task-{TASK}_run-{run}"
log_file_path = os.path.join(
    LOG_DIRECTORY,
    f"{bids_file_stem}.log",
)

logging.console.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# PsychoPy logging
# ---------------------------------------------------------------------------

# Create the log directory if it does not already exist.
os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Keep a reference to the LogFile object for the duration of the experiment.
log_file = logging.LogFile(
    log_file_path,
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
    name="PsychoPyEvents",
    type="Markers",
    channel_count=1,
    channel_format="string",
    source_id=f"psychopy-events-{socket.gethostname()}",
)

event_outlet = StreamOutlet(event_stream_info)

logging.info("Experiment-event LSL stream initialized")


# ---------------------------------------------------------------------------
# Pupil Labs connection
# ---------------------------------------------------------------------------

# Connect to a Pupil Labs eye tracker if one is available and selected. When
# there is no device, the experiment still runs and sends markers over LSL.
device, clock_offset_ns = get_pupil_labs_device()

# Optionally, verify that the device is correctly configured with the desired template.
configure_pupil_labs_template(
    device=device,
    template_name="Recording with Notes",  # default template
)


def send_event_to_outputs(event_string: str):
    """Send an event marker to LSL and, when connected, to Pupil Labs.

    Schedule this function with ``win.callOnFlip`` when a marker should be
    timestamped as close as possible to a visual change. PsychoPy's own log
    uses ``win.logOnFlip`` separately so it receives PsychoPy's flip timestamp.
    """
    event_outlet.push_sample([event_string])
    if device is not None and clock_offset_ns is not None:
        send_event_to_pupil_labs(
            event_string=event_string,
            device=device,
            clock_offset_ns=clock_offset_ns,
        )


# ---------------------------------------------------------------------------
# Launch LabRecorder and check LSL streams
# ---------------------------------------------------------------------------

launch_lab_recorder(r"LabRecorder-1.18.0-Win_amd64\LabRecorder.exe")
set_lab_recorder_filename(
    root="examples_logs_and_data", filename=f"{bids_file_stem}.xdf"
)
update_lab_recorder()

# Check that all expected LSL streams are available
expected_streams = [{"name": "PsychoPyEvents", "type": "Markers"}]
if device is not None:
    expected_streams.append({"type": "Gaze"})

flag, streams = check_lsl_streams(expected_streams)

if not flag:
    logging.error(f"Expecting: {expected_streams}")
    logging.error(f"Found streams: {streams}")
    if device is not None:
        device.close()
    core.quit()

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
    marker_ids=range(4),
    marker_size_pixels=200,
    auto_layout=True,
)
for marker in markers:
    marker.autoDraw = True

# Use the same keyboard device for the start-screen response and Escape
# interruption callback.
kb = keyboard.KeyboardDevice()


def end_experiment(interrupted: bool = False) -> None:
    """
    End the experiment and release its resources.

    An experiment-end marker is written to the PsychoPy log and the LSL event
    stream. If a Pupil Labs recording is active, the marker is also sent to
    the eye tracker before its recording is stopped and saved.
    """
    event_string = "experiment end (interrupted)" if interrupted else "experiment end"

    # Record the final marker in PsychoPy and LSL before stopping the device,
    # so it can also be sent to the active Pupil Labs recording below.
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
    stop_recording_lab_recorder()
    logging.info("LabRecorder stopped")
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

# Start only after the participant presses the space bar. Escape remains
# registered as an interruption key while keyboard events are being processed.
kb.waitKeys(keyList=["space"])

# Clear the instruction screen.
win.flip()


# ---------------------------------------------------------------------------
# Start the external recording first, then allow it to initialize before the
# experiment-start marker is sent to the output streams.
# ---------------------------------------------------------------------------

start_recording_lab_recorder()
if device is not None:
    device.recording_start()
    logging.info("Pupil Labs recording started")

core.wait(STARTUP_SECONDS)
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

    # Run external marker output immediately after the upcoming flip, placing
    # its timestamp close to the flash's visual onset. PsychoPy timestamps the
    # same event separately through logOnFlip.
    win.callOnFlip(
        send_event_to_outputs,
        flash_onset_event,
    )
    win.logOnFlip(
        level=logging.EXP,
        msg=flash_onset_event,
    )

    # Display the flash and run both callbacks registered above.
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

# Leave a short post-trial period before writing the end marker and stopping
# the Pupil Labs recording.
core.wait(1.0)

end_experiment(interrupted=False)
