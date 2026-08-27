/**
 * Árbitro YOLO (ONNX) no browser — fase 2.
 * Fallback: quem chama usa stub se load falhar.
 */

export const GRAIN_CLASSES = [
  "Broken",
  "Chalky",
  "Clean",
  "Damaged",
  "Discolored",
  "Immature",
  "Organic Foreign Matters",
];

/** Classes que contam como grão (exclui matéria estranha). */
export const GRAIN_CLASS_IDS = new Set([0, 1, 2, 3, 4, 5]);

export const DEFAULT_MODEL_URL = "./models/grain-nano.onnx";
export const INPUT_SIZE = 320;

/**
 * Parse saída YOLOv8 Ultralytics: [1, 4+nc, N] → boxes após NMS.
 * Coordenadas em pixels do input (ex.: 320).
 */
export function parseYoloOutput(output, opts = {}) {
  const confTh = opts.conf ?? 0.25;
  const iouTh = opts.iou ?? 0.45;
  const nc = opts.nc ?? 7;
  const inputSize = opts.inputSize ?? INPUT_SIZE;

  // ort tensor: dims [1, 4+nc, anchors] ou [1, anchors, 4+nc]
  let data;
  let channels;
  let anchors;
  if (output.dims && output.dims.length === 3) {
    data = output.data;
    if (output.dims[1] === 4 + nc) {
      channels = output.dims[1];
      anchors = output.dims[2];
    } else if (output.dims[2] === 4 + nc) {
      // transpose mental: tratar como [1, anchors, channels]
      return parseYoloOutputTransposed(output.data, output.dims[1], nc, confTh, iouTh);
    } else {
      channels = output.dims[1];
      anchors = output.dims[2];
    }
  } else {
    data = output.data || output;
    channels = 4 + nc;
    anchors = (data.length / channels) | 0;
  }

  const proposals = [];
  for (let i = 0; i < anchors; i++) {
    let bestCls = 0;
    let bestScore = -1;
    for (let c = 0; c < nc; c++) {
      const s = data[(4 + c) * anchors + i];
      if (s > bestScore) {
        bestScore = s;
        bestCls = c;
      }
    }
    if (bestScore < confTh) continue;
    const cx = data[0 * anchors + i];
    const cy = data[1 * anchors + i];
    const w = data[2 * anchors + i];
    const h = data[3 * anchors + i];
    proposals.push({
      cx,
      cy,
      w,
      h,
      score: bestScore,
      cls: bestCls,
      x1: cx - w / 2,
      y1: cy - h / 2,
      x2: cx + w / 2,
      y2: cy + h / 2,
    });
  }

  const kept = nms(proposals, iouTh);
  return kept.map((b) => ({
    ...b,
    // clamp visual
    cx: Math.min(inputSize, Math.max(0, b.cx)),
    cy: Math.min(inputSize, Math.max(0, b.cy)),
  }));
}

function parseYoloOutputTransposed(data, anchors, nc, confTh, iouTh) {
  const stride = 4 + nc;
  const proposals = [];
  for (let i = 0; i < anchors; i++) {
    const off = i * stride;
    const cx = data[off];
    const cy = data[off + 1];
    const w = data[off + 2];
    const h = data[off + 3];
    let bestCls = 0;
    let bestScore = -1;
    for (let c = 0; c < nc; c++) {
      const s = data[off + 4 + c];
      if (s > bestScore) {
        bestScore = s;
        bestCls = c;
      }
    }
    if (bestScore < confTh) continue;
    proposals.push({
      cx,
      cy,
      w,
      h,
      score: bestScore,
      cls: bestCls,
      x1: cx - w / 2,
      y1: cy - h / 2,
      x2: cx + w / 2,
      y2: cy + h / 2,
    });
  }
  return nms(proposals, iouTh);
}

function iou(a, b) {
  const x1 = Math.max(a.x1, b.x1);
  const y1 = Math.max(a.y1, b.y1);
  const x2 = Math.min(a.x2, b.x2);
  const y2 = Math.min(a.y2, b.y2);
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  const ua = Math.max(0, a.x2 - a.x1) * Math.max(0, a.y2 - a.y1);
  const ub = Math.max(0, b.x2 - b.x1) * Math.max(0, b.y2 - b.y1);
  return inter / (ua + ub - inter + 1e-6);
}

export function nms(boxes, iouTh) {
  const sorted = [...boxes].sort((a, b) => b.score - a.score);
  const keep = [];
  const dead = new Set();
  for (let i = 0; i < sorted.length; i++) {
    if (dead.has(i)) continue;
    keep.push(sorted[i]);
    for (let j = i + 1; j < sorted.length; j++) {
      if (dead.has(j)) continue;
      if (iou(sorted[i], sorted[j]) > iouTh) dead.add(j);
    }
  }
  return keep;
}

export function countGrainBoxes(boxes) {
  const grains = boxes.filter((b) => GRAIN_CLASS_IDS.has(b.cls));
  const conf =
    grains.length === 0
      ? 0
      : grains.reduce((s, b) => s + b.score, 0) / grains.length;
  return { n: grains.length, conf, boxes: grains };
}

/**
 * Prepara tensor float32 CHW [1,3,S,S] a partir de ImageData RGBA (já letterbox 320).
 */
export function imageDataToTensor(imageData, size = INPUT_SIZE) {
  const { data, width, height } = imageData;
  if (width !== size || height !== size) {
    throw new Error(`Esperado ${size}x${size}, veio ${width}x${height}`);
  }
  const out = new Float32Array(3 * size * size);
  const plane = size * size;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const p = y * size + x;
      out[p] = data[i] / 255;
      out[plane + p] = data[i + 1] / 255;
      out[2 * plane + p] = data[i + 2] / 255;
    }
  }
  return out;
}

