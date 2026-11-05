# Predictive Brain Lab Experiment Helpers

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
[![PyPI - Version](https://img.shields.io/pypi/v/pbl-exp)](https://pypi.org/project/pbl-exp/)

Useful helper functions for running experiments at the Predictive Brain Lab (Bochum).

Overall, the philosophy is to provide simple and convenient tools for running experiments while logging events and experimental information across devices.

## Installation

The library can be installed via pip:

```bash
pip install pbl-exp
```

## Documentation

See the [full documentation](https://ncc-brain.github.io/pbl-exp/), including
the API reference and examples.

## Modules and functionalities

### `pupil_labs` module

Supports connecting to and configuring a Pupil Labs eye tracker (such as Neon):

- Discover available devices and select one to connect to
- Verify the active recording template and optionally update its data
- Send timestamped events to the device (with [offset correction](https://pupil-labs.github.io/pl-realtime-api/dev/methods/simple/remote-control/#with-manual-clock-offset-correction))

### `lsl` module

Provides helpers for Lab Streaming Layer (LSL) and LabRecorder:

- Create an LSL string-marker outlet
- Check whether one or more streams are available
- Launch, configure, and control LabRecorder

### `markers` module

Generates AprilTag and ArUco fiducial markers as PsychoPy stimuli, with optional automatic positioning around the display.
