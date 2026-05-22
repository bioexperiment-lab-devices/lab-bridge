# Composing experiments

One-off device calls are fine for exploration. For a real experiment you usually chain steps — set up the devices, run a sequence, record results, tear down. `bioexperiment_suite.experiment` is the place for that.

## Minimal example

```python
from bioexperiment_suite.interfaces import LabDevicesClient

client = LabDevicesClient(user="<your-lab>")
devices = client.discover()
pump = devices.pumps[0]
densitometer = devices.densitometers[0]

pump.set_default_flow_rate(1.0)
pump.pour_in_volume(5.0)
od = densitometer.measure_optical_density()
print({"od": od})
```

This is "an experiment by hand" — just a notebook cell. For long-running protocols (timed steps, branches, error handling), the `experiment/` module gives you a structured composition layer; see the upstream repo for the canonical entry points.

## Reference notebook

A full reference experiment notebook (multi-step protocol, results, plotting) lives in the `bio_tools` repo at [`bio_tools/examples/experiment_example.ipynb`](https://github.com/khamitovdr/bio_tools/blob/main/examples/experiment_example.ipynb). Clone it, drop it into your JupyterLab workspace, and adapt to your devices.

## Notebook hygiene

- One notebook per experiment. Don't reuse a notebook across days — clarity beats cleverness.
- Save outputs to the same directory as the notebook. JupyterLab persists across sessions.
- Note your lab name in the first cell. Future-you will thank you.

## When discover takes too long

`discover()` is destructive — every call re-probes the serial ports. For an iterative session (write code, run, tweak), call `discover()` once at the start, then reuse the returned `devices` object. If the device set changes mid-session (someone plugged something in), call `client.list_devices()` to refresh from SerialHop's cache without forcing another re-probe.
