/**
 * Tests do assistente (dúvida + stub).
 */
import {
  assessDoubt,
  stubArbitrate,
  resolveCrossingCount,
  blobStats,
} from "../assist.mjs";

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function caseDoubtLarge() {
  const d = assessDoubt(
    { area: 300, w: 20, h: 12 },
    { medianArea: 80 }
  );
  assert(d.doubtful, "large should be doubtful");
  assert(d.reasons.includes("large_cluster"), "expected large_cluster");
  return { name: "doubt_large_cluster", ok: true };
}

function caseStubSplitsCluster() {
  const v = stubArbitrate(
    { area: 320, w: 28, h: 14 },
    { medianArea: 90 }
  );
  assert(v.n >= 2, `stub should split, got ${v.n}`);
  assert(v.source === "stub", "source stub");
  return { name: "stub_split_cluster", ok: true, got: v.n };
}

function caseStubRejectTiny() {
  const v = stubArbitrate(
    { area: 20, w: 5, h: 4 },
    { medianArea: 90 }
  );
  assert(v.n === 0, `tiny should be 0, got ${v.n}`);
  return { name: "stub_reject_tiny", ok: true };
}

function caseAssistOffClassic() {
  const r = resolveCrossingCount(
    { area: 400, w: 30, h: 15 },
    { medianArea: 80 },
    "off"
  );
  assert(r.n === 1 && r.source === "classic", "off must stay classic +1");
  return { name: "assist_off_classic", ok: true };
}

function caseAssistDoubtUsesStub() {
  const r = resolveCrossingCount(
    { area: 400, w: 30, h: 15 },
    { medianArea: 80, hits: 5, age: 5 },
    "doubt"
  );
  assert(r.doubtful, "should be doubtful");
  assert(r.n >= 2, `doubt stub should count N, got ${r.n}`);
  return { name: "assist_doubt_stub_n", ok: true, got: r.n };
}

function caseBlobStats() {
  const s = blobStats([
    { area: 10 },
    { area: 20 },
    { area: 30 },
  ]);
  assert(s.medianArea === 20, `median got ${s.medianArea}`);
  return { name: "blob_stats_median", ok: true };
}

const cases = [
  caseDoubtLarge,
  caseStubSplitsCluster,
  caseStubRejectTiny,
  caseAssistOffClassic,
  caseAssistDoubtUsesStub,
  caseBlobStats,
];

let failed = 0;
for (const run of cases) {
  try {
    const r = run();
    console.log(`PASS  ${r.name}${r.got != null ? `  got=${r.got}` : ""}`);
  } catch (e) {
    failed += 1;
    console.error(`FAIL  ${e.message}`);
  }
}
console.log("---");
console.log(`Assist: ${cases.length - failed}/${cases.length} ok`);
if (failed) process.exit(1);
