# Live streaming

When a lab operator allows streaming on their bench, you can watch the
experiment live from your browser.

## Watch a lab

1. Click "Live streams" in the navbar (or visit `/streamer/labs`).
2. Pick the lab you want to watch. Labs without armed streams are greyed
   out — ask the operator to enable a camera.
3. The lab page shows one tile per camera. Streams start automatically
   when you open the page and stop within ~5 seconds of you leaving.

## What you'll see

- One tile per camera ("translation"). Each tile shows the camera label
  and a connection state badge (`connecting…`, `live`, `retrying`, or
  `ended`).
- Use the video controls for fullscreen and picture-in-picture.
- If a stream ends mid-experiment, the page auto-retries 3 times with
  backoff. After that, click the tile to manually retry.

## Limits

- Up to 3 viewers per camera at the same time.
- Video only — no audio in v1.
- Streams are live-only — nothing is recorded.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Lab is greyed out | Operator hasn't armed any camera yet. |
| Tile stuck on "connecting…" | Your network may be blocking UDP ports 50000–50100. Try a different network. |
| Tile shows "ended" | Operator stopped allowing this camera, or the lab disconnected. |
