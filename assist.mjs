/**
 * Assistente híbrido — dúvida + árbitro (stub na fase 1; ONNX depois).
 */

export function median(values) {
  if (!values.length) return 0;
  const a = [...values].sort((x, y) => x - y);
  const m = (a.length / 2) | 0;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

/**
 * @param {{ area: number, w?: number, h?: number }} blob
 * @param {{ medianArea: number, nearLinePeers?: number, hits?: number, age?: number }} ctx
 */
export function assessDoubt(blob, ctx = {}) {
  const reasons = [];
  const med = ctx.medianArea || 0;
  const area = blob.area || 0;
  const w = blob.w || 1;
  const h = blob.h || 1;
  const aspect = w > h ? w / h : h / w;

  if (med > 0 && area > med * 2.5) reasons.push("large_cluster");
  if (med > 0 && area > 0 && area < med * 0.4) reasons.push("tiny_noise");
  if (aspect > 3.5) reasons.push("elongated");
  if ((ctx.nearLinePeers || 0) >= 2) reasons.push("crowded_line");
  if ((ctx.hits || 0) < 3 && (ctx.age || 0) < 4) reasons.push("unstable");

  return {
    doubtful: reasons.length > 0,
    reasons,
  };
}

/**
 * Stub do YOLO: estima N grãos pela área relativa à mediana.
 * Sem modelo — heurística auditável para fase 1.
 */
export function stubArbitrate(blob, ctx = {}) {
  const med = Math.max(1, ctx.medianArea || blob.area || 1);
  const ratio = (blob.area || 0) / med;
  let n = 1;
  if (ratio >= 2.3) n = Math.min(8, Math.max(2, Math.round(ratio)));
  if (ratio < 0.35) n = 0;

  const doubt = assessDoubt(blob, ctx);
  if (doubt.reasons.includes("elongated") && ratio < 1.8) n = 0;

  return {
    n,
    conf: n === 0 ? 0.55 : Math.min(0.9, 0.5 + ratio * 0.1),
    source: "stub",
    reasons: doubt.reasons,
  };
}

/**
 * Resolve quantos contar neste cruzamento (síncrono / stub).
 * assistMode: "off" | "doubt"
 */
export function resolveCrossingCount(blob, ctx, assistMode) {
  if (!assistMode || assistMode === "off") {
    return { n: 1, source: "classic", doubtful: false, reasons: [] };
  }

  const doubt = assessDoubt(blob, ctx);
  if (assistMode === "doubt" && !doubt.doubtful) {
    return { n: 1, source: "classic", doubtful: false, reasons: [] };
  }

  const verdict = stubArbitrate(blob, { ...ctx, ...doubt });
  return {
    n: verdict.n,
    source: verdict.source,
    doubtful: true,
    reasons: verdict.reasons,
    conf: verdict.conf,
  };
}

/**
 * Versão async: se houver dúvida e `yoloArbitrate` disponível, usa YOLO no crop;
 * senão cai no stub.
 * yoloArbitrate: async (blob, ctx) => { n, conf, source, ms? }
 */
export async function resolveCrossingCountAsync(
  blob,
  ctx,
  assistMode,
  yoloArbitrate
) {
  if (!assistMode || assistMode === "off") {
    return { n: 1, source: "classic", doubtful: false, reasons: [] };
  }

  const doubt = assessDoubt(blob, ctx);
  if (assistMode === "doubt" && !doubt.doubtful) {
    return { n: 1, source: "classic", doubtful: false, reasons: [] };
  }

  if (typeof yoloArbitrate === "function") {
    try {
      const verdict = await yoloArbitrate(blob, { ...ctx, ...doubt });
      return {
        n: verdict.n,
        source: verdict.source || "yolo",
        doubtful: true,
        reasons: doubt.reasons,
        conf: verdict.conf,
        ms: verdict.ms,
      };
    } catch (err) {
      console.warn("YOLO falhou, usando stub:", err);
    }
  }

  const verdict = stubArbitrate(blob, { ...ctx, ...doubt });
  return {
    n: verdict.n,
    source: verdict.source,
    doubtful: true,
    reasons: verdict.reasons,
    conf: verdict.conf,
  };
}

/** Estatísticas de área a partir dos blobs visíveis. */
export function blobStats(blobs) {
  const areas = blobs.map((b) => b.area).filter((a) => a > 0);
  return {
    medianArea: median(areas),
    count: blobs.length,
  };
}
