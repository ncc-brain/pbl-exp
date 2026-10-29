from psychopy import core, logging, visual
from psychopy.hardware import keyboard

from PBL.exp import get_pupil_labs_device, send_event_to_pupil_labs

# Create a log file to record experiment events and messages
lastLog = logging.LogFile(
    "demo_logs/psychopy_and_pupil_labs.log", level=logging.INFO, filemode="w"
)

N = 5  # Number of trials
DUR = 0.5  # Duration of the flash in seconds
INTERVAL = 3  # Interval between flashes in seconds

# Choose whether to record from a Pupil Labs device
device, offset_ns = get_pupil_labs_device()


def end_experiment(device, offset_ns):
    if device is not None and offset_ns is not None:
        send_event_to_pupil_labs(device, "experiment end", offset_ns)
        device.recording_stop_and_save()
        device.close()
    logging.exp("experiment end")
    logging.flush()
    core.quit()


# Experiment parameters and PsychoPy objects
win = visual.Window(fullscr=True, color=[-1, -1, -1])  # black
win.mouseVisible = False
square = visual.Rect(win, width=2, height=2, fillColor="white", units="norm")
text = visual.TextStim(win, text="Press space to start", height=0.05, units="height")

kb = keyboard.KeyboardDevice()
kb.registerCallback(
    response="escape",
    func=end_experiment,
    args=[device, offset_ns],
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
    win.callOnFlip(send_event_to_pupil_labs, device, "flash onset", offset_ns)
    win.logOnFlip(level=logging.EXP, msg="flash onset")
    win.flip()
    core.wait(DUR)
    win.flip()
    core.wait(INTERVAL)
    logging.flush()
    kb.getKeys()  # Check for escape key press during the interval

core.wait(1)
end_experiment(device, offset_ns)
