(function () {
  "use strict";

  const root = document.querySelector(".streamer-lab");
  if (!root) return;
  const labName = root.dataset.lab;
  const tiles = root.querySelectorAll(".tile");

  const RETRY_BACKOFF_MS = [2000, 5000, 15000];

  function setState(tile, state) {
    const el = tile.querySelector(".state");
    el.dataset.state = state;
    el.textContent = state === "live" ? "live"
      : state === "retrying" ? "retrying…"
      : state === "ended" ? "ended"
      : "connecting…";
  }

  async function attach(tile, attempt) {
    const translationId = tile.dataset.translationId;
    setState(tile, attempt > 0 ? "retrying" : "connecting");
    const pc = new RTCPeerConnection();
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.ontrack = (e) => {
      tile.querySelector("video").srcObject = e.streams[0];
    };
    pc.onconnectionstatechange = () => {
      const cs = pc.connectionState;
      if (cs === "connected") setState(tile, "live");
      else if (cs === "failed" || cs === "closed") setState(tile, "ended");
    };

    await pc.setLocalDescription(await pc.createOffer());

    // Translation IDs are SerialHop-assigned and may contain characters
    // that are illegal in URL paths (Windows DirectShow device strings
    // routinely include '/', '?', and '\'). Encode each segment.
    const url = `/streamer/whep/${encodeURIComponent(labName)}/${encodeURIComponent(translationId)}`;
    let resp;
    try {
      resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: pc.localDescription.sdp,
      });
    } catch (e) {
      scheduleRetry(tile, attempt);
      return;
    }

    if (resp.status === 504 || resp.status === 502) {
      scheduleRetry(tile, attempt);
      return;
    }
    if (!resp.ok) {
      setState(tile, "ended");
      return;
    }

    tile.dataset.subscriberLocation = resp.headers.get("Location") || "";
    const answerSdp = await resp.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
    tile._pc = pc;
  }

  function scheduleRetry(tile, attempt) {
    if (attempt >= RETRY_BACKOFF_MS.length) {
      setState(tile, "ended");
      return;
    }
    setState(tile, "retrying");
    setTimeout(() => attach(tile, attempt + 1), RETRY_BACKOFF_MS[attempt]);
  }

  tiles.forEach((t) => attach(t, 0));

  window.addEventListener("pagehide", () => {
    tiles.forEach((t) => {
      if (t.dataset.subscriberLocation) {
        fetch(t.dataset.subscriberLocation, {
          method: "DELETE",
          keepalive: true,
        });
      }
    });
  });
})();
