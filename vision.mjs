/**
 * Núcleo de visão clássica (testável em Node, reutilizável no browser).
 * Esteira preta + grãos claros — sem ML.
 */

export function boxBlur(src, width, height, radius) {
  if (radius <= 0) return src;
  const tmp = new Float32Array(width * height);
  const out = new Float32Array(width * height);
  const r = radius;
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

export function roiBounds(width, height, roiFrac, direction) {
  const horizontal = direction === "ltr" || direction === "rtl";
  if (horizontal) {
    const band = height * roiFrac;
    const y0 = Math.max(0, Math.floor((height - band) / 2));
    const y1 = Math.min(height, Math.ceil(y0 + band));
    return { x0: 0, x1: width, y0, y1 };
  }
  const band = width * roiFrac;
  const x0 = Math.max(0, Math.floor((width - band) / 2));
  const x1 = Math.min(width, Math.ceil(x0 + band));
  return { x0, x1, y0: 0, y1: height };
}

export function applyRoi(mask, width, height, roi) {
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (x < roi.x0 || x >= roi.x1 || y < roi.y0 || y >= roi.y1) {
        mask[y * width + x] = 0;
      }
    }
  }
}

export function percentileInRoi(lum, width, height, roi, p) {
  const samples = [];
  const step = Math.max(
    1,
    Math.floor(((roi.x1 - roi.x0) * (roi.y1 - roi.y0)) / 4000)
  );
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

export function erode(src, width, height) {
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

export function dilate(src, width, height) {
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

export function morphOpenClose(mask, width, height, rounds) {
  if (rounds <= 0) return mask;
  let src = mask;
  for (let r = 0; r < Math.min(rounds, 2); r++) src = erode(src, width, height);
  for (let r = 0; r < Math.min(rounds, 2); r++) src = dilate(src, width, height);
  if (rounds >= 3) {
    src = erode(src, width, height);
    if (rounds >= 4) src = erode(src, width, height);
    src = dilate(src, width, height);
  }
  return src;
}

export function buildMask(lum, width, height, roi, cfg) {
  const n = width * height;
  const mask = new Uint8Array(n);
  const thr = cfg.threshold;
  const invert = !!cfg.invert;
  const mode = cfg.mode || "contrast";

  if (mode === "absolute") {
    for (let p = 0; p < n; p++) {
      mask[p] = (invert ? lum[p] < thr : lum[p] > thr) ? 1 : 0;
    }
  } else if (mode === "local") {
    const local = boxBlur(lum, width, height, 7);
    for (let p = 0; p < n; p++) {
      const on = invert ? lum[p] < local[p] - thr : lum[p] > local[p] + thr;
      mask[p] = on ? 1 : 0;
    }
  } else {
    const belt = percentileInRoi(lum, width, height, roi, 0.18);
    const cut = belt + thr;
    for (let p = 0; p < n; p++) {
      mask[p] = (invert ? lum[p] < belt - thr : lum[p] > cut) ? 1 : 0;
    }
  }

  applyRoi(mask, width, height, roi);
  return morphOpenClose(mask, width, height, cfg.morph ?? 1);
}

export function findBlobs(mask, width, height, minArea, maxArea) {
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
      if (aspect > 4.5) continue;

      const fill = area / (bw * bh);
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

export function isHorizontal(direction) {
  return direction === "ltr" || direction === "rtl";
}

export function lineCoordinate(width, height, linePos, direction) {
  return isHorizontal(direction) ? width * linePos : height * linePos;
}

export function axisValue(pt, direction) {
  return isHorizontal(direction) ? pt.x : pt.y;
}

export function crossesForward(prev, curr, line, direction) {
  const a = axisValue(prev, direction);
  const b = axisValue(curr, direction);
  if (direction === "ltr" || direction === "ttb") return a < line && b >= line;
  return a > line && b <= line;
}

/**
 * Tracking simples entre frames (estado mutável em `state`).
 * state = { tracks, nextTrackId }
 */
export function matchTracks(blobs, state, matchDist) {
  const tracks = state.tracks;
  const assignedBlob = new Set();
  const nextTracks = [];

  for (const track of tracks) {
    let best = -1;
    let bestDist = matchDist;
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
        age: track.age + 1,
        counted: track.counted,
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
      id: state.nextTrackId++,
      x: b.x,
      y: b.y,
      prevX: b.x,
      prevY: b.y,
      age: 1,
      counted: false,
      missed: 0,
      hits: 1,
    });
  }

  state.tracks = nextTracks;
  return nextTracks;
}

export function countCrossings(tracks, line, direction, now, events) {
  let added = 0;
  for (const track of tracks) {
    if (track.counted || track.missed > 0) continue;
    if (track.age < 2 || (track.hits || 0) < 2) continue;
    if (
      crossesForward(
        { x: track.prevX, y: track.prevY },
        { x: track.x, y: track.y },
        line,
        direction
      )
    ) {
      track.counted = true;
      added += 1;
      if (events) events.push(now);
    }
  }
  return added;
}

/** Detecta blobs em um frame de luminância. */
export function detectBlobs(lum, width, height, cfg) {
  const blurred = boxBlur(lum, width, height, 1);
  const roi = roiBounds(width, height, cfg.roi ?? 0.55, cfg.direction || "ltr");
  const mask = buildMask(blurred, width, height, roi, cfg);
  const scale = (width * height) / (640 * 360);
  const minA = Math.max(2, Math.round((cfg.minArea ?? 25) * scale));
  const maxA = Math.max(minA + 1, Math.round((cfg.maxArea ?? 2500) * scale));
  const blobs = findBlobs(mask, width, height, minA, maxA);
  return { mask, blobs, roi, blurred };
}

/** Gera luminância sintética: fundo escuro + elipses claras. */
export function synthesizeFrame(width, height, grains, opts = {}) {
  const belt = opts.belt ?? 28;
  const grainLum = opts.grainLum ?? 200;
  const noise = opts.noise ?? 4;
  const lum = new Float32Array(width * height);
  for (let i = 0; i < lum.length; i++) {
    lum[i] = belt + (Math.random() - 0.5) * noise;
  }
  for (const g of grains) {
    const rx = g.rx ?? 4;
    const ry = g.ry ?? 2.5;
    const x0 = Math.max(0, Math.floor(g.x - rx - 1));
    const x1 = Math.min(width - 1, Math.ceil(g.x + rx + 1));
    const y0 = Math.max(0, Math.floor(g.y - ry - 1));
    const y1 = Math.min(height - 1, Math.ceil(g.y + ry + 1));
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const nx = (x - g.x) / rx;
        const ny = (y - g.y) / ry;
        if (nx * nx + ny * ny <= 1) {
          lum[y * width + x] = grainLum + (Math.random() - 0.5) * noise;
        }
      }
    }
  }
  return lum;
}

export const DEFAULT_CFG = {
  mode: "contrast",
  threshold: 38,
  minArea: 25,
  maxArea: 2500,
  linePos: 0.5,
  roi: 0.7,
  matchDist: 36,
  morph: 1,
  invert: false,
  direction: "ltr",
  countMode: "belt",
};
