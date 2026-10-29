from psychopy import core, logging, visual
from psychopy.hardware import keyboard

from PBL.exp import get_pupil_labs_device, send_event_to_pupil_labs

# Create a log file to record experiment events and messages
lastLog = logging.LogFile(
    "examples_logs/psychopy_and_pupil_labs.log", level=logging.INFO, filemode="w"
)

N = 5  # Number of trials
DUR = 0.5  # Duration of the flash in seconds
INTERVAL = 3  # Interval between flashes in seconds

# Choose whether to record from a Pupil Labs device
device, offset_ns = get_pupil_labs_device()


# Define a function to end the experiment and handle Pupil Labs device cleanup
def end_experiment(device, offset_ns, interrupt=False):
    exp_exp_string = "experiment end" + (" (interrupted)" if interrupt else "")
    if device is not None and offset_ns is not None:
        send_event_to_pupil_labs(
            device,
            exp_exp_string,
            offset_ns,
        )
        device.recording_stop_and_save()
        device.close()
    logging.exp(exp_exp_string)
    logging.flush()
    core.quit()


# Experiment parameters and PsychoPy objects
win = visual.Window(fullscr=True, color=[-1, -1, -1])  # black
win.mouseVisible = False
square = visual.Rect(win, width=2, height=2, fillColor="white", units="norm")
text = visual.TextStim(win, text="Press space to start", height=0.05, units="height")

# Initialize a keyboard to capture key presses during the experiment
kb = keyboard.KeyboardDevice()
# Register the escape key to end the experiment
kb.registerCallback(
    response="escape",
    func=end_experiment,
    args=[device, offset_ns, True],
)

# Display initial message and wait for space key to continue
text.draw()
win.flip()
kb.waitKeys(keyList=["space"])
win.flip()
logging.exp("experiment start")
device.recording_start() if device is not None else None
core.wait(3)

for i in range(N):
    square.draw()
    # The following code ensures that the flash onset event is logged on both PsychoPy and Pupil Labs
    # exactly when the screen flip occurs
    win.callOnFlip(send_event_to_pupil_labs, device, "flash onset", offset_ns)
    win.logOnFlip(level=logging.EXP, msg="flash onset")
    win.flip()  # Flip the window to display the flash and trigger the events

    core.wait(DUR)
    win.flip()
    core.wait(INTERVAL)

    # Flush the logs to update the log file immediately
    logging.flush()
    kb.getKeys()  # Check if escape key was pressed during the trial

core.wait(1)
end_experiment(device, offset_ns, interrupt=False)
