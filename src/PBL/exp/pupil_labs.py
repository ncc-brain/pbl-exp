import sys
from time import time_ns

from psychopy import gui, logging
from pupil_labs.realtime_api.simple import Device, discover_devices


def get_pupil_labs_device(
    search_duration_seconds: float = 5.0, n_offset_measurements: int = 100
):
    """
    Get the Pupil Labs device and its time offset.

    The function first prompts the user to decide whether to use the Pupil Labs eye tracker.
    If the user chooses no, the function will return None for both the device and the time offset.
    If the user chooses yes, the function will search for available Pupil Labs devices on the network
    for `search_duration_seconds` to find available devices.

    If only one device is found, a dialog will inform the user that this device will be used.
    If multiple devices are found, the user will be prompted to select which device to use by its IP address.

    Parameters
    ----------
    search_duration_seconds : float
        Duration to search for Pupil Labs devices.
    n_offset_measurements : int
        Number of offset measurements to estimate the time offset.

    Returns
    -------
    device : object or None
        The connected Pupil Labs device, or None if not used.
    median_offset_ns : int or None
        The estimated median time offset of the device in nanoseconds, or None if not used.

    Raises
    ------
    RuntimeError
        If no Pupil Labs device is found when one is expected.
    """
    # Get whether to use the Pupil Labs Eye Tracker
    dlg = gui.Dlg(title="Pupil Labs Eye Tracker")
    dlg.addField("Use Pupil Labs eye tracker?", False, choices=[True, False])
    dlg_data = dlg.show()
    sys.exit() if not dlg.OK else None
    record_pl = dlg_data[0]

    if record_pl:
        devices = discover_devices(search_duration_seconds=search_duration_seconds)
        if not devices:
            dlg = gui.Dlg(title="No Pupil Labs device found")
            dlg.addText("No Pupil Labs device found. Check your connection.")
            dlg.show()
            raise RuntimeError("No Pupil Labs device found.")
        elif len(devices) == 1:
            device = devices[0]
        else:
            ip_addresses = [device.address for device in devices]
            dlg = gui.Dlg(title="Pupil Labs configuration")
            dlg.addText("Multiple Pupil Labs devices found.")
            dlg.addField("Select the device to use:", choices=ip_addresses)
            dlg.show()
            selected_ip = dlg.data[0]
            for d in devices:
                if d.address == selected_ip:
                    device = d
                else:
                    d.close()
        # Show the connected device information
        device_vars = vars(device)
        dlg = gui.Dlg(title="Pupil Labs configuration")
        if len(devices) == 1:
            dlg.addText("Exactly one Pupil Labs device found:")
        else:
            dlg.addText("Selected Pupil Labs device:")
        for key, value in device_vars.items():
            dlg.addText(f"{key}: {value}")
        dlg.show()
        sys.exit() if not dlg.OK else None
        if device.version_glasses == 1:
            serial = device.serial_number_glasses
        else:
            serial = device.module_serial
        logging.info(f"Connected to Pupil Labs device (serial number: {serial})")

        median_offset_ns = round(
            device.estimate_time_offset().time_offset_ms.median * 1_000_000
        )
        offset_std = round(
            device.estimate_time_offset(n_offset_measurements).time_offset_ms.std
            * 1_000_000
        )
        logging.info(
            f"Estimated Pupil Labs device time offset (ns) = {median_offset_ns} ± {offset_std} (median ± std)"
        )

        return device, median_offset_ns
    else:
        return None, None


def send_event_to_pupil_labs(device: Device, event_string: str, clock_offset_ns: int):
    """
    Send an event to the Pupil Labs device with a timestamp.

    Parameters
    ----------
    device : Device
        The connected Pupil Labs device.
    event_string : str
        The event description to send.
    clock_offset_ns : int
        The clock offset in nanoseconds to adjust the event timestamp.
    """
    if device is not None:
        device.send_event(
            event_string,
            event_timestamp_unix_ns=int(time_ns() - clock_offset_ns),
        )


if __name__ == "__main__":
    logging.console.setLevel(logging.INFO)
    device, offset_ns = get_pupil_labs_device()
    if device is not None:
        device.close()
