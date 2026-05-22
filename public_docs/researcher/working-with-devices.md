# Working with devices

This page is a cookbook — one recipe per common task per device type. Each recipe is the smallest Python snippet that makes the device do the thing. Drop a snippet into a notebook cell, swap `<your-lab>` for your lab name, and adapt the numbers to your protocol.

## Setup (shared by every recipe)

```python
from bioexperiment_suite.interfaces import LabDevicesClient

client = LabDevicesClient(user="<your-lab>")
devices = client.discover()
```

Every recipe below assumes you've run this once at the top of the notebook.

## Pumps

### Set the default flow rate

```python
pump = devices.pumps[0]
pump.set_default_flow_rate(1.0)   # ml/min
```

Subsequent volume-based commands use this rate unless you override it.

### Pour a fixed volume

```python
pump.pour_in_volume(5.0)          # ml; uses the default flow rate
```

Blocks until the pump has dispensed the requested volume.

### Continuous rotation

```python
pump.start_continuous_rotation(1)  # direction
# ... wait, do other things ...
pump.stop_continuous_rotation()
```

Useful when you want the pump running while another cell measures something downstream.

## Densitometers

### Read temperature

```python
densitometer = devices.densitometers[0]
densitometer.get_temperature()
# 22.4  -> degrees Celsius
```

Returns immediately; cheap to poll.

### Measure optical density

```python
od = densitometer.measure_optical_density()
```

Behind the scenes the call sends a start command, sleeps ~3 seconds while the device settles, and reads. Expect the call to block for ~3 seconds.

## Valves

The `Valve` class is currently a placeholder — the lab-bridge serial vocabulary for valves is being added. Pass-through commands work via `client.send_command(device_id, …)` if you need them today; check the latest `bioexperiment_suite` release notes for new high-level methods as they land.

## Picking by position

`devices.pumps[0]` picks the first pump SerialHop returned. The order is stable across calls for a given lab unless the operator re-runs discovery or unplugs hardware. If you have multiple devices of the same type and want determinism, address them by their position in the list and document which is which in your notebook — a one-line comment in the first cell ("pumps[0] is the inlet pump, pumps[1] is the outlet pump") will save you and future-you a lot of time.
