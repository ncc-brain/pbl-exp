import os
import random

from psychopy import core, gui, logging, visual
from psychopy.hardware import keyboard

from pred_brain.exp import (
    configure_pupil_labs_template,
    create_fiducial_marker_stimuli,
    get_pupil_labs_device,
    send_event_to_pupil_labs,
)
from pred_brain.exp.lsl import (
    check_lsl_streams,
    create_markers_outlet,
    launch_lab_recorder,
    set_lab_recorder_filename,
    start_recording_lab_recorder,
    stop_recording_lab_recorder,
    update_lab_recorder,
)

# ---------------------------------------------------------------------------
# 1. Participant information
# ---------------------------------------------------------------------------
# Ask for the participant ID and run number. They are used to build
# BIDS-style file names for the log and LabRecorder files.

dlg = gui.Dlg(title="Participant Information")
dlg.addField("Participant ID:")
dlg.addField("Run:")
dlg.show()  # Blocks until the dialog is closed.
if dlg.OK:
    participant_id = dlg.data[0]
    run = int(dlg.data[1])
else:
    core.quit()  # The user pressed cancel.

# ---------------------------------------------------------------------------
# 2. Experiment configuration
# ---------------------------------------------------------------------------
# All timing and path settings are collected here so they are easy to change.

TASK = "JudgeColor"
N_TRIALS = 5
FLASH_DURATION_SECONDS = 0.5  # How long the flash stays on screen.
FLASH_TO_QUESTION_SECONDS = 1.0  # Blank delay between flash and question.
ISI = 1.0  # Inter-trial interval after the response.
STARTUP_SECONDS = 3.0  # Time for recorders to initialise before the first marker.

log_directory = "examples_logs_and_data"
lab_recorder_path = r"LabRecorder-1.18.0-Win_amd64\LabRecorder.exe"

bids_file_stem = f"sub-{participant_id}_task-{TASK}_run-{run}"

# ---------------------------------------------------------------------------
# 3. PsychoPy logging
# ---------------------------------------------------------------------------
# Log INFO and above to the console and to a file. Events are logged at the
# EXP level, which sits between INFO and WARNING.

logging.console.setLevel(logging.INFO)
os.makedirs(log_directory, exist_ok=True)

# Keep a reference to the LogFile for the whole experiment; otherwise the file
# may be closed when the object is garbage collected.
log_file = logging.LogFile(
    os.path.join(log_directory, f"{bids_file_stem}.log"),
    level=logging.INFO,
    filemode="w",
)
logging.info("Experiment initialization started")

# ---------------------------------------------------------------------------
# 4. LSL marker stream
# ---------------------------------------------------------------------------
# Create an LSL outlet with one string channel. Every experiment event is
# pushed through it, and LabRecorder saves it together with the other streams.

markers_outlet = create_markers_outlet()
markers_outlet_name = markers_outlet.get_info().name()
logging.info(f"{markers_outlet_name} LSL stream initialized")

# ---------------------------------------------------------------------------
# 5. Pupil Labs connection
# ---------------------------------------------------------------------------
# Connect to a Pupil Labs eye tracker if one is found. The clock offset
# converts PsychoPy timestamps to the device clock. If no device is found,
# `device` is None and the experiment still runs, sending markers over LSL only.

device, clock_offset_ns = get_pupil_labs_device()

# Make sure the device uses the recording template we expect.
configure_pupil_labs_template(
    device=device,
    template_name="Recording with Notes",
)


# Define a helper function to send events to both LSL and Pupil Labs.
def send_event_to_outputs(event_string: str) -> None:
    """Send an event marker to LSL and, when connected, to Pupil Labs.

    Schedule this function with ``win.callOnFlip`` when a marker should be
    timestamped as close as possible to a visual change. PsychoPy's own log
    uses ``win.logOnFlip`` separately so it receives PsychoPy's flip timestamp.
    """
    markers_outlet.push_sample([event_string])
    if device is not None and clock_offset_ns is not None:
        send_event_to_pupil_labs(
            event_string=event_string,
            device=device,
            clock_offset_ns=clock_offset_ns,
        )


# ---------------------------------------------------------------------------
# 6. LabRecorder and LSL stream check
# ---------------------------------------------------------------------------
# Start LabRecorder, point it to the output file, and refresh its stream list
# so that it sees our marker stream.

launch_lab_recorder(lab_recorder_path)
set_lab_recorder_filename(root=log_directory, filename=f"{bids_file_stem}.xdf")
update_lab_recorder()

# Verify that every stream we want to record is visible on the network before
# starting. Names are matched as regular expressions.
expected_streams = [{"name": markers_outlet_name, "type": "Markers"}]
if device is not None:
    # Add expected streams for the Pupil Labs device if it is connected.
    expected_streams.append({"name": r"Neon Gaze$", "type": "Gaze"})
    expected_streams.append({"name": r"Neon Events$", "type": "Event"})

streams_ok, found_streams = check_lsl_streams(expected_streams)

