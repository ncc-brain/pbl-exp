# pbl-exp

Useful helper functions for running experiments at the Predictive Brain Lab (Bochum).

Overall, the philosophy is to provide simple and convenient tools for running experiments while logging events and experimental information. This includes the use of PsychoPy GUI dialogs for user input and configuration.

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

send_event_to_pupil_labs(device, "event_name", median_offset_ns)
```

This event can also be called with device is `None`, which simplifies testing and debugging. In this case, the function will not attempt to send the event to any device but will still log the event with the provided timestamp.
