(() => {
  "use strict";

  const STORAGE_KEY = "esteira-yolo-v1";
  const MAX_LOT_ERROR = 0.005;
  const LINE_GRAB_PX = 16;
  const MIN_AREA_FRAC = 0.03;

  const $ = (id) => document.getElementById(id);
  const yoloFrame = $("yoloFrame");
  const overlay = $("overlay");
  const viewport = $("viewport");
  const statusText = $("statusText");
  const countValue = $("countValue");
  const visibleValue = $("visibleValue");
  const rateValue = $("rateValue");
  const fpsValue = $("fpsValue");
  const sessionValue = $("sessionValue");
  const expectedLotEl = $("expectedLot");
  const errorPctValue = $("errorPctValue");
  const validationBadge = $("validationBadge");
  const btnYoloConnect = $("btnYoloConnect");
  const btnPause = $("btnPause");
  const btnReset = $("btnReset");
  const btnDrawArea = $("btnDrawArea");
  const btnClearArea = $("btnClearArea");
  const btnTogglePanel = $("btnTogglePanel");
  const panelBody = $("panelBody");
  const btnSaveCfg = $("btnSaveCfg");
  const btnLoadCfg = $("btnLoadCfg");
  const yoloServiceUrlEl = $("yoloServiceUrl");
  const directionEl = $("direction");
  const linePosEl = $("linePos");
  const linePosLabel = $("linePosLabel");
  const confEl = $("conf");
  const confLabel = $("confLabel");
  const showConfEl = $("showConf");
  const dimOutsideEl = $("dimOutside");
  const editHint = $("editHint");

  const octx = overlay.getContext("2d");

  const DEFAULTS = {
    yoloServiceUrl: "http://localhost:8765",
    direction: "rtl",
    linePos: 0.5,
    conf: 0.3,
    roi: null, // [x0, y0, x1, y1] em fracoes do frame; null = imagem inteira
    showConf: true,
    dimOutside: true,
    expectedLot: 200,
  };
  const cfg = { ...DEFAULTS };

  let ws = null;
  let connected = false;
  let paused = false;
  let lastState = null;
  let frameSize = { w: 640, h: 480 };
  let totalCount = 0;
  let lastDisplayCount = 0;
  let countEvents = [];
  let sessionStart = 0;
  let fps = 0;
  let frameLoop = 0;

  let drawMode = false;
  let dragRect = null; // {x0,y0,x1,y1} em fracoes, durante o desenho
  let draggingLine = false;

  // ------------------------------------------------------------ config

  function isVertical() {
    return cfg.direction === "ltr" || cfg.direction === "rtl";
  }

  function roiOrFull() {
    return cfg.roi || [0, 0, 1, 1];
  }

  function clampLineToRoi() {
    const [x0, y0, x1, y1] = roiOrFull();
    const lo = isVertical() ? x0 : y0;
    const hi = isVertical() ? x1 : y1;
    const pad = (hi - lo) * 0.05;
    if (cfg.linePos < lo + pad || cfg.linePos > hi - pad) cfg.linePos = (lo + hi) / 2;
  }

  function applyCfgToDOM() {
    yoloServiceUrlEl.value = cfg.yoloServiceUrl;
    directionEl.value = cfg.direction;
    linePosEl.value = String(Math.round(cfg.linePos * 100));
    linePosLabel.textContent = linePosEl.value;
    confEl.value = String(Math.round(cfg.conf * 100));
    confLabel.textContent = confEl.value;
    showConfEl.checked = cfg.showConf;
    dimOutsideEl.checked = cfg.dimOutside;
    expectedLotEl.value = String(cfg.expectedLot);
  }

  function readControls() {
    cfg.yoloServiceUrl = yoloServiceUrlEl.value.trim() || DEFAULTS.yoloServiceUrl;
    cfg.direction = directionEl.value;
    cfg.linePos = Number(linePosEl.value) / 100;
    cfg.conf = Number(confEl.value) / 100;
    cfg.showConf = showConfEl.checked;
    cfg.dimOutside = dimOutsideEl.checked;
    cfg.expectedLot = Math.max(1, Number(expectedLotEl.value) || 200);
    linePosLabel.textContent = linePosEl.value;
    confLabel.textContent = confEl.value;
  }

  function pushConfig() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({
        type: "config",
        direction: cfg.direction,
        line_pos: cfg.linePos,
        conf: cfg.conf,
        roi: roiOrFull(),
      })
    );
  }

  function saveCfg(silent = false) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
      if (!silent) setStatus("Configuração salva neste navegador");
    } catch {
      if (!silent) setStatus("Não foi possível salvar");
    }
  }

  function loadCfg() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) Object.assign(cfg, JSON.parse(raw));
    } catch {
      /* config corrompida: fica o padrao */
    }
  }

  // ------------------------------------------------------------ HUD

  function setStatus(msg) {
    statusText.textContent = msg;
  }

  function formatSession(ms) {
    const s = Math.floor(ms / 1000);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }

  function ratePerMinute(now) {
    countEvents = countEvents.filter((t) => now - t <= 60_000);
    if (countEvents.length < 2) return countEvents.length;
    const span = Math.max(1, now - countEvents[0]);
    return Math.round((countEvents.length * 60_000) / span);
  }

  function updateHud(visible) {
    const now = performance.now();
    if (totalCount !== lastDisplayCount) {
      countValue.classList.remove("bump");
      void countValue.offsetWidth;
      countValue.classList.add("bump");
      lastDisplayCount = totalCount;
    }
    countValue.textContent = String(totalCount);
    visibleValue.textContent = String(visible);
    rateValue.textContent = String(ratePerMinute(now));
    fpsValue.textContent = fps ? fps.toFixed(0) : "—";
    sessionValue.textContent = sessionStart ? formatSession(now - sessionStart) : "0:00";
  }

  function updateValidation() {
    const n = cfg.expectedLot;
    const err = Math.abs(totalCount - n) / n;
    errorPctValue.textContent = `${(err * 100).toFixed(2)}%`;
    const pass = err <= MAX_LOT_ERROR;
    validationBadge.textContent = pass ? "PASS" : "FAIL";
    validationBadge.dataset.state = pass ? "pass" : "fail";
  }

  // ------------------------------------------------------------ geometria

  function viewMap() {
    const rect = viewport.getBoundingClientRect();
    const cssW = Math.max(1, rect.width);
    const cssH = Math.max(1, rect.height);
    const scale = Math.min(cssW / frameSize.w, cssH / frameSize.h);
    const dispW = frameSize.w * scale;
    const dispH = frameSize.h * scale;
    return { rect, cssW, cssH, scale, ox: (cssW - dispW) / 2, oy: (cssH - dispH) / 2, dispW, dispH };
  }

  function fracToCss(m, fx, fy) {
    return [m.ox + fx * m.dispW, m.oy + fy * m.dispH];
  }

  function eventToFrac(ev) {
    const m = viewMap();
    const fx = (ev.clientX - m.rect.left - m.ox) / m.dispW;
    const fy = (ev.clientY - m.rect.top - m.oy) / m.dispH;
    return [Math.min(1, Math.max(0, fx)), Math.min(1, Math.max(0, fy))];
  }

  function nearLine(ev) {
    const m = viewMap();
    const [x0, y0, x1, y1] = roiOrFull();
    const px = ev.clientX - m.rect.left;
    const py = ev.clientY - m.rect.top;
    if (isVertical()) {
      const [lx, ly0] = fracToCss(m, cfg.linePos, y0);
      const [, ly1] = fracToCss(m, cfg.linePos, y1);
      return Math.abs(px - lx) <= LINE_GRAB_PX && py >= ly0 - LINE_GRAB_PX && py <= ly1 + LINE_GRAB_PX;
    }
    const [lx0, ly] = fracToCss(m, x0, cfg.linePos);
    const [lx1] = fracToCss(m, x1, cfg.linePos);
    return Math.abs(py - ly) <= LINE_GRAB_PX && px >= lx0 - LINE_GRAB_PX && px <= lx1 + LINE_GRAB_PX;
  }

  // ------------------------------------------------------------ desenho

  function render() {
    const m = viewMap();
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(m.cssW * dpr);
    const h = Math.round(m.cssH * dpr);
    if (overlay.width !== w || overlay.height !== h) {
      overlay.width = w;
      overlay.height = h;
    }
    octx.setTransform(dpr, 0, 0, dpr, 0, 0);
    octx.clearRect(0, 0, m.cssW, m.cssH);
    if (!connected) return;

    const area = dragRect ? [dragRect.x0, dragRect.y0, dragRect.x1, dragRect.y1] : roiOrFull();
    const [ax0, ay0] = fracToCss(m, Math.min(area[0], area[2]), Math.min(area[1], area[3]));
    const [ax1, ay1] = fracToCss(m, Math.max(area[0], area[2]), Math.max(area[1], area[3]));

    if (cfg.dimOutside && (cfg.roi || dragRect)) {
      octx.fillStyle = "rgba(0, 0, 0, 0.55)";
      octx.beginPath();
      octx.rect(m.ox, m.oy, m.dispW, m.dispH);
      octx.rect(ax0, ay0, ax1 - ax0, ay1 - ay0);
      octx.fill("evenodd");
    }
    if (cfg.roi || dragRect) {
      octx.strokeStyle = "#ff9f1c";
      octx.lineWidth = 2;
      octx.setLineDash(dragRect ? [6, 4] : []);
      octx.strokeRect(ax0, ay0, ax1 - ax0, ay1 - ay0);
      octx.setLineDash([]);
      octx.fillStyle = "#ff9f1c";
      octx.font = "600 12px system-ui, sans-serif";
      octx.fillText("Área de contagem", ax0 + 6, Math.max(14, ay0 - 6));
    }

    const boxes = (lastState && lastState.boxes) || [];
    octx.font = "12px ui-monospace, monospace";
    for (const b of boxes) {
      const [x, y] = fracToCss(m, b.x1 / frameSize.w, b.y1 / frameSize.h);
      const [x2, y2] = fracToCss(m, b.x2 / frameSize.w, b.y2 / frameSize.h);
      const color = b.counted ? "#5aa9ff" : "#3ecf8e";
      octx.strokeStyle = color;
      octx.lineWidth = 2;
      octx.strokeRect(x, y, x2 - x, y2 - y);
      const label = cfg.showConf ? `#${b.id} ${Math.round((b.conf || 0) * 100)}%` : `#${b.id}`;
      const tw = octx.measureText(label).width + 6;
      octx.fillStyle = "rgba(0, 0, 0, 0.6)";
      octx.fillRect(x, Math.max(0, y - 15), tw, 14);
      octx.fillStyle = color;
      octx.fillText(label, x + 3, Math.max(11, y - 4));
    }

    if (!dragRect) drawLine(m);
  }

  function drawLine(m) {
    const [x0, y0, x1, y1] = roiOrFull();
    octx.strokeStyle = draggingLine ? "#fff3a8" : "#f2d45c";
    octx.lineWidth = draggingLine ? 3 : 2;
    octx.beginPath();
    let hx;
    let hy;
    if (isVertical()) {
      const [lx, ly0] = fracToCss(m, cfg.linePos, y0);
      const [, ly1] = fracToCss(m, cfg.linePos, y1);
      octx.moveTo(lx, ly0);
      octx.lineTo(lx, ly1);
      hx = lx;
      hy = (ly0 + ly1) / 2;
    } else {
      const [lx0, ly] = fracToCss(m, x0, cfg.linePos);
      const [lx1] = fracToCss(m, x1, cfg.linePos);
      octx.moveTo(lx0, ly);
      octx.lineTo(lx1, ly);
      hx = (lx0 + lx1) / 2;
      hy = ly;
    }
    octx.stroke();
    // alca + seta do sentido de passagem
    octx.fillStyle = "#f2d45c";
    octx.beginPath();
    octx.arc(hx, hy, 7, 0, Math.PI * 2);
    octx.fill();
    const arrow = { rtl: [-1, 0], ltr: [1, 0], ttb: [0, 1], btt: [0, -1] }[cfg.direction] || [1, 0];
    const ax = hx + arrow[0] * 22;
    const ay = hy + arrow[1] * 22;
    octx.lineWidth = 2;
    octx.beginPath();
    octx.moveTo(hx + arrow[0] * 9, hy + arrow[1] * 9);
    octx.lineTo(ax, ay);
    octx.lineTo(ax - arrow[0] * 6 - arrow[1] * 5, ay - arrow[1] * 6 - arrow[0] * 5);
    octx.moveTo(ax, ay);
    octx.lineTo(ax - arrow[0] * 6 + arrow[1] * 5, ay - arrow[1] * 6 + arrow[0] * 5);
    octx.stroke();
  }

  // ------------------------------------------------------------ interacao

  function setDrawMode(on) {
    drawMode = on;
    dragRect = null;
    viewport.classList.toggle("drawing", on);
    btnDrawArea.textContent = on ? "Cancelar desenho" : "Desenhar área de contagem";
    editHint.innerHTML = on
      ? "Clique e arraste sobre o vídeo para marcar a <strong>área de contagem</strong>. Só o que estiver dentro dela vai para o YOLO."
      : "O vídeo mostra exatamente o que o YOLO detecta: caixa verde = comprimido visto, caixa azul = já contado. Arraste a <strong>linha amarela</strong> para mudar onde conta.";
    render();
  }

  function capture(ev) {
    try {
      overlay.setPointerCapture(ev.pointerId);
    } catch {
      /* ponteiro ja liberado */
    }
  }

  overlay.addEventListener("pointerdown", (ev) => {
    if (!connected) return;
    if (drawMode) {
      const [fx, fy] = eventToFrac(ev);
      dragRect = { x0: fx, y0: fy, x1: fx, y1: fy };
      capture(ev);
      ev.preventDefault();
      return;
    }
    if (nearLine(ev)) {
      draggingLine = true;
      capture(ev);
      ev.preventDefault();
      render();
    }
  });

  overlay.addEventListener("pointermove", (ev) => {
    if (!connected) return;
    if (dragRect) {
      const [fx, fy] = eventToFrac(ev);
      dragRect.x1 = fx;
      dragRect.y1 = fy;
      render();
      return;
    }
    if (draggingLine) {
      const [fx, fy] = eventToFrac(ev);
      const [x0, y0, x1, y1] = roiOrFull();
      const v = isVertical() ? fx : fy;
      const lo = isVertical() ? x0 : y0;
      const hi = isVertical() ? x1 : y1;
      cfg.linePos = Math.min(hi - 0.01, Math.max(lo + 0.01, v));
      linePosEl.value = String(Math.round(cfg.linePos * 100));
      linePosLabel.textContent = linePosEl.value;
      render();
      return;
    }
    if (!drawMode) {
      viewport.classList.toggle("grab-line", nearLine(ev));
      viewport.classList.toggle("grab-vertical", isVertical());
    }
  });

  function endPointer() {
    if (dragRect) {
      const x0 = Math.min(dragRect.x0, dragRect.x1);
      const x1 = Math.max(dragRect.x0, dragRect.x1);
      const y0 = Math.min(dragRect.y0, dragRect.y1);
      const y1 = Math.max(dragRect.y0, dragRect.y1);
      dragRect = null;
      if ((x1 - x0) * (y1 - y0) >= MIN_AREA_FRAC) {
        cfg.roi = [x0, y0, x1, y1].map((v) => Math.round(v * 1000) / 1000);
        clampLineToRoi();
        applyCfgToDOM();
        pushConfig();
        saveCfg(true);
        setStatus("Área de contagem definida");
      } else {
        setStatus("Área muito pequena — arraste um retângulo maior");
      }
      setDrawMode(false);
      return;
    }
    if (draggingLine) {
      draggingLine = false;
      pushConfig();
      saveCfg(true);
      setStatus(`Linha em ${Math.round(cfg.linePos * 100)}%`);
      render();
    }
  }
  overlay.addEventListener("pointerup", endPointer);
  overlay.addEventListener("pointercancel", endPointer);

  btnDrawArea.addEventListener("click", () => setDrawMode(!drawMode));
  btnClearArea.addEventListener("click", () => {
    cfg.roi = null;
    setDrawMode(false);
    pushConfig();
    saveCfg(true);
    setStatus("Usando a imagem inteira");
  });

  // ------------------------------------------------------------ servico

  function baseUrl() {
    return cfg.yoloServiceUrl.replace(/\/$/, "");
  }

  function wsUrl() {
    const u = new URL(baseUrl());
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    u.pathname = "/ws";
    u.search = "";
    u.hash = "";
    return u.toString();
  }

  function onState(state) {
    if (!state || state.type !== "state") return;
    const prev = totalCount;
    totalCount = Number(state.total) || 0;
    const now = performance.now();
    for (let i = 0; i < totalCount - prev; i++) countEvents.push(now);
    fps = Number(state.fps) || fps;
    frameSize = { w: state.frame_w || frameSize.w, h: state.frame_h || frameSize.h };
    paused = !!state.paused;
    lastState = state;
    updateHud((state.boxes || []).length);
    updateValidation();
    if (state.model_warning) setStatus(`YOLO: ${state.model_warning}`);
    render();
  }

  async function runFrameLoop(token) {
    while (connected && token === frameLoop) {
      const t0 = performance.now();
      try {
        const res = await fetch(`${baseUrl()}/frame.jpg?raw=1&t=${Date.now()}`, { cache: "no-store" });
        if (res.ok) {
          const url = URL.createObjectURL(await res.blob());
          const prev = yoloFrame.src;
          yoloFrame.src = url;
          yoloFrame.hidden = false;
          viewport.classList.add("live");
          if (prev && prev.startsWith("blob:")) URL.revokeObjectURL(prev);
        }
      } catch {
        /* falha transitoria */
      }
      const wait = Math.max(30, 80 - (performance.now() - t0));
      await new Promise((r) => setTimeout(r, wait));
    }
  }

  function setConnectedUI(on) {
    btnYoloConnect.textContent = on ? "Desconectar YOLO" : "Conectar YOLO";
    btnPause.disabled = !on;
    btnReset.disabled = !on;
    btnDrawArea.disabled = !on;
    btnClearArea.disabled = !on;
    viewport.classList.toggle("connected", on);
  }

  function disconnect() {
    connected = false;
    frameLoop += 1;
    if (ws) {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
      ws = null;
    }
    if (yoloFrame.src && yoloFrame.src.startsWith("blob:")) URL.revokeObjectURL(yoloFrame.src);
    yoloFrame.removeAttribute("src");
    yoloFrame.hidden = true;
    viewport.classList.remove("live");
    setDrawMode(false);
    sessionStart = 0;
    lastState = null;
    setConnectedUI(false);
    btnPause.textContent = "Pausar contagem";
    setStatus("YOLO desconectado");
    updateHud(0);
    render();
  }

  function connect() {
    readControls();
    if (connected) {
      disconnect();
      return;
    }
    setStatus("Conectando ao serviço YOLO…");
    try {
      ws = new WebSocket(wsUrl());
    } catch {
      setStatus("URL do serviço inválida");
      return;
    }
    ws.addEventListener("open", () => {
      connected = true;
      sessionStart = performance.now();
      setConnectedUI(true);
      pushConfig();
      setStatus("YOLO conectado — contando no PC");
      frameLoop += 1;
      runFrameLoop(frameLoop);
    });
    ws.addEventListener("message", (ev) => {
      try {
        onState(JSON.parse(ev.data));
      } catch {
        /* mensagem invalida */
      }
    });
    ws.addEventListener("close", () => {
      if (connected) disconnect();
    });
    ws.addEventListener("error", () => {
      setStatus(`Falha no WebSocket — o serviço está rodando em ${baseUrl()}?`);
    });
  }

  // ------------------------------------------------------------ eventos

  btnYoloConnect.addEventListener("click", connect);

  btnPause.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    paused = !paused;
    ws.send(JSON.stringify({ type: "pause", paused }));
    btnPause.textContent = paused ? "Retomar contagem" : "Pausar contagem";
    setStatus(paused ? "Contagem pausada" : "Contando no PC…");
  });

  btnReset.addEventListener("click", () => {
    totalCount = 0;
    lastDisplayCount = 0;
    countEvents = [];
    sessionStart = connected && !paused ? performance.now() : 0;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "reset" }));
    updateHud(0);
    updateValidation();
  });

  [directionEl, linePosEl, confEl].forEach((el) =>
    el.addEventListener("input", () => {
      readControls();
      if (el === directionEl) clampLineToRoi();
      applyCfgToDOM();
      pushConfig();
      render();
    })
  );
  [showConfEl, dimOutsideEl].forEach((el) =>
    el.addEventListener("change", () => {
      readControls();
      render();
    })
  );
  yoloServiceUrlEl.addEventListener("change", readControls);
  expectedLotEl.addEventListener("input", () => {
    readControls();
    updateValidation();
  });

  btnTogglePanel.addEventListener("click", () => {
    const open = btnTogglePanel.getAttribute("aria-expanded") === "true";
    btnTogglePanel.setAttribute("aria-expanded", open ? "false" : "true");
    panelBody.hidden = open;
  });

  btnSaveCfg.addEventListener("click", () => {
    readControls();
    saveCfg();
  });
  btnLoadCfg.addEventListener("click", () => {
    Object.assign(cfg, DEFAULTS);
    applyCfgToDOM();
    pushConfig();
    saveCfg(true);
    render();
    setStatus("Padrões restaurados");
  });

  window.addEventListener("resize", render);
  window.addEventListener("beforeunload", () => {
    if (connected) disconnect();
  });
  setInterval(() => {
    if (connected) updateHud((lastState && lastState.boxes ? lastState.boxes.length : 0));
  }, 1000);

  loadCfg();
  applyCfgToDOM();
  updateHud(0);
  updateValidation();
  setConnectedUI(false);
})();
