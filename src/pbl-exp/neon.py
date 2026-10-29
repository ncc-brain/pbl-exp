import sys

from psychopy import gui, logging

# Get whether to use the Pupil Labs Eye Tracker
dlg = gui.Dlg(title="Neon Eye Tracker")
dlg.addField("Use Neon eye tracker?", False, choices=[True, False])
dlg_data = dlg.show()
sys.exit() if not dlg.OK else None
record_neon = dlg_data["Use Neon eye tracker?"]

if record_neon:
    from pupil_labs.realtime_api.simple import discover_devices
    devices = discover_devices(search_duration_seconds=5.0) # Search for devices for 5 seconds
    if not devices:
        dlg = gui.Dlg(title="No Neon found")
        dlg.addText("No Neon eye tracker devices found. Check your connection.")
        dlg.show()
        raise RuntimeError("No Neon eye tracker devices found.")
    elif len(devices) == 1:
        neon = devices[0]
        dlg = gui.Dlg(title="Neon configuration")
        dlg.addText(f"Using the only Neon found at {neon.address}")
        dlg.show()
    else:
        ip_addresses = [device.address for device in devices]
        dlg = gui.Dlg(title="Neon configuration")
        dlg.addText("Multiple Neon devices found.")
        dlg.addField("Select the device to use:", choices=ip_addresses)
        dlg.show()
        selected_ip = dlg.data[0]
        neon = next(d for d in devices if d.address == selected_ip)
    logging.info(f"Using Neon device at {neon.address}")
    
    offset_ns = round(neon.estimate_time_offset().time_offset_ms.median * 1_000_000)
    logging.info(f"Estimated time offset (ns): {offset_ns}")