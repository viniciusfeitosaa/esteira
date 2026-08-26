import {
  assessDoubt,
  blobStats,
  resolveCrossingCount,
  stubArbitrate,
} from "./assist.mjs";

(() => {
  "use strict";

  const STORAGE_KEY = "esteira-calib-v5";

  const video = document.getElementById("video");
  const overlay = document.getElementById("overlay");
  const processCanvas = document.getElementById("process");
  const viewport = document.getElementById("viewport");
  const statusText = document.getElementById("statusText");
  const countValue = document.getElementById("countValue");
  const visibleValue = document.getElementById("visibleValue");
  const rateValue = document.getElementById("rateValue");
  const fpsValue = document.getElementById("fpsValue");
  const sessionValue = document.getElementById("sessionValue");
  const thresholdTitle = document.getElementById("thresholdTitle");

  const btnStart = document.getElementById("btnStart");
  const btnPause = document.getElementById("btnPause");
  const btnSnap = document.getElementById("btnSnap");
  const btnAssistCheck = document.getElementById("btnAssistCheck");
  const btnReset = document.getElementById("btnReset");
  const btnTogglePanel = document.getElementById("btnTogglePanel");
  const btnSaveCfg = document.getElementById("btnSaveCfg");
  const btnLoadCfg = document.getElementById("btnLoadCfg");
  const btnAuto = document.getElementById("btnAuto");
  const panelBody = document.getElementById("panelBody");

  const countModeEl = document.getElementById("countMode");
  const assistModeEl = document.getElementById("assistMode");
  const modeEl = document.getElementById("mode");
  const thresholdEl = document.getElementById("threshold");
  const minAreaEl = document.getElementById("minArea");
  const maxAreaEl = document.getElementById("maxArea");
  const linePosEl = document.getElementById("linePos");
  const roiEl = document.getElementById("roi");
  const matchDistEl = document.getElementById("matchDist");
  const morphEl = document.getElementById("morph");
  const invertEl = document.getElementById("invert");
  const showMaskEl = document.getElementById("showMask");
  const showRoiEl = document.getElementById("showRoi");
  const directionEl = document.getElementById("direction");

  const thresholdLabel = document.getElementById("thresholdLabel");
  const minAreaLabel = document.getElementById("minAreaLabel");
  const maxAreaLabel = document.getElementById("maxAreaLabel");
  const linePosLabel = document.getElementById("linePosLabel");
  const roiLabel = document.getElementById("roiLabel");
  const matchDistLabel = document.getElementById("matchDistLabel");
  const morphLabel = document.getElementById("morphLabel");

  const octx = overlay.getContext("2d", { alpha: true });
  const pctx = processCanvas.getContext("2d", {
    willReadFrequently: true,
    alpha: false,
  });

  /** Processamento em res. reduzida (performance no celular) */
  const PROC_W = 360;

  let stream = null;
  let running = false;
  let counting = false;
  let totalCount = 0;
  let tracks = [];
  let nextTrackId = 1;
  let rafId = 0;
  let lastTs = 0;
  let fpsEma = 0;
  let procH = 200;
  let sessionStart = 0;
  let countEvents = [];
  let lastDisplayCount = 0;

  /** Último frame de luminância (para Auto calibrar) */
  let lastLum = null;
  let lastRoi = null;
  let lastProc = { w: PROC_W, h: 200 };

  let lastVisibleBlobs = 0;
  let lastBlobList = [];
  let hintCooldown = 0;
  let lastMedianArea = 0;

  const cfg = {
    countMode: "belt",
    assistMode: "off",
    mode: "contrast",
    threshold: 38,
    minArea: 25,
    maxArea: 2500,
    linePos: 0.5,
    roi: 0.55,
    matchDist: 36,
    morph: 1,
    invert: false,
    showMask: false,
    showRoi: true,
    direction: "ltr",
  };

  function applyCfgToDOM() {
    countModeEl.value = cfg.countMode || "belt";
    assistModeEl.value = cfg.assistMode || "off";
    modeEl.value = cfg.mode;
    thresholdEl.value = String(cfg.threshold);
    minAreaEl.value = String(cfg.minArea);
    maxAreaEl.value = String(cfg.maxArea);
    linePosEl.value = String(Math.round(cfg.linePos * 100));
    roiEl.value = String(Math.round(cfg.roi * 100));
    matchDistEl.value = String(cfg.matchDist);
    morphEl.value = String(cfg.morph);
    invertEl.checked = cfg.invert;
    showMaskEl.checked = cfg.showMask;
    showRoiEl.checked = cfg.showRoi;
    directionEl.value = cfg.direction;
    updateThresholdUI();
    bindLabels();
  }

  function updateThresholdUI() {
    if (cfg.mode === "absolute") {
      thresholdEl.min = "20";
      thresholdEl.max = "250";
      if (cfg.threshold < 20) cfg.threshold = 120;
      thresholdEl.value = String(cfg.threshold);
      thresholdTitle.innerHTML = `Limiar de brilho <em id="thresholdLabel">${cfg.threshold}</em>`;
    } else if (cfg.mode === "local") {
      thresholdEl.min = "2";
      thresholdEl.max = "50";
      if (cfg.threshold > 50) cfg.threshold = 12;
      thresholdEl.value = String(cfg.threshold);
      thresholdTitle.innerHTML = `Sensibilidade local <em id="thresholdLabel">${cfg.threshold}</em>`;
    } else {
      thresholdEl.min = "8";
      thresholdEl.max = "120";
      if (cfg.threshold > 120) cfg.threshold = 38;
      thresholdEl.value = String(cfg.threshold);
      thresholdTitle.innerHTML = `Contraste sobre a esteira <em id="thresholdLabel">${cfg.threshold}</em>`;
    }
  }

  function bindLabels() {
    const thr = document.getElementById("thresholdLabel");
    if (thr) thr.textContent = String(cfg.threshold);
    minAreaLabel.textContent = String(cfg.minArea);
    maxAreaLabel.textContent = String(cfg.maxArea);
    linePosLabel.textContent = String(Math.round(cfg.linePos * 100));
    roiLabel.textContent = String(Math.round(cfg.roi * 100));
    matchDistLabel.textContent = String(cfg.matchDist);
    morphLabel.textContent = String(cfg.morph);
  }

  function readControls() {
    cfg.countMode = countModeEl.value;
    cfg.assistMode = assistModeEl.value;
    cfg.mode = modeEl.value;
    cfg.threshold = Number(thresholdEl.value);
    cfg.minArea = Number(minAreaEl.value);
    cfg.maxArea = Number(maxAreaEl.value);
    cfg.linePos = Number(linePosEl.value) / 100;
    cfg.roi = Number(roiEl.value) / 100;
    cfg.matchDist = Number(matchDistEl.value);
    cfg.morph = Number(morphEl.value);
    cfg.invert = invertEl.checked;
    cfg.showMask = showMaskEl.checked;
    cfg.showRoi = showRoiEl.checked;
    cfg.direction = directionEl.value;
    if (cfg.minArea > cfg.maxArea) {
      cfg.maxArea = cfg.minArea;
      maxAreaEl.value = String(cfg.maxArea);
    }
    bindLabels();
    updateCountModeUI();
  }

  function updateCountModeUI() {
    const instant = cfg.countMode === "instant";
    if (btnSnap) btnSnap.style.display = instant ? "" : "none";
    if (btnAssistCheck) {
      const showAssistBtn = instant && cfg.assistMode === "doubt";
      btnAssistCheck.hidden = !showAssistBtn;
      btnAssistCheck.style.display = showAssistBtn ? "" : "none";
    }
    const counterLabel = document.querySelector(".counter-label");
    if (counterLabel) {
      counterLabel.textContent = instant ? "Grãos na tela" : "Total contado";
    }
  }

  function saveCfg() {
    readControls();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
      setStatus("Calibração salva");
    } catch {
      setStatus("Não foi possível salvar");
    }
  }

  function loadCfg(silent = false) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        if (!silent) setStatus("Nenhuma calibração salva");
        return false;
      }
      Object.assign(cfg, JSON.parse(raw));
      applyCfgToDOM();
      if (!silent) setStatus("Calibração restaurada");
      return true;
    } catch {
      if (!silent) setStatus("Falha ao ler calibração");
      return false;
    }
  }

  modeEl.addEventListener("change", () => {
    cfg.mode = modeEl.value;
    updateThresholdUI();
    readControls();
  });

  countModeEl.addEventListener("change", () => {
    readControls();
    tracks = [];
    if (cfg.countMode === "instant") {
      totalCount = lastVisibleBlobs;
      setStatus(
        lastVisibleBlobs
          ? `Instantâneo: ${lastVisibleBlobs} grão(s) visíveis`
          : "Instantâneo — aponte aos grãos (não precisa cruzar a linha)"
      );
    } else {
      setStatus("Esteira — só conta ao cruzar a linha amarela");
    }
    updateHud(lastVisibleBlobs);
  });

  assistModeEl.addEventListener("change", () => {
    readControls();
    setStatus(
      cfg.assistMode === "doubt"
        ? "Assistente: só dúvidas (stub — YOLO na fase 2)"
        : "Assistente off — só clássico"
    );
  });

  [
    thresholdEl,
    minAreaEl,
    maxAreaEl,
    linePosEl,
    roiEl,
    matchDistEl,
    morphEl,
    invertEl,
    showMaskEl,
    showRoiEl,
    directionEl,
  ].forEach((el) => el.addEventListener("input", readControls));

  function setStatus(msg) {
    statusText.textContent = msg;
  }

  function formatSession(ms) {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    return `${m}:${String(s % 60).padStart(2, "0")}`;
  }

  function ratePerMinute(now) {
    const windowMs = 60_000;
    countEvents = countEvents.filter((t) => now - t <= windowMs);
    if (countEvents.length < 2) return countEvents.length;
    const span = Math.max(1, now - countEvents[0]);
    return Math.round((countEvents.length * 60_000) / span);
  }

  function updateHud(visible = 0, now = performance.now()) {
    if (totalCount !== lastDisplayCount) {
      countValue.classList.remove("bump");
      void countValue.offsetWidth;
      countValue.classList.add("bump");
      lastDisplayCount = totalCount;
    }
    countValue.textContent = String(totalCount);
    visibleValue.textContent = String(visible);
    rateValue.textContent = String(ratePerMinute(now));
    fpsValue.textContent = fpsEma ? fpsEma.toFixed(0) : "—";
    if (sessionStart && counting) {
      sessionValue.textContent = formatSession(now - sessionStart);
    } else if (!sessionStart) {
      sessionValue.textContent = "0:00";
    }
  }

  function isHorizontal() {
    return cfg.direction === "ltr" || cfg.direction === "rtl";
  }

  /** Video com object-fit: contain → coordenadas de overlay */
  function containMap(srcW, srcH, dstW, dstH) {
    const scale = Math.min(dstW / srcW, dstH / srcH);
    const dispW = srcW * scale;
    const dispH = srcH * scale;
    return {
      scaleX: scale,
      scaleY: scale,
      offsetX: (dstW - dispW) / 2,
      offsetY: (dstH - dispH) / 2,
    };
  }

  function roiBounds(width, height) {
    if (isHorizontal()) {
      const band = height * cfg.roi;
      const y0 = Math.max(0, Math.floor((height - band) / 2));
      const y1 = Math.min(height, Math.ceil(y0 + band));
      return { x0: 0, x1: width, y0, y1 };
    }
    const band = width * cfg.roi;
    const x0 = Math.max(0, Math.floor((width - band) / 2));
    const x1 = Math.min(width, Math.ceil(x0 + band));
    return { x0, x1, y0: 0, y1: height };
  }

  function applyRoi(mask, width, height, roi) {
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        if (x < roi.x0 || x >= roi.x1 || y < roi.y0 || y >= roi.y1) {
          mask[y * width + x] = 0;
        }
      }
    }
  }

  function boxBlur(src, width, height, radius) {
    if (radius <= 0) return src;
    const tmp = new Float32Array(width * height);
    const out = new Float32Array(width * height);
    const r = radius;
    // horizontal
    for (let y = 0; y < height; y++) {
      let sum = 0;
      for (let x = -r; x <= r; x++) {
        const xx = Math.min(width - 1, Math.max(0, x));
        sum += src[y * width + xx];
      }
      for (let x = 0; x < width; x++) {
        tmp[y * width + x] = sum / (2 * r + 1);
        const xOut = x - r;
        const xIn = x + r + 1;
        if (xOut >= 0) sum -= src[y * width + xOut];
        else sum -= src[y * width];
        if (xIn < width) sum += src[y * width + xIn];
        else sum += src[y * width + width - 1];
      }
    }
    // vertical
    for (let x = 0; x < width; x++) {
      let sum = 0;
      for (let y = -r; y <= r; y++) {
        const yy = Math.min(height - 1, Math.max(0, y));
        sum += tmp[yy * width + x];
      }
      for (let y = 0; y < height; y++) {
        out[y * width + x] = sum / (2 * r + 1);
        const yOut = y - r;
        const yIn = y + r + 1;
        if (yOut >= 0) sum -= tmp[yOut * width + x];
        else sum -= tmp[x];
        if (yIn < height) sum += tmp[yIn * width + x];
        else sum += tmp[(height - 1) * width + x];
      }
    }
    return out;
  }

  /** Percentil de luminância na ROI (esteira costuma ser o trecho escuro) */
  function percentileInRoi(lum, width, height, roi, p) {
    const samples = [];
    const step = Math.max(1, Math.floor(((roi.x1 - roi.x0) * (roi.y1 - roi.y0)) / 4000));
    for (let y = roi.y0; y < roi.y1; y++) {
      for (let x = roi.x0; x < roi.x1; x += step) {
        samples.push(lum[y * width + x]);
      }
    }
    if (!samples.length) return 0;
    samples.sort((a, b) => a - b);
    const idx = Math.min(samples.length - 1, Math.floor(samples.length * p));
    return samples[idx];
  }

  function otsuFromHistogram(hist, total) {
    if (total <= 0) return 128;
    let sum = 0;
    for (let i = 0; i < 256; i++) sum += i * hist[i];
    let sumB = 0;
    let wB = 0;
    let maxVar = -1;
    let thr = 128;
    for (let t = 0; t < 256; t++) {
      wB += hist[t];
      if (wB === 0) continue;
      const wF = total - wB;
      if (wF === 0) break;
      sumB += t * hist[t];
      const mB = sumB / wB;
      const mF = (sum - sumB) / wF;
      const between = wB * wF * (mB - mF) * (mB - mF);
      if (between > maxVar) {
        maxVar = between;
        thr = t;
      }
    }
    return thr;
  }

  function buildMask(lum, width, height, roi) {
    const n = width * height;
    const mask = new Uint8Array(n);
    const thr = cfg.threshold;

    if (cfg.mode === "absolute") {
      for (let p = 0; p < n; p++) {
        const on = cfg.invert ? lum[p] < thr : lum[p] > thr;
        mask[p] = on ? 1 : 0;
      }
    } else if (cfg.mode === "local") {
      // média local 15×15 vs pixel: realça grãos mesmo com sombra na esteira
      const local = boxBlur(lum, width, height, 7);
      const C = thr;
      for (let p = 0; p < n; p++) {
        const on = cfg.invert
          ? lum[p] < local[p] - C
          : lum[p] > local[p] + C;
        mask[p] = on ? 1 : 0;
      }
    } else {
      // contraste: grão = esteira (percentil escuro) + offset
      const belt = percentileInRoi(lum, width, height, roi, 0.18);
      const cut = belt + thr;
      for (let p = 0; p < n; p++) {
        const on = cfg.invert ? lum[p] < belt - thr : lum[p] > cut;
        mask[p] = on ? 1 : 0;
      }
    }

    applyRoi(mask, width, height, roi);
    return morphOpenClose(mask, width, height, cfg.morph);
  }

  /** Abertura (ruído) + erosão extra opcional para separar grãos colados */
  function morphOpenClose(mask, width, height, rounds) {
    if (rounds <= 0) return mask;
    let src = mask;

    // abertura: erode → dilate
    for (let r = 0; r < Math.min(rounds, 2); r++) {
      src = erode(src, width, height);
    }
    for (let r = 0; r < Math.min(rounds, 2); r++) {
      src = dilate(src, width, height);
    }
    // separação forte se morph alto
    if (rounds >= 3) {
      src = erode(src, width, height);
      if (rounds >= 4) src = erode(src, width, height);
      src = dilate(src, width, height);
    }
    return src;
  }

  function erode(src, width, height) {
    const dst = new Uint8Array(width * height);
    for (let y = 1; y < height - 1; y++) {
      for (let x = 1; x < width - 1; x++) {
        const i = y * width + x;
        if (
          src[i] &&
          src[i - 1] &&
          src[i + 1] &&
          src[i - width] &&
          src[i + width]
        ) {
          dst[i] = 1;
        }
      }
    }
    return dst;
  }

  function dilate(src, width, height) {
    const dst = new Uint8Array(width * height);
    for (let y = 1; y < height - 1; y++) {
      for (let x = 1; x < width - 1; x++) {
        const i = y * width + x;
        if (!src[i]) continue;
        dst[i] = 1;
        dst[i - 1] = 1;
        dst[i + 1] = 1;
        dst[i - width] = 1;
        dst[i + width] = 1;
      }
    }
    return dst;
  }

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
        let minX = x;
        let maxX = x;
        let minY = y;
        let maxY = y;
        const stack = [i];
        visited[i] = 1;

        while (stack.length) {
          const idx = stack.pop();
          const cx = idx % width;
          const cy = (idx / width) | 0;
          sumX += cx;
          sumY += cy;
          area++;
          if (cx < minX) minX = cx;
          if (cx > maxX) maxX = cx;
          if (cy < minY) minY = cy;
          if (cy > maxY) maxY = cy;

          const neighbors = [idx - 1, idx + 1, idx - width, idx + width];
          for (const n of neighbors) {
            if (n < 0 || n >= visited.length) continue;
            if (visited[n] || !mask[n]) continue;
            const nx = n % width;
            if (Math.abs(nx - cx) > 1) continue;
            visited[n] = 1;
            stack.push(n);
          }
        }

        if (area < minArea || area > maxArea) continue;

        const bw = maxX - minX + 1;
        const bh = maxY - minY + 1;
        const aspect = bw > bh ? bw / bh : bh / bw;
        if (aspect > 4.5) continue; // reflexo linear / borda

        const boxArea = bw * bh;
        const fill = area / boxArea;
        // grãos de arroz preenchem razoavelmente o bounding box
        if (fill < 0.22) continue;

        blobs.push({
          x: sumX / area,
          y: sumY / area,
          area,
          w: bw,
          h: bh,
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
      const vx = track.x - track.prevX;
      const vy = track.y - track.prevY;
      const predX = track.x + vx * 0.85;
      const predY = track.y + vy * 0.85;

      for (let i = 0; i < blobs.length; i++) {
        if (assignedBlob.has(i)) continue;
        const d = Math.hypot(blobs[i].x - predX, blobs[i].y - predY);
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
          area: b.area,
          w: b.w,
          h: b.h,
          age: track.age + 1,
          counted: track.counted,
          assistStatus: track.assistStatus || null,
          missed: 0,
          hits: (track.hits || 1) + 1,
        });
      } else if (track.missed < 5) {
        nextTracks.push({
          ...track,
          x: predX,
          y: predY,
          prevX: track.x,
          prevY: track.y,
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
        area: b.area,
        w: b.w,
        h: b.h,
        age: 1,
        counted: false,
        assistStatus: null,
        missed: 0,
        hits: 1,
      });
    }

    tracks = nextTracks;
  }

  function peersNearLine(track, line) {
    let n = 0;
    for (const t of tracks) {
      if (t.id === track.id || t.missed > 0) continue;
      if (Math.abs(axisValue(t) - line) < cfg.matchDist * 0.65) n += 1;
    }
    return n;
  }

  function countCrossings(line, now) {
    for (const track of tracks) {
      if (track.counted || track.missed > 0) continue;
      if (track.age < 2 || (track.hits || 0) < 2) continue;
      if (
        !crossesForward(
          { x: track.prevX, y: track.prevY },
          { x: track.x, y: track.y },
          line
        )
      ) {
        continue;
      }

      const blob = {
        area: track.area || 0,
        w: track.w || 1,
        h: track.h || 1,
      };
      const ctx = {
        medianArea: lastMedianArea,
        nearLinePeers: peersNearLine(track, line),
        hits: track.hits || 0,
        age: track.age || 0,
      };
      const verdict = resolveCrossingCount(blob, ctx, cfg.assistMode);
      track.counted = true;
      track.assistStatus =
        verdict.source === "classic"
          ? verdict.doubtful
            ? "doubt"
            : "classic"
          : verdict.n <= 0
            ? "rejected"
            : "confirmed";

      if (verdict.n > 0) {
        totalCount += verdict.n;
        for (let k = 0; k < verdict.n; k++) countEvents.push(now);
        if (verdict.source !== "classic") {
          setStatus(
            `IA stub: ${verdict.reasons.join(",") || "ok"} → +${verdict.n}`
          );
        }
      } else if (verdict.source !== "classic") {
        setStatus(`IA stub rejeitou (${verdict.reasons.join(",")})`);
      }
    }
  }

  function drawOverlay(blobs, line, procW, procHLocal, roi) {
    const w = overlay.width;
    const h = overlay.height;
    octx.clearRect(0, 0, w, h);

    const map = containMap(procW, procHLocal, w, h);
    const toX = (x) => x * map.scaleX + map.offsetX;
    const toY = (y) => y * map.scaleY + map.offsetY;

    if (cfg.showRoi && cfg.roi < 0.99) {
      octx.fillStyle = "rgba(0, 0, 0, 0.48)";
      octx.fillRect(0, 0, w, h);
      octx.clearRect(
        toX(roi.x0),
        toY(roi.y0),
        (roi.x1 - roi.x0) * map.scaleX,
        (roi.y1 - roi.y0) * map.scaleY
      );
      // repor laterais fora do letterbox?
      // máscara: pintar fora do ROI dentro do rect do vídeo
      if (isHorizontal()) {
        octx.fillStyle = "rgba(0, 0, 0, 0.48)";
        octx.fillRect(toX(0), toY(0), procW * map.scaleX, toY(roi.y0) - toY(0));
        octx.fillRect(
          toX(0),
          toY(roi.y1),
          procW * map.scaleX,
          toY(procHLocal) - toY(roi.y1)
        );
      } else {
        octx.fillStyle = "rgba(0, 0, 0, 0.48)";
        octx.fillRect(toX(0), toY(0), toX(roi.x0) - toX(0), procHLocal * map.scaleY);
        octx.fillRect(
          toX(roi.x1),
          toY(0),
          toX(procW) - toX(roi.x1),
          procHLocal * map.scaleY
        );
      }
      octx.strokeStyle = "rgba(62, 207, 142, 0.7)";
      octx.lineWidth = 1.5;
      octx.setLineDash([4, 4]);
      octx.strokeRect(
        toX(roi.x0),
        toY(roi.y0),
        (roi.x1 - roi.x0) * map.scaleX,
        (roi.y1 - roi.y0) * map.scaleY
      );
      octx.setLineDash([]);
    }

    octx.strokeStyle = "rgba(242, 212, 92, 0.95)";
    octx.lineWidth = Math.max(2, w * 0.004);
    octx.setLineDash([10, 8]);
    octx.beginPath();
    if (isHorizontal()) {
      const x = toX(line);
      octx.moveTo(x, toY(0));
      octx.lineTo(x, toY(procHLocal));
    } else {
      const y = toY(line);
      octx.moveTo(toX(0), y);
      octx.lineTo(toX(procW), y);
    }
    octx.stroke();
    octx.setLineDash([]);

    octx.fillStyle = "rgba(242, 212, 92, 0.9)";
    octx.font = `${Math.max(12, w * 0.03)}px system-ui, sans-serif`;
    const label = { ltr: "→", rtl: "←", ttb: "↓", btt: "↑" }[cfg.direction] || "→";
    if (isHorizontal()) octx.fillText(label, toX(line) + 8, toY(0) + 28);
    else octx.fillText(label, toX(0) + 12, toY(line) - 8);

    for (const b of blobs) {
      const x = toX(b.x);
      const y = toY(b.y);
      const r = Math.max(4, Math.sqrt(b.area) * 0.38 * map.scaleX);
      const doubt =
        cfg.assistMode === "doubt"
          ? assessDoubt(b, { medianArea: lastMedianArea })
          : { doubtful: false };
      octx.beginPath();
      octx.arc(x, y, r, 0, Math.PI * 2);
      if (doubt.doubtful) {
        octx.strokeStyle = "rgba(242, 180, 60, 0.95)";
        octx.fillStyle = "rgba(242, 180, 60, 0.28)";
      } else {
        octx.strokeStyle = "rgba(62, 207, 142, 0.95)";
        octx.fillStyle = "rgba(62, 207, 142, 0.3)";
      }
      octx.lineWidth = 2;
      octx.stroke();
      octx.fill();
    }

    for (const t of tracks) {
      if (t.missed > 0) continue;
      let fill = "rgba(232, 240, 234, 0.9)";
      if (t.assistStatus === "confirmed") fill = "rgba(80, 160, 255, 0.95)";
      else if (t.assistStatus === "rejected") fill = "rgba(228, 87, 87, 0.95)";
      else if (t.counted) fill = "rgba(242, 212, 92, 0.95)";
      octx.fillStyle = fill;
      octx.beginPath();
      octx.arc(toX(t.x), toY(t.y), 3, 0, Math.PI * 2);
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
    const n = PROC_W * procH;
    const lum = new Float32Array(n);

    for (let i = 0, p = 0; i < data.length; i += 4, p++) {
      // luminância + peso no canal verde (arroz costuma ser “quente”)
      lum[p] =
        0.25 * data[i] + 0.5 * data[i + 1] + 0.15 * data[i + 2] + 0.1 * Math.max(data[i], data[i + 1], data[i + 2]);
    }

    const blurred = boxBlur(lum, PROC_W, procH, 1);
    const roi = roiBounds(PROC_W, procH);
    let mask = buildMask(blurred, PROC_W, procH, roi);

    lastLum = blurred;
    lastRoi = roi;
    lastProc = { w: PROC_W, h: procH };

    if (cfg.showMask) {
      for (let i = 0, p = 0; i < data.length; i += 4, p++) {
        const v = mask[p] ? 255 : 0;
        data[i] = v;
        data[i + 1] = v;
        data[i + 2] = v;
      }
      pctx.putImageData(image, 0, 0);
      octx.clearRect(0, 0, overlay.width, overlay.height);
      const map = containMap(PROC_W, procH, overlay.width, overlay.height);
      octx.drawImage(
        processCanvas,
        map.offsetX,
        map.offsetY,
        PROC_W * map.scaleX,
        procH * map.scaleY
      );
      // linha sobre máscara
      const line = lineCoordinate(PROC_W, procH);
      octx.strokeStyle = "rgba(242, 212, 92, 0.95)";
      octx.lineWidth = 2;
      octx.setLineDash([8, 6]);
      octx.beginPath();
      if (isHorizontal()) {
        const x = line * map.scaleX + map.offsetX;
        octx.moveTo(x, map.offsetY);
        octx.lineTo(x, map.offsetY + procH * map.scaleY);
      } else {
        const y = line * map.scaleY + map.offsetY;
        octx.moveTo(map.offsetX, y);
        octx.lineTo(map.offsetX + PROC_W * map.scaleX, y);
      }
      octx.stroke();
      octx.setLineDash([]);
    }

    // escala de área relativa ao frame de referência do slider (como se fosse ~640×360)
    const scale = (PROC_W * procH) / (640 * 360);
    const minA = Math.max(2, Math.round(cfg.minArea * scale));
    const maxA = Math.max(minA + 1, Math.round(cfg.maxArea * scale));
    const blobs = findBlobs(mask, PROC_W, procH, minA, maxA);
    const line = lineCoordinate(PROC_W, procH);
    const stats = blobStats(blobs);
    lastMedianArea = stats.medianArea;
    lastBlobList = blobs;

    if (counting) {
      if (!sessionStart) sessionStart = ts;
      if (cfg.countMode === "instant") {
        tracks = [];
        totalCount = blobs.length;
      } else {
        matchTracks(blobs);
        const before = totalCount;
        countCrossings(line, ts);
        if (
          blobs.length > 0 &&
          totalCount === before &&
          ts - hintCooldown > 4000
        ) {
          hintCooldown = ts;
          setStatus(
            `${blobs.length} detectado(s) — mova pela linha amarela para contar`
          );
        } else if (totalCount > before) {
          setStatus(`Contou +${totalCount - before} · total ${totalCount}`);
        }
      }
    } else {
      tracks = [];
    }

    lastVisibleBlobs = blobs.length;

    if (!cfg.showMask) {
      drawOverlay(blobs, line, PROC_W, procH, roi);
    }

    if (lastTs) {
      const fps = 1000 / Math.max(1, ts - lastTs);
      fpsEma = fpsEma ? fpsEma * 0.85 + fps * 0.15 : fps;
    }
    lastTs = ts;
    updateHud(blobs.length, ts);
  }

  function autoCalibrate() {
    if (!lastLum || !lastRoi) {
      setStatus("Inicie a câmera e deixe grãos na esteira");
      return;
    }
    const { w, h } = lastProc;
    const roi = lastRoi;
    const hist = new Uint32Array(256);
    let total = 0;
    const step = 1;
    for (let y = roi.y0; y < roi.y1; y += step) {
      for (let x = roi.x0; x < roi.x1; x += step) {
        const v = Math.max(0, Math.min(255, Math.round(lastLum[y * w + x])));
        hist[v]++;
        total++;
      }
    }
    const otsu = otsuFromHistogram(hist, total);
    const belt = percentileInRoi(lastLum, w, h, roi, 0.15);
    const grain = percentileInRoi(lastLum, w, h, roi, 0.85);
    const gap = Math.max(8, grain - belt);

    cfg.mode = "contrast";
    modeEl.value = "contrast";
    updateThresholdUI();
    // fica no meio do vão esteira→grão, um pouco abaixo do grão
    cfg.threshold = Math.max(10, Math.min(100, Math.round(gap * 0.42)));
    // áreas típicas: metade do que Otsu “vê”
    const sampleMask = buildMask(lastLum, w, h, roi);
    const scale = (w * h) / (640 * 360);
    const blobs = findBlobs(
      sampleMask,
      w,
      h,
      Math.max(2, Math.round(8 * scale)),
      Math.max(50, Math.round(12000 * scale))
    );

    if (blobs.length > 0) {
      const areas = blobs.map((b) => b.area).sort((a, b) => a - b);
      const med = areas[(areas.length / 2) | 0] / scale;
      cfg.minArea = Math.max(5, Math.round(med * 0.35));
      cfg.maxArea = Math.max(cfg.minArea + 50, Math.round(med * 4.5));
    } else {
      // pouca coisa detetada — limiar um pouco mais frouxo
      cfg.threshold = Math.max(8, Math.round(cfg.threshold * 0.75));
      cfg.minArea = 12;
      cfg.maxArea = 3000;
    }

    applyCfgToDOM();
    readControls();
    setStatus(
      `Auto: contraste ${cfg.threshold} · esteira~${belt.toFixed(0)} grão~${grain.toFixed(0)} (otsu ${otsu})`
    );
  }

  async function startCamera() {
    if (stream) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("Navegador sem suporte a câmera");
      return;
    }

    if (
      !window.isSecureContext &&
      location.hostname !== "localhost" &&
      location.hostname !== "127.0.0.1"
    ) {
      setStatus("Use HTTPS para câmera no celular");
    }

    btnStart.disabled = true;
    setStatus("Pedindo acesso à câmera…");

    const attempts = [
      {
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      },
      { audio: false, video: { facingMode: "environment" } },
      { audio: false, video: true },
    ];

    let lastErr = null;
    for (const constraints of attempts) {
      try {
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        break;
      } catch (err) {
        lastErr = err;
      }
    }

    if (!stream) {
      console.error(lastErr);
      btnStart.disabled = false;
      const name = lastErr && lastErr.name ? lastErr.name : "Error";
      if (name === "NotAllowedError") setStatus("Permissão de câmera negada");
      else if (name === "NotFoundError") setStatus("Nenhuma câmera encontrada");
      else if (name === "NotReadableError") setStatus("Câmera em uso por outro app");
      else setStatus("Falha ao abrir a câmera");
      return;
    }

    try {
      video.srcObject = stream;
      await video.play();
      viewport.classList.add("live");
      running = true;
      counting = true;
      sessionStart = 0;
      btnPause.disabled = false;
      btnReset.disabled = false;
      btnSnap.disabled = false;
      if (btnAssistCheck) btnAssistCheck.disabled = false;
      btnPause.textContent = "Pausar contagem";
      btnStart.disabled = false;
      btnStart.textContent = "Parar câmera";
      setStatus(
        cfg.countMode === "instant"
          ? "Instantâneo — total = grãos visíveis"
          : "Esteira — cruze a linha amarela para contar"
      );
      updateCountModeUI();
      lastTs = 0;
      rafId = requestAnimationFrame(processFrame);
    } catch (err) {
      console.error(err);
      stopCamera();
      setStatus("Falha ao iniciar o vídeo");
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
    sessionStart = 0;
    lastLum = null;
    btnStart.disabled = false;
    btnStart.textContent = "Iniciar câmera";
    btnPause.disabled = true;
    btnSnap.disabled = true;
    if (btnAssistCheck) btnAssistCheck.disabled = true;
    btnPause.textContent = "Pausar contagem";
    setStatus("Câmera desligada");
    updateHud(0);
  }

  btnStart.addEventListener("click", () => {
    if (stream) stopCamera();
    else startCamera();
  });

  btnPause.addEventListener("click", () => {
    if (!stream) return;
    counting = !counting;
    if (!counting) tracks = [];
    else sessionStart = sessionStart || performance.now();
    btnPause.textContent = counting ? "Pausar contagem" : "Retomar contagem";
    setStatus(counting ? "Contando…" : "Contagem pausada");
  });

  btnReset.addEventListener("click", () => {
    totalCount = 0;
    lastDisplayCount = 0;
    countEvents = [];
    tracks = [];
    sessionStart = counting ? performance.now() : 0;
    updateHud(Number(visibleValue.textContent) || 0);
  });

  btnSnap.addEventListener("click", () => {
    if (!stream) return;
    const n = lastVisibleBlobs;
    totalCount = n;
    setStatus(`Snapshot: ${n} grão(s) na área`);
    updateHud(n);
  });

  if (btnAssistCheck) {
    btnAssistCheck.addEventListener("click", () => {
      if (!stream || !lastBlobList.length) {
        setStatus("Nada para verificar");
        return;
      }
      const stats = blobStats(lastBlobList);
      let sum = 0;
      let adjusted = 0;
      for (const b of lastBlobList) {
        const v = stubArbitrate(b, { medianArea: stats.medianArea });
        sum += v.n;
        if (v.n !== 1) adjusted += 1;
      }
      totalCount = sum;
      setStatus(
        `IA stub: ${lastBlobList.length} blobs → ${sum} grãos (${adjusted} ajustados)`
      );
      updateHud(lastBlobList.length);
    });
  }

  btnTogglePanel.addEventListener("click", () => {
    const open = btnTogglePanel.getAttribute("aria-expanded") === "true";
    btnTogglePanel.setAttribute("aria-expanded", open ? "false" : "true");
    panelBody.hidden = open;
  });

  btnSaveCfg.addEventListener("click", saveCfg);
  btnLoadCfg.addEventListener("click", () => {
    if (!loadCfg(false)) {
      Object.assign(cfg, {
        countMode: "belt",
        assistMode: "off",
        mode: "contrast",
        threshold: 38,
        minArea: 25,
        maxArea: 2500,
        linePos: 0.5,
        roi: 0.55,
        matchDist: 36,
        morph: 1,
        invert: false,
        showMask: false,
        showRoi: true,
        direction: "ltr",
      });
      applyCfgToDOM();
      setStatus("Padrões restaurados");
    }
  });
  btnAuto.addEventListener("click", autoCalibrate);

  window.addEventListener("beforeunload", () => {
    if (stream) stopCamera();
  });

  loadCfg(true);
  if (!cfg.countMode) cfg.countMode = "belt";
  if (!cfg.assistMode) cfg.assistMode = "off";
  applyCfgToDOM();
  readControls();
  updateHud(0);
  setStatus("Pronto — inicie a câmera");
})();
