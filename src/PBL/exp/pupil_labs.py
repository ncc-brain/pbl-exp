from time import time_ns

from psychopy import core, gui, logging
from pupil_labs.realtime_api.simple import Device, discover_devices


def get_pupil_labs_device(
    search_duration_seconds: float = 3.0,
    n_offset_measurements: int = 100,
):
    """
    Configure a connection to a Pupil Labs eye tracker and estimate its clock offset.

    The user is first asked whether to connect to a Pupil Labs eye tracker. If
    the user declines, the function returns ``(None, None)``.

    If the user chooses to connect, the function searches the network for
    available Pupil Labs devices. A single discovered device is selected
    automatically. If multiple devices are discovered, the user selects one
    by its IP address.

    If no device is discovered, the user can return to the initial
    configuration dialog and try again. Cancelling any dialog terminates the
    PsychoPy experiment.

    Parameters
    ----------
    search_duration_seconds : float, default=3.0
        Number of seconds to search the network for Pupil Labs devices.
    n_offset_measurements : int, default=100
        Number of measurements used to estimate the clock offset between the
        computer and the selected device.

    Returns
    -------
    device : object or None
        The connected Pupil Labs device, or ``None`` if the user chooses not
        to connect to one.
    median_offset_ns : int or None
        The median estimated clock offset, in nanoseconds, or ``None`` if no
        device is used.
    """
    while True:  # Repeat configuration if no device is detected
        dlg = gui.Dlg(title="Pupil Labs eye tracker")
        dlg.addField(
            "Connect to a Pupil Labs eye tracker?",
            "Yes",
            choices=["Yes", "No"],
        )
        dlg_data = dlg.show()

        if not dlg.OK:
            core.quit()

        connect_pl = dlg_data[0] == "Yes"

        if not connect_pl:
            logging.info("Pupil Labs eye-tracker connection not enabled")
            return None, None

        # Search the network for available Pupil Labs devices.
        devices = discover_devices(search_duration_seconds=search_duration_seconds)

        if not devices:
            dlg = gui.Dlg(title="No Pupil Labs eye tracker detected")
            dlg.addText(
                f"A {search_duration_seconds:g}-second search did not detect "
                "a Pupil Labs eye tracker.\n\n"
                "Make sure the eye tracker is powered on and connected to the "
                "same network as this computer.\n\n"
                "Select OK to return to the setup dialog, or Cancel to exit."
            )
            dlg.show()

            if not dlg.OK:
                core.quit()

            continue

        if len(devices) == 1:
            # Select the only available device automatically.
            device = devices[0]

        else:
            # Ask the user to select one of the available devices.
            ip_addresses = [candidate.address for candidate in devices]

            dlg = gui.Dlg(title="Pupil Labs eye-tracker configuration")
            dlg.addText("Multiple Pupil Labs eye trackers were detected.")
            dlg.addField(
                "Select the device IP address:",
                choices=ip_addresses,
            )
            dlg.show()

            if not dlg.OK:
                for candidate in devices:
                    candidate.close()
                core.quit()

            selected_ip = dlg.data[0]
            device = next(
                candidate for candidate in devices if candidate.address == selected_ip
            )

            # Close connections to devices that were not selected.
            for candidate in devices:
                if candidate is not device:
                    candidate.close()

        # Display information about the selected device.
        dlg = gui.Dlg(title="Pupil Labs eye-tracker configuration")

        if len(devices) == 1:
            dlg.addText(
                "One Pupil Labs eye tracker was detected. "
                "The following device will be used:"
            )
        else:
            dlg.addText("The following Pupil Labs eye tracker was selected:")

        for key, value in vars(device).items():
            dlg.addText(f"{key}: {value}")

        dlg.show()

        if not dlg.OK:
            device.close()
            core.quit()

        # Identify the eye-tracker model and serial number.
        if device.version_glasses == 1:
            device_name = "Invisible"
            serial_number = device.serial_number_glasses
        elif device.version_glasses == 2:
            device_name = "Neon"
            serial_number = device.module_serial
        else:
            raise ValueError(
                f"Unsupported Pupil Labs device version: {device.version_glasses}"
            )

        logging.info(
            f"Connected to Pupil Labs {device_name} (serial number: {serial_number})"
        )

        # Estimate the clock offset using one set of measurements.
        time_echo_estimates = device.estimate_time_offset(n_offset_measurements)

        median_offset_ns = round(time_echo_estimates.time_offset_ms.median * 1_000_000)
        offset_std_ns = round(time_echo_estimates.time_offset_ms.std * 1_000_000)

        logging.info(
            "Estimated Pupil Labs clock offset: "
            f"median={median_offset_ns} ns, "
            f"standard deviation={offset_std_ns} ns, "
            f"measurements={n_offset_measurements}"
        )

        return device, median_offset_ns


def post_pupil_labs_template(device: Device | None = None):
    """
    Verify that the a correct template is selected on the Pupil Labs device,
    and optionally posts it to the device.

    Parameters
    ----------
    device : Device or None, default=None
        Connected Pupil Labs device.

    Returns
    -------
    bool
        True if the device is connected and responsive, False otherwise.
    """
    if device is not None:
        template = device.get_template()
        template_data = device.get_template_data()


def send_event_to_pupil_labs(
    event_string: str,
    device: Device | None = None,
    clock_offset_ns: int | None = None,
) -> None:
    """
    Send a timestamped event to a connected Pupil Labs eye tracker.

    The event timestamp is based on the computer's current Unix time and is
    adjusted by the estimated clock offset between the computer and the eye
    tracker. If no device is provided, the function returns without sending
    an event.

    Parameters
    ----------
    event_string : str
        Description or label of the event.
    device : Device or None, default=None
        Connected Pupil Labs device. If ``None``, no event is sent.
    clock_offset_ns : int, default=0
        Estimated clock offset, in nanoseconds, to subtract from the
        computer's Unix timestamp.
    """
    if device is None or clock_offset_ns is None:
        return

    device.send_event(
        event_string,
        event_timestamp_unix_ns=time_ns() - clock_offset_ns,
    )


if __name__ == "__main__":
    logging.console.setLevel(logging.INFO)

    device, clock_offset_ns = get_pupil_labs_device()

    if device is not None:
        try:
            send_event_to_pupil_labs(
                event_string="connection_test",
                device=device,
                clock_offset_ns=clock_offset_ns,
            )
            logging.info("Sent connection test event to Pupil Labs eye tracker")
        finally:
            device.close()
            logging.info("Closed the Pupil Labs eye-tracker connection")
