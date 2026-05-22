# Run your first notebook

This walkthrough takes about five minutes. By the end, you'll have discovered the devices on your lab, run one pump command, and read a temperature from a densitometer.

## 1. Sign in

Open `/jupyter/` in a browser. Authelia gates the page — sign in with the credentials your admin issued, and JupyterLab loads behind it. Create a new Python 3 notebook from the launcher (File → New → Notebook).

## 2. Find your lab's name

Open `/` in another tab. The **Registered labs** panel shows every lab the server knows about. Your lab's pill says ONLINE if its SerialHop is currently connected. The lab name on the card is what you pass to `LabDevicesClient(user=…)`. From the notebook you can also list them:

```python
from bioexperiment_suite.interfaces import LabDevicesClient

LabDevicesClient.list_registered_users()    # every lab the server knows about
LabDevicesClient.list_active_users()        # the subset currently online
```

## 3. Connect and discover devices

```python
client = LabDevicesClient(user="<your-lab>")
devices = client.discover()
print(devices)
# DiscoveredDevices(pumps=[...], densitometers=[...], valves=[...], discovered_at=...)
```

`discover()` asks SerialHop to re-probe every serial port and return a fresh device list. `devices.pumps`, `devices.densitometers`, and `devices.valves` give you the device objects you'll call methods on for the rest of the session.

> [!NOTE]
> Discovery is destructive — it re-probes serial ports and rebuilds SerialHop's device cache. If a colleague might be in the middle of a measurement, use `client.list_devices()` instead — it returns the cached list without disturbing anything.

## 4. Drive a pump

```python
pump = devices.pumps[0]
pump.set_default_flow_rate(1)        # ml/min
pump.start_continuous_rotation(1)    # direction
pump.stop_continuous_rotation()
```

Each call returns once the device acknowledges, so you can chain commands in a single cell without worrying about timing. The full recipe set lives in [Working with devices](/docs/researcher/working-with-devices).

## 5. Read from a densitometer

```python
densitometer = devices.densitometers[0]
densitometer.get_temperature()
# 22.4
```

`get_temperature()` returns degrees Celsius. For optical density readings see the recipe in [Working with devices](/docs/researcher/working-with-devices) — that call takes a few seconds because the device needs to settle.

## Where to next

- [Working with devices](/docs/researcher/working-with-devices) for more recipes.
- [Composing experiments](/docs/researcher/experiments) for chaining steps into a protocol.
- [Troubleshooting](/docs/researcher/troubleshooting) if `discover()` came back empty or any call raised.