if not streams_ok:
    # Abort rather than collect data that is missing a stream.
    logging.error(f"Expecting: {expected_streams}")
    logging.error(f"Found streams: {found_streams}")
    if device is not None:
        device.close()
    core.quit()

# ---------------------------------------------------------------------------
# 7. Display, stimuli and keyboard
# ---------------------------------------------------------------------------

win = visual.Window(fullscr=True)
win.mouseVisible = False

# Full-screen coloured rectangle used as the flash.
stimulus = visual.Rect(
    win=win, width=1, height=1, fillColor="white", units="norm", name="Stimulus"
)

# Text used for the instruction and, later, the question.
text = visual.TextStim(
    win=win,
    text="Press the space bar to start",
    height=0.05,
    units="height",
    name="Instruction",
)

# Fiducial markers in the screen corners let the Pupil Labs software map gaze
# onto the display. With autoDraw they are drawn on every flip.
markers = create_fiducial_marker_stimuli(
    win=win,
    marker_family="36h11",
    marker_ids=range(4),
    marker_size_pixels=200,
    auto_layout=True,
)
for marker in markers:
    marker.autoDraw = True

# One keyboard device serves the start screen, the responses and the Escape
# interruption callback.
kb = keyboard.KeyboardDevice()


# Helper function to end the experiment and release resources.
def end_experiment(interrupted: bool = False) -> None:
    """
    End the experiment and release its resources.

    An experiment-end marker is written to the PsychoPy log and the LSL event
    stream. If a Pupil Labs recording is active, the marker is also sent to
    the eye tracker before its recording is stopped and saved.
    """
    if interrupted:
        event_string = "experiment end (interrupted)"
        logging.warning(event_string)
    else:
        event_string = "experiment end"
        logging.exp(event_string)

    # Record the experiment end marker in the LSL stream.
    markers_outlet.push_sample([event_string])

    # Send the experiment end marker to the Pupil Labs device if it is connected.
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


# Pressing Escape calls `end_experiment(True)`. The callback is processed
# whenever keyboard events are checked (e.g. inside `kb.waitKeys`).
kb.registerCallback(
    response="escape",
    func=end_experiment,
    args=[True],
)


# ---------------------------------------------------------------------------
# 8. Start screen
# ---------------------------------------------------------------------------

text.draw()
win.flip()

# Wait for the participant (or experimenter) to press the space bar.
kb.waitKeys(keyList=["space"])

# Clear the instruction screen.
win.flip()

# ---------------------------------------------------------------------------
# 9. Start recording
# ---------------------------------------------------------------------------
# Start the external recordings first and give them time to initialise, so the
# experiment-start marker is not lost.

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
# 10. Trial loop
# ---------------------------------------------------------------------------
# Each trial: flash -> blank -> question -> response -> inter-trial interval.

# From now on, `text` shows the response question.
text.setName("question")
text.setText("What color was the flash?\n<-- Red    Blue -->")

# Correct response key for each flash colour.
correct_keys = {"red": "left", "blue": "right"}

for trial_index in range(N_TRIALS):
    # Choose the flash colour and prepare it in the back buffer. Nothing is
    # visible until the next `win.flip()`.
    color = random.choice(["red", "blue"])
    stimulus.setFillColor(color)
    stimulus.draw()

    # Register two actions for the upcoming flip:
    #  * callOnFlip sends the LSL / Pupil Labs marker right after the flip,
    #    placing its timestamp close to the flash's visual onset;
    #  * logOnFlip lets PsychoPy log the event with its own flip timestamp.
    event_name = "flash onset"
    win.callOnFlip(send_event_to_outputs, event_name)
    win.logOnFlip(level=logging.EXP, msg=event_name)

    # Show the flash (this runs both callbacks) and keep it on screen.
    win.flip()
    core.wait(FLASH_DURATION_SECONDS)

    # Flip again without drawing the stimulus to remove the flash, then wait.
    win.flip()
    core.wait(FLASH_TO_QUESTION_SECONDS)

    # Show the question, marking its onset the same way as the flash.
    text.draw()
    event_name = "question onset"
    win.callOnFlip(send_event_to_outputs, event_name)
    win.logOnFlip(level=logging.EXP, msg=event_name)
    win.flip()

    # Wait for a response. Escape still ends the experiment through the
    # callback registered earlier.
    keys = kb.waitKeys(keyList=["left", "right"])
    key_pressed = keys[0].name
    correct_text = "correct" if key_pressed == correct_keys[color] else "incorrect"

    # Record the response. No flip is involved, so log and send it directly.
    event_name = f"response: {key_pressed} ({correct_text})"
    send_event_to_outputs(event_name)
    logging.data(event_name)

    # Clear the question and wait before the next trial.
    win.flip()
    core.wait(ISI)

    # Write queued log messages to disk after every trial.
    logging.flush()

# ---------------------------------------------------------------------------
# 11. Normal experiment completion
# ---------------------------------------------------------------------------
# Sends the end marker, stops all recordings and closes the window.

end_experiment(interrupted=False)
