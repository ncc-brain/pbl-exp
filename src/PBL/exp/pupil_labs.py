import sys
from time import time_ns

from psychopy import gui, logging
from pupil_labs.realtime_api.simple import Device, discover_devices


def get_pupil_labs_device(search_duration_seconds=5.0):
    """
    Get the Pupil Labs device and its time offset.

    Parameters
    ----------
    search_duration_seconds : float
        Duration to search for Pupil Labs devices.

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
            dlg = gui.Dlg(title="Pupil Labs configuration")
            dlg.addText(f"Using the only Pupil Labs device found at {device.address}")
            dlg.show()
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
        logging.info(f"Connected to Pupil Labs device at {device.address}")

        median_offset_ns = round(
            device.estimate_time_offset().time_offset_ms.median * 1_000_000
        )
        offset_std = round(device.estimate_time_offset().time_offset_ms.std * 1_000_000)
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
