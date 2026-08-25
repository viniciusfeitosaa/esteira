/**
 * Case tests sintéticos do pipeline de visão (sem câmera).
 * Uso: npm test
 */
import {
  DEFAULT_CFG,
  detectBlobs,
  synthesizeFrame,
  matchTracks,
  countCrossings,
  lineCoordinate,
} from "../vision.mjs";

const W = 360;
const H = 200;

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function cfg(over = {}) {
  return { ...DEFAULT_CFG, roi: 0.85, morph: 1, threshold: 35, ...over };
}

function placeRow(n, y, x0, gap) {
  const grains = [];
  for (let i = 0; i < n; i++) {
    grains.push({ x: x0 + i * gap, y, rx: 5, ry: 3 });
  }
  return grains;
}

function caseEmptyBelt() {
  const lum = synthesizeFrame(W, H, [], { belt: 30, noise: 3 });
  const { blobs } = detectBlobs(lum, W, H, cfg());
  assert(blobs.length === 0, `empty: esperado 0, obteve ${blobs.length}`);
  return { name: "empty_belt", ok: true, got: 0, expected: 0 };
}

function caseInstantStatic(n) {
  const grains = placeRow(n, H / 2, 40, 28);
  const lum = synthesizeFrame(W, H, grains);
  const { blobs } = detectBlobs(lum, W, H, cfg({ minArea: 8, maxArea: 4000 }));
  assert(
    blobs.length === n,
    `instant_${n}: esperado ${n}, obteve ${blobs.length}`
  );
  return { name: `instant_static_${n}`, ok: true, got: blobs.length, expected: n };
}

function caseBeltStaticNoCount() {
  // O bug do usuário: grãos parados + modo esteira → total 0 (correto)
  const grains = placeRow(8, H / 2, 50, 30);
  const state = { tracks: [], nextTrackId: 1 };
  let total = 0;
  const line = lineCoordinate(W, H, 0.5, "ltr");
  const c = cfg({ minArea: 8 });

  for (let f = 0; f < 15; f++) {
    const lum = synthesizeFrame(W, H, grains);
    const { blobs } = detectBlobs(lum, W, H, c);
    matchTracks(blobs, state, c.matchDist);
    total += countCrossings(state.tracks, line, "ltr", f, []);
  }
  assert(total === 0, `belt_static: esperado 0 cruzamentos, obteve ${total}`);
  return { name: "belt_static_no_count", ok: true, got: total, expected: 0 };
}

function caseBeltCrossing(n) {
  const state = { tracks: [], nextTrackId: 1 };
  let total = 0;
  const line = lineCoordinate(W, H, 0.5, "ltr");
  const c = cfg({ minArea: 8, matchDist: 48, morph: 0 });
  const y = H / 2;
  // espaçamento maior + faixas Y alternadas evitam fusão de blobs
  const startXs = Array.from({ length: n }, (_, i) => 20 + i * 18);
  const frames = 55;
  const speed = (W * 0.6) / frames;

  for (let f = 0; f < frames; f++) {
    const grains = startXs.map((sx, i) => ({
      x: sx + f * speed,
      y: y + ((i % 3) - 1) * 10,
      rx: 4.5,
      ry: 2.8,
    }));
    const lum = synthesizeFrame(W, H, grains, { noise: 1.5 });
    const { blobs } = detectBlobs(lum, W, H, c);
    matchTracks(blobs, state, c.matchDist);
    total += countCrossings(state.tracks, line, "ltr", f, []);
  }
  assert(
    total === n,
    `belt_cross_${n}: esperado ${n}, obteve ${total}`
  );
  return { name: `belt_crossing_${n}`, ok: true, got: total, expected: n };
}

function caseNoiseReject() {
  const lum = synthesizeFrame(W, H, [], { belt: 40, noise: 35 });
  const { blobs } = detectBlobs(lum, W, H, cfg({ minArea: 20, morph: 2 }));
  assert(blobs.length <= 2, `noise: esperado ≤2, obteve ${blobs.length}`);
  return { name: "noise_reject", ok: true, got: blobs.length, expected: "≤2" };
}

function caseDetectVsGroundTruth() {
  const n = 12;
  const grains = placeRow(n, H / 2, 35, 26);
  const lum = synthesizeFrame(W, H, grains, { grainLum: 210, belt: 25 });
  const { blobs } = detectBlobs(lum, W, H, cfg({ minArea: 6, threshold: 30 }));
  const err = Math.abs(blobs.length - n);
  assert(err <= 1, `gt_${n}: esperado ~${n}, obteve ${blobs.length}`);
  return {
    name: "detect_vs_gt_12",
    ok: true,
    got: blobs.length,
    expected: n,
    err,
  };
}

const cases = [
  caseEmptyBelt,
  () => caseInstantStatic(5),
  () => caseInstantStatic(10),
  caseBeltStaticNoCount,
  () => caseBeltCrossing(3),
  () => caseBeltCrossing(7),
  caseNoiseReject,
  caseDetectVsGroundTruth,
];

let failed = 0;
const results = [];

for (const run of cases) {
  try {
    const r = run();
    results.push(r);
    console.log(`PASS  ${r.name}  got=${r.got} expected=${r.expected}`);
  } catch (e) {
    failed += 1;
    results.push({ name: run.name || "case", ok: false, error: e.message });
    console.error(`FAIL  ${e.message}`);
  }
}

console.log("---");
console.log(
  `Resumo: ${results.filter((r) => r.ok).length}/${results.length} ok` +
    (failed ? ` · ${failed} falha(s)` : "")
);

if (failed) process.exit(1);
