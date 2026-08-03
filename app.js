(() => {
  "use strict";

  const video = document.getElementById("video");
  const overlay = document.getElementById("overlay");
  const processCanvas = document.getElementById("process");
  const viewport = document.getElementById("viewport");
  const statusText = document.getElementById("statusText");
  const countValue = document.getElementById("countValue");
  const visibleValue = document.getElementById("visibleValue");
  const fpsValue = document.getElementById("fpsValue");

  const btnStart = document.getElementById("btnStart");
  const btnPause = document.getElementById("btnPause");
  const btnReset = document.getElementById("btnReset");
  const btnTogglePanel = document.getElementById("btnTogglePanel");
  const panelBody = document.getElementById("panelBody");

  const thresholdEl = document.getElementById("threshold");
  const minAreaEl = document.getElementById("minArea");
  const maxAreaEl = document.getElementById("maxArea");
  const linePosEl = document.getElementById("linePos");
  const matchDistEl = document.getElementById("matchDist");
  const invertEl = document.getElementById("invert");
  const showMaskEl = document.getElementById("showMask");
  const directionEl = document.getElementById("direction");

  const thresholdLabel = document.getElementById("thresholdLabel");
  const minAreaLabel = document.getElementById("minAreaLabel");
  const maxAreaLabel = document.getElementById("maxAreaLabel");
  const linePosLabel = document.getElementById("linePosLabel");
  const matchDistLabel = document.getElementById("matchDistLabel");

  const octx = overlay.getContext("2d", { alpha: true });
  const pctx = processCanvas.getContext("2d", {
    willReadFrequently: true,
    alpha: false,
  });

  /** Processamento em resolução reduzida para performance em celular */
  const PROC_W = 320;

  let stream = null;
  let running = false;
  let counting = false;
  let totalCount = 0;
  let tracks = [];
  let nextTrackId = 1;
  let rafId = 0;
  let lastTs = 0;
  let fpsEma = 0;
  let procH = 180;

  const cfg = {
    threshold: 140,
    minArea: 40,
    maxArea: 4000,
    linePos: 0.5,
    matchDist: 28,
    invert: false,
    showMask: false,
    direction: "ltr",
  };

  function bindLabels() {
    thresholdLabel.textContent = String(cfg.threshold);
    minAreaLabel.textContent = String(cfg.minArea);
    maxAreaLabel.textContent = String(cfg.maxArea);
    linePosLabel.textContent = String(Math.round(cfg.linePos * 100));
    matchDistLabel.textContent = String(cfg.matchDist);
  }

  function readControls() {
    cfg.threshold = Number(thresholdEl.value);
    cfg.minArea = Number(minAreaEl.value);
    cfg.maxArea = Number(maxAreaEl.value);
    cfg.linePos = Number(linePosEl.value) / 100;
    cfg.matchDist = Number(matchDistEl.value);
    cfg.invert = invertEl.checked;
    cfg.showMask = showMaskEl.checked;
    cfg.direction = directionEl.value;
    if (cfg.minArea > cfg.maxArea) {
      cfg.maxArea = cfg.minArea;
      maxAreaEl.value = String(cfg.maxArea);
    }
    bindLabels();
  }

  [
    thresholdEl,
    minAreaEl,
    maxAreaEl,
    linePosEl,
    matchDistEl,
    invertEl,
    showMaskEl,
    directionEl,
  ].forEach((el) => el.addEventListener("input", readControls));

  function setStatus(msg) {
    statusText.textContent = msg;
  }

  function updateHud(visible = 0) {
    countValue.textContent = String(totalCount);
    visibleValue.textContent = String(visible);
    fpsValue.textContent = fpsEma ? fpsEma.toFixed(0) : "—";
  }

  function isHorizontal() {
    return cfg.direction === "ltr" || cfg.direction === "rtl";
  }

  /** Extrai blobs conectados (4-vizinhos) de uma imagem binária */
  function findBlobs(mask, width, height, minArea, maxArea) {
    const visited = new Uint8Array(width * height);
    const blobs = [];

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const i = y * width + x;
        if (!mask[i] || visited[i]) continue;

        let sumX = 0;
        let sumY = 0;
        let area = 0;
        const stack = [i];
        visited[i] = 1;

        while (stack.length) {
          const idx = stack.pop();
          const cx = idx % width;
          const cy = (idx / width) | 0;
          sumX += cx;
          sumY += cy;
          area++;

          const neighbors = [
            idx - 1,
            idx + 1,
            idx - width,
            idx + width,
          ];
          for (const n of neighbors) {
            if (n < 0 || n >= visited.length) continue;
            if (visited[n] || !mask[n]) continue;
            const nx = n % width;
            // impede wrap horizontal
            if (Math.abs(nx - cx) > 1) continue;
            visited[n] = 1;
            stack.push(n);
          }
        }

        if (area < minArea || area > maxArea) continue;
        blobs.push({
          x: sumX / area,
          y: sumY / area,
          area,
        });
      }
    }
    return blobs;
  }

  function axisValue(pt) {
    return isHorizontal() ? pt.x : pt.y;
  }

  function lineCoordinate(width, height) {
    return isHorizontal() ? width * cfg.linePos : height * cfg.linePos;
  }

  function crossesForward(prev, curr, line) {
    const a = axisValue(prev);
    const b = axisValue(curr);
    if (cfg.direction === "ltr" || cfg.direction === "ttb") {
      return a < line && b >= line;
    }
    return a > line && b <= line;
  }

  function matchTracks(blobs) {
    const maxDist = cfg.matchDist;
    const assignedBlob = new Set();
    const nextTracks = [];

    for (const track of tracks) {
      let best = -1;
      let bestDist = maxDist;
      for (let i = 0; i < blobs.length; i++) {
        if (assignedBlob.has(i)) continue;
        const dx = blobs[i].x - track.x;
        const dy = blobs[i].y - track.y;
        const d = Math.hypot(dx, dy);
        if (d < bestDist) {
          bestDist = d;
          best = i;
        }
      }

      if (best >= 0) {
        const b = blobs[best];
        assignedBlob.add(best);
        nextTracks.push({
          id: track.id,
          x: b.x,
          y: b.y,
          prevX: track.x,
          prevY: track.y,
          age: track.age + 1,
          counted: track.counted,
          missed: 0,
        });
      } else if (track.missed < 3) {
        nextTracks.push({
          ...track,
          missed: track.missed + 1,
        });
      }
    }

    for (let i = 0; i < blobs.length; i++) {
      if (assignedBlob.has(i)) continue;
      const b = blobs[i];
      nextTracks.push({
        id: nextTrackId++,
        x: b.x,
        y: b.y,
        prevX: b.x,
        prevY: b.y,
        age: 1,
        counted: false,
        missed: 0,
      });
    }

    tracks = nextTracks;
  }

  function countCrossings(line) {
    for (const track of tracks) {
      if (track.counted || track.missed > 0) continue;
      if (track.age < 2) continue;
      if (
        crossesForward(
          { x: track.prevX, y: track.prevY },
          { x: track.x, y: track.y },
          line
        )
      ) {
        track.counted = true;
        totalCount += 1;
      }
    }
  }

  function drawOverlay(blobs, line, procW, procHLocal) {
    const w = overlay.width;
    const h = overlay.height;
    octx.clearRect(0, 0, w, h);

    const sx = w / procW;
    const sy = h / procHLocal;

    // linha de contagem
    octx.strokeStyle = "rgba(242, 212, 92, 0.95)";
    octx.lineWidth = Math.max(2, w * 0.004);
    octx.setLineDash([10, 8]);
    octx.beginPath();
    if (isHorizontal()) {
      const x = line * sx;
      octx.moveTo(x, 0);
      octx.lineTo(x, h);
    } else {
      const y = line * sy;
      octx.moveTo(0, y);
      octx.lineTo(w, y);
    }
    octx.stroke();
    octx.setLineDash([]);

    // setas de direção
    octx.fillStyle = "rgba(242, 212, 92, 0.85)";
    octx.font = `${Math.max(12, w * 0.03)}px system-ui, sans-serif`;
    const label =
      {
        ltr: "→",
        rtl: "←",
        ttb: "↓",
        btt: "↑",
      }[cfg.direction] || "→";
    if (isHorizontal()) {
      octx.fillText(label, line * sx + 8, 28);
    } else {
      octx.fillText(label, 12, line * sy - 8);
    }

    for (const b of blobs) {
      const x = b.x * sx;
      const y = b.y * sy;
      const r = Math.max(4, Math.sqrt(b.area) * 0.35 * ((sx + sy) / 2));
      octx.beginPath();
      octx.arc(x, y, r, 0, Math.PI * 2);
      octx.strokeStyle = "rgba(62, 207, 142, 0.95)";
      octx.lineWidth = 2;
      octx.stroke();
      octx.fillStyle = "rgba(62, 207, 142, 0.35)";
      octx.fill();
    }

    for (const t of tracks) {
      if (t.missed > 0) continue;
      const x = t.x * sx;
      const y = t.y * sy;
      octx.fillStyle = t.counted
        ? "rgba(242, 212, 92, 0.95)"
        : "rgba(232, 240, 234, 0.9)";
      octx.beginPath();
      octx.arc(x, y, 3, 0, Math.PI * 2);
      octx.fill();
    }
  }

  function processFrame(ts) {
    if (!running) return;
    rafId = requestAnimationFrame(processFrame);

    if (video.readyState < 2) return;

    const vw = video.videoWidth;
    const vh = video.videoHeight;
    if (!vw || !vh) return;

    const aspect = vh / vw;
    procH = Math.max(1, Math.round(PROC_W * aspect));
    if (processCanvas.width !== PROC_W || processCanvas.height !== procH) {
      processCanvas.width = PROC_W;
      processCanvas.height = procH;
    }

    const displayW = viewport.clientWidth;
    const displayH = viewport.clientHeight;
    if (overlay.width !== displayW || overlay.height !== displayH) {
      overlay.width = displayW;
      overlay.height = displayH;
    }

    pctx.drawImage(video, 0, 0, PROC_W, procH);
    const image = pctx.getImageData(0, 0, PROC_W, procH);
    const data = image.data;
    const mask = new Uint8Array(PROC_W * procH);
    const thr = cfg.threshold;

    for (let i = 0, p = 0; i < data.length; i += 4, p++) {
      // luminância aproximada
      const y = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
      const on = cfg.invert ? y < thr : y > thr;
      mask[p] = on ? 1 : 0;
      if (cfg.showMask) {
        const v = on ? 255 : 0;
        data[i] = v;
        data[i + 1] = v;
        data[i + 2] = v;
      }
    }

    if (cfg.showMask) {
      pctx.putImageData(image, 0, 0);
      octx.clearRect(0, 0, overlay.width, overlay.height);
      octx.drawImage(processCanvas, 0, 0, overlay.width, overlay.height);
    }

    const scale = (PROC_W * procH) / (640 * 360);
    const minA = Math.max(3, Math.round(cfg.minArea * scale));
    const maxA = Math.max(minA + 1, Math.round(cfg.maxArea * scale));
    const blobs = findBlobs(mask, PROC_W, procH, minA, maxA);

    if (counting) {
      matchTracks(blobs);
      const line = lineCoordinate(PROC_W, procH);
      countCrossings(line);
    } else {
      tracks = [];
    }

    if (!cfg.showMask) {
      const line = lineCoordinate(PROC_W, procH);
      drawOverlay(blobs, line, PROC_W, procH);
    } else {
      // redesenha linha sobre a máscara
      const line = lineCoordinate(PROC_W, procH);
      const sx = overlay.width / PROC_W;
      const sy = overlay.height / procH;
      octx.strokeStyle = "rgba(242, 212, 92, 0.95)";
      octx.lineWidth = 2;
      octx.setLineDash([8, 6]);
      octx.beginPath();
      if (isHorizontal()) {
        octx.moveTo(line * sx, 0);
        octx.lineTo(line * sx, overlay.height);
      } else {
        octx.moveTo(0, line * sy);
        octx.lineTo(overlay.width, line * sy);
      }
      octx.stroke();
      octx.setLineDash([]);
    }

    if (lastTs) {
      const fps = 1000 / Math.max(1, ts - lastTs);
      fpsEma = fpsEma ? fpsEma * 0.85 + fps * 0.15 : fps;
    }
    lastTs = ts;
    updateHud(blobs.length);
  }

  async function startCamera() {
    if (stream) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("Navegador sem suporte a câmera");
      return;
    }

    btnStart.disabled = true;
    setStatus("Pedindo acesso à câmera…");

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });
      video.srcObject = stream;
      await video.play();
      viewport.classList.add("live");
      running = true;
      counting = true;
      btnPause.disabled = false;
      btnReset.disabled = false;
      btnPause.textContent = "Pausar contagem";
      btnStart.textContent = "Câmera ativa";
      setStatus("Contando…");
      lastTs = 0;
      rafId = requestAnimationFrame(processFrame);
    } catch (err) {
      console.error(err);
      stream = null;
      btnStart.disabled = false;
      const name = err && err.name ? err.name : "Error";
      if (name === "NotAllowedError") {
        setStatus("Permissão de câmera negada");
      } else if (name === "NotFoundError") {
        setStatus("Nenhuma câmera encontrada");
      } else {
        setStatus("Falha ao abrir a câmera");
      }
    }
  }

  function stopCamera() {
    running = false;
    counting = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    video.srcObject = null;
    viewport.classList.remove("live");
    octx.clearRect(0, 0, overlay.width, overlay.height);
    tracks = [];
    btnStart.disabled = false;
    btnStart.textContent = "Iniciar câmera";
    btnPause.disabled = true;
    btnPause.textContent = "Pausar contagem";
    setStatus("Câmera desligada");
    updateHud(0);
  }

  btnStart.addEventListener("click", () => {
    if (stream) {
      stopCamera();
    } else {
      startCamera();
    }
  });

  btnPause.addEventListener("click", () => {
    if (!stream) return;
    counting = !counting;
    if (!counting) tracks = [];
    btnPause.textContent = counting ? "Pausar contagem" : "Retomar contagem";
    setStatus(counting ? "Contando…" : "Contagem pausada");
  });

  btnReset.addEventListener("click", () => {
    totalCount = 0;
    tracks = [];
    updateHud(Number(visibleValue.textContent) || 0);
  });

  btnTogglePanel.addEventListener("click", () => {
    const open = btnTogglePanel.getAttribute("aria-expanded") === "true";
    btnTogglePanel.setAttribute("aria-expanded", open ? "false" : "true");
    panelBody.hidden = open;
  });

  window.addEventListener("beforeunload", () => {
    if (stream) stopCamera();
  });

  readControls();
  updateHud(0);
  setStatus("Pronto — inicie a câmera");
})();
