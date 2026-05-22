# Researcher guide

lab-bridge runs your experiments out of a shared JupyterLab notebook environment. The `bioexperiment_suite` Python package is preinstalled — you import it, find your lab by name, discover its devices, and drive the hardware over the chisel tunnel. There's no per-researcher install; every notebook lives in the same environment, so you can pick up where a colleague left off without setting anything up.

This guide is task-oriented. It walks you through a first successful notebook, gives you copy-pasteable recipes for the common device operations, shows how to compose those calls into an experiment, and tells you where to look when something doesn't respond. It is not an API reference — method signatures and the full exception hierarchy live in the `bioexperiment_suite` repo.

## Where things live

- **JupyterLab** — `/jupyter/`. Sign in with the credentials your admin issued.
- **Your lab's name** — visible on `/` (the home page) once you're signed in, in the "Registered labs" panel. The name is what you pass to `LabDevicesClient(user=…)`.
- **Live agent logs** — `/grafana/d/lab-bridge-client-logs/lab-client-logs?var-client=<your-lab>`. Use this when something feels off mid-experiment.

## Reading order

- [Run your first notebook](/docs/researcher/first-notebook) — your first 5-minute success.
- [Working with devices](/docs/researcher/working-with-devices) — common recipes for pumps, densitometers, and valves.
- [Composing experiments](/docs/researcher/experiments) — composing multi-step protocols.
- [Troubleshooting](/docs/researcher/troubleshooting) — what to do when something doesn't respond.

## Where the library lives

Source, full API, and release notes for `bioexperiment_suite` are at [`khamitovdr/bioexperiment_suite`](https://github.com/khamitovdr/bioexperiment_suite); the example experiment notebook lives in `bio_tools` and is linked from the [Composing experiments](/docs/researcher/experiments) page.
