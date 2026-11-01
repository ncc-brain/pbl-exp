# pbl-exp

Useful helper functions for running experiments at the Predictive Brain Lab (Bochum).

Overall, the philosophy is to provide simple and convenient tools for running experiments while logging events and experimental information across devices. 

The library aims to log/send events to:

- Pupil Labs eye tracker
- SR Research Eyelink eye tracker
- Lab Streaming Layer (LSL) streams
- PsychoPy log files

This includes the use of PsychoPy GUI dialogs for user input and configuration.

This repository also provides examples for how to use these helper functions.

## Installation

```bash
pip install pbl-exp
```

## Usage

### Conveniently connect to a Pupil Labs device and send events

```python
from PBL.exp import get_pupil_labs_device

device, median_offset_ns = get_pupil_labs_device()
```

This will open a dialog asking you:

1. Whether you want to connect to a Pupil Labs device.
2. Which device to connect to if multiple devices are available.

If a device is selected, the function will return the device object and estimate the median clock offset in nanoseconds. If no device is selected, it will return `None` for both.

The clock offset can then be used to send events to the Pupil Labs device with corrected timestamps. For example:

```python
from PBL.exp import send_event_to_pupil_labs

send_event_to_pupil_labs("event_name", device, median_offset_ns)
```

This event can also be called with device is `None`, which simplifies testing and debugging. In this case, the function will not attempt to send the event to any device but will still log the event with the provided timestamp.

### Display fiducial markers in PsychoPy

Use `create_fiducial_marker_stimuli` to generate AprilTag or ArUco marker
images as PsychoPy `ImageStim` objects. For example, create six AprilTag
stimuli and display them throughout the experiment:

```python
from psychopy import visual
from PBL.exp import create_fiducial_marker_stimuli

win = visual.Window(fullscr=True)

markers = create_fiducial_marker_stimuli(
    win=win,
    marker_family="36h11",
    marker_ids=range(6),
    marker_size_pixels=200,
    auto_layout=True,
    margin=50,
)

# Draw once per frame, or set autoDraw to keep them visible.
for marker in markers:
    marker.autoDraw = True

win.flip()
```

`marker_family` can be one of the AprilTag families `"16h5"`, `"25h9"`,
`"36h10"`, or `"36h11"`; an ArUco dictionary such as `"4x4_50"` or
`"6x6_250"`; or `"aruco_original"`. Choose `marker_ids` from the valid IDs
for that dictionary. `marker_size_pixels` sets the square marker's width and
height in pixels.

With `auto_layout=True` (the default), exactly 4, 6, or 8 markers are placed
around the window perimeter. Their order in `marker_ids` determines their
clockwise positions, starting at the top-left; `margin` is the minimum
distance from a marker to the window edge in pixels. To control positions
yourself or use a different number of markers, pass `auto_layout=False` and
set each stimulus's `pos` in PsychoPy pixel coordinates:

```python
markers = create_fiducial_marker_stimuli(
    win=win,
    marker_family="6x6_250",
    marker_ids=[10, 11],
    marker_size_pixels=200,
    auto_layout=False,
)
markers[0].pos = (-300, 0)
markers[1].pos = (300, 0)
```

Marker generation requires an OpenCV build with the `aruco` module. If it is
unavailable, install an OpenCV build that includes the contributed modules,
such as `opencv-contrib-python`.
