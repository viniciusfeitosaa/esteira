/**
 * Testes do parser YOLO (sem ORT / sem modelo).
 */
import {
  parseYoloOutput,
  countGrainBoxes,
  nms,
  GRAIN_CLASS_IDS,
} from "../yolo-assist.mjs";
import { resolveCrossingCountAsync } from "../assist.mjs";

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function caseParseEmpty() {
  const anchors = 10;
  const nc = 7;
  const channels = 4 + nc;
  const data = new Float32Array(channels * anchors); // zeros → nada acima do conf
  const boxes = parseYoloOutput(
    { data, dims: [1, channels, anchors] },
    { conf: 0.25, nc }
  );
  assert(boxes.length === 0, `expected 0 boxes, got ${boxes.length}`);
  return { name: "yolo_parse_empty", ok: true };
}

function caseParseOneGrain() {
  const anchors = 4;
  const nc = 7;
  const channels = 4 + nc;
  const data = new Float32Array(channels * anchors);
  const i = 1;
  data[0 * anchors + i] = 160; // cx
  data[1 * anchors + i] = 160; // cy
  data[2 * anchors + i] = 40; // w
  data[3 * anchors + i] = 20; // h
  data[(4 + 2) * anchors + i] = 0.9; // Clean
  const boxes = parseYoloOutput(
    { data, dims: [1, channels, anchors] },
    { conf: 0.25, nc }
  );
  assert(boxes.length === 1, `expected 1, got ${boxes.length}`);
  assert(boxes[0].cls === 2, `cls Clean=2, got ${boxes[0].cls}`);
  const c = countGrainBoxes(boxes);
  assert(c.n === 1, `grain count ${c.n}`);
  return { name: "yolo_parse_one_clean", ok: true };
}

function caseForeignMatterExcluded() {
  const boxes = [
    { cls: 6, score: 0.99, x1: 0, y1: 0, x2: 10, y2: 10 },
    { cls: 2, score: 0.8, x1: 20, y1: 20, x2: 30, y2: 30 },
  ];
  const c = countGrainBoxes(boxes);
  assert(c.n === 1, `foreign excluded, got ${c.n}`);
  assert(GRAIN_CLASS_IDS.has(2) && !GRAIN_CLASS_IDS.has(6), "class map");
  return { name: "yolo_exclude_foreign", ok: true };
}

function caseNmsMerges() {
  const boxes = [
    { score: 0.9, x1: 0, y1: 0, x2: 10, y2: 10, cls: 2 },
    { score: 0.8, x1: 1, y1: 1, x2: 11, y2: 11, cls: 2 },
    { score: 0.7, x1: 50, y1: 50, x2: 60, y2: 60, cls: 0 },
  ];
  const k = nms(boxes, 0.5);
  assert(k.length === 2, `nms keep 2, got ${k.length}`);
  return { name: "yolo_nms", ok: true };
}

async function caseAsyncFallsToStub() {
  const r = await resolveCrossingCountAsync(
    { area: 400, w: 30, h: 15 },
    { medianArea: 80, hits: 5, age: 5 },
    "doubt",
    null
  );
  assert(r.source === "stub", `expected stub, got ${r.source}`);
  assert(r.n >= 2, `stub N, got ${r.n}`);
  return { name: "async_fallback_stub", ok: true, got: r.n };
}

async function caseAsyncUsesYolo() {
  const r = await resolveCrossingCountAsync(
    { area: 400, w: 30, h: 15 },
    { medianArea: 80, hits: 5, age: 5 },
    "doubt",
    async () => ({ n: 3, conf: 0.8, source: "yolo", ms: 12 })
  );
  assert(r.source === "yolo" && r.n === 3, `yolo n=3, got ${r.source}/${r.n}`);
  return { name: "async_uses_yolo", ok: true };
}

const cases = [
  caseParseEmpty,
  caseParseOneGrain,
  caseForeignMatterExcluded,
  caseNmsMerges,
  caseAsyncFallsToStub,
  caseAsyncUsesYolo,
];

let failed = 0;
for (const run of cases) {
  try {
    const r = await run();
    console.log(`PASS  ${r.name}${r.got != null ? `  got=${r.got}` : ""}`);
  } catch (e) {
    failed += 1;
    console.error(`FAIL  ${e.message}`);
  }
}
console.log("---");
console.log(`YOLO assist: ${cases.length - failed}/${cases.length} ok`);
if (failed) process.exit(1);