/**
 * Recorta região ao redor do blob e faz letterbox 320 com fundo preto.
 * @param {ImageData} frame — frame RGB do process canvas
 */
export function cropBlobLetterbox(frame, blob, size = INPUT_SIZE, pad = 1.8) {
  const fw = frame.width;
  const fh = frame.height;
  const bw = Math.max(8, blob.w || Math.sqrt(blob.area || 64));
  const bh = Math.max(8, blob.h || Math.sqrt(blob.area || 64));
  const side = Math.max(bw, bh) * pad;
  let x0 = Math.floor((blob.x || fw / 2) - side / 2);
  let y0 = Math.floor((blob.y || fh / 2) - side / 2);
  let x1 = Math.ceil(x0 + side);
  let y1 = Math.ceil(y0 + side);
  x0 = Math.max(0, x0);
  y0 = Math.max(0, y0);
  x1 = Math.min(fw, x1);
  y1 = Math.min(fh, y1);
  const cw = Math.max(1, x1 - x0);
  const ch = Math.max(1, y1 - y0);

  const canvas =
    typeof OffscreenCanvas !== "undefined"
      ? new OffscreenCanvas(size, size)
      : Object.assign(document.createElement("canvas"), {
          width: size,
          height: size,
        });
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, size, size);

  const scale = Math.min(size / cw, size / ch);
  const dw = cw * scale;
  const dh = ch * scale;
  const dx = (size - dw) / 2;
  const dy = (size - dh) / 2;

  // drawImage from ImageData via temp canvas
  const tmp =
    typeof OffscreenCanvas !== "undefined"
      ? new OffscreenCanvas(fw, fh)
      : Object.assign(document.createElement("canvas"), {
          width: fw,
          height: fh,
        });
  tmp.width = fw;
  tmp.height = fh;
  const tctx = tmp.getContext("2d");
  tctx.putImageData(frame, 0, 0);
  ctx.drawImage(tmp, x0, y0, cw, ch, dx, dy, dw, dh);

  return ctx.getImageData(0, 0, size, size);
}

/**
 * Letterbox do frame inteiro (modo Verificar com IA).
 */
export function frameLetterbox(frame, size = INPUT_SIZE) {
  const fw = frame.width;
  const fh = frame.height;
  const canvas =
    typeof OffscreenCanvas !== "undefined"
      ? new OffscreenCanvas(size, size)
      : Object.assign(document.createElement("canvas"), {
          width: size,
          height: size,
        });
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, size, size);
  const scale = Math.min(size / fw, size / fh);
  const dw = fw * scale;
  const dh = fh * scale;
  const dx = (size - dw) / 2;
  const dy = (size - dh) / 2;
  const tmp =
    typeof OffscreenCanvas !== "undefined"
      ? new OffscreenCanvas(fw, fh)
      : Object.assign(document.createElement("canvas"), {
          width: fw,
          height: fh,
        });
  tmp.width = fw;
  tmp.height = fh;
  const tctx = tmp.getContext("2d");
  tctx.putImageData(frame, 0, 0);
  ctx.drawImage(tmp, 0, 0, fw, fh, dx, dy, dw, dh);
  return ctx.getImageData(0, 0, size, size);
}

export function createYoloAssist(options = {}) {
  const modelUrl = options.modelUrl || DEFAULT_MODEL_URL;
  const conf = options.conf ?? 0.25;
  let session = null;
  let ort = null;
  let ready = false;
  let lastMs = 0;
  let loadError = null;

  async function load() {
    try {
      ort = await import(
        "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.3/dist/ort.web.min.mjs"
      );
      ort.env.wasm.wasmPaths =
        "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.3/dist/";
      ort.env.wasm.numThreads = 1;
      session = await ort.InferenceSession.create(modelUrl, {
        executionProviders: ["wasm"],
      });
      ready = true;
      loadError = null;
      return true;
    } catch (err) {
      ready = false;
      loadError = err && err.message ? err.message : String(err);
      console.warn("YOLO ONNX não carregou:", loadError);
      return false;
    }
  }

  function isReady() {
    return ready && !!session;
  }

  function getStatus() {
    return { ready, lastMs, loadError, modelUrl };
  }

  async function detectImageData(imageData) {
    if (!isReady()) throw new Error("Modelo não carregado");
    const tensorData = imageDataToTensor(imageData, INPUT_SIZE);
    const inputName = session.inputNames[0];
    const tensor = new ort.Tensor("float32", tensorData, [
      1,
      3,
      INPUT_SIZE,
      INPUT_SIZE,
    ]);
    const t0 = performance.now();
    const feeds = { [inputName]: tensor };
    const results = await session.run(feeds);
    lastMs = performance.now() - t0;
    const outName = session.outputNames[0];
    const out = results[outName];
    const boxes = parseYoloOutput(out, { conf, nc: 7, inputSize: INPUT_SIZE });
    return countGrainBoxes(boxes);
  }

  async function arbitrateCrop(frame, blob) {
    const crop = cropBlobLetterbox(frame, blob, INPUT_SIZE);
    const verdict = await detectImageData(crop);
    return {
      n: verdict.n,
      conf: verdict.conf,
      source: "yolo",
      ms: lastMs,
      boxes: verdict.boxes,
    };
  }

  async function arbitrateFrame(frame) {
    const lb = frameLetterbox(frame, INPUT_SIZE);
    const verdict = await detectImageData(lb);
    return {
      n: verdict.n,
      conf: verdict.conf,
      source: "yolo",
      ms: lastMs,
      boxes: verdict.boxes,
    };
  }

  return {
    load,
    isReady,
    getStatus,
    arbitrateCrop,
    arbitrateFrame,
    detectImageData,
  };
}
