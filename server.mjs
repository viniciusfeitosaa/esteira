/**
 * Servidor estático local.
 * HTTPS (padrão) — necessário para getUserMedia no celular fora de localhost.
 * Uso: node server.mjs          → https://IP:8443
 *      node server.mjs --http   → http://localhost:8080
 */

import http from "node:http";
import https from "node:https";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import os from "node:os";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;
const useHttp = process.argv.includes("--http");
const PORT = Number(process.env.PORT) || (useHttp ? 8080 : 8443);
const CERT_DIR = path.join(ROOT, ".certs");
const PFX_PATH = path.join(CERT_DIR, "dev.pfx");
const PFX_PASS = "esteira-dev";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".map": "application/json",
};

function localIPs() {
  const nets = os.networkInterfaces();
  const ips = [];
  for (const list of Object.values(nets)) {
    if (!list) continue;
    for (const n of list) {
      if (n.family === "IPv4" && !n.internal) ips.push(n.address);
    }
  }
  return ips;
}

function ensurePfx() {
  if (fs.existsSync(PFX_PATH)) return;
  fs.mkdirSync(CERT_DIR, { recursive: true });

  const ips = localIPs();
  const dnsNames = ["localhost", "127.0.0.1", ...ips]
    .map((d) => `'${d}'`)
    .join(",");

  const ps = `
$ErrorActionPreference = 'Stop'
$dns = @(${dnsNames})
$cert = New-SelfSignedCertificate -Subject 'CN=Esteira Dev' -DnsName $dns -KeyAlgorithm RSA -KeyLength 2048 -CertStoreLocation 'Cert:\\CurrentUser\\My' -NotAfter (Get-Date).AddYears(3) -FriendlyName 'Esteira Dev' -KeyExportPolicy Exportable
$pwd = ConvertTo-SecureString -String '${PFX_PASS}' -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath '${PFX_PATH.replace(/\\/g, "/")}' -Password $pwd | Out-Null
Write-Output 'ok'
`;

  try {
    execFileSync(
      "powershell.exe",
      ["-NoProfile", "-NonInteractive", "-Command", ps],
      { stdio: ["ignore", "pipe", "pipe"] }
    );
  } catch (err) {
    console.error("Falha ao gerar certificado SSL automático.");
    console.error(String(err.stderr || err.message || err));
    console.error("Tente: node server.mjs --http (só localhost com câmera).");
    process.exit(1);
  }

  if (!fs.existsSync(PFX_PATH)) {
    console.error("Certificado não foi criado em", PFX_PATH);
    process.exit(1);
  }
  console.log("Certificado de desenvolvimento gerado em .certs/dev.pfx");
}

function safePath(urlPath) {
  const decoded = decodeURIComponent((urlPath || "/").split("?")[0]);
  let rel = decoded === "/" ? "/index.html" : decoded;
  rel = path.normalize(rel).replace(/^(\.\.[/\\])+/, "");
  const full = path.join(ROOT, rel);
  if (!full.startsWith(ROOT)) return null;
  return full;
}

function handler(req, res) {
  const filePath = safePath(req.url);
  if (!filePath) {
    res.writeHead(400);
    res.end("Bad request");
    return;
  }

  let target = filePath;
  if (fs.existsSync(target) && fs.statSync(target).isDirectory()) {
    target = path.join(target, "index.html");
  }

  if (!fs.existsSync(target) || !fs.statSync(target).isFile()) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("404");
    return;
  }

  const ext = path.extname(target).toLowerCase();
  const type = MIME[ext] || "application/octet-stream";
  res.writeHead(200, {
    "Content-Type": type,
    "Cache-Control": "no-cache",
  });
  fs.createReadStream(target).pipe(res);
}

function printBanner(proto) {
  const host = proto === "https" ? "https" : "http";
  console.log("");
  console.log("Esteira — servidor local");
  console.log("────────────────────────");
  console.log(`PC:      ${host}://localhost:${PORT}`);
  for (const ip of localIPs()) {
    console.log(`Celular: ${host}://${ip}:${PORT}`);
  }
  if (proto === "https") {
    console.log("");
    console.log("No celular: abra o link, aceite o aviso de certificado");
    console.log('(Avançado → Continuar / "Prosseguir mesmo assim").');
  }
  console.log("");
}

if (useHttp) {
  http.createServer(handler).listen(PORT, "0.0.0.0", () => {
    printBanner("http");
  });
} else {
  ensurePfx();
  const opts = {
    pfx: fs.readFileSync(PFX_PATH),
    passphrase: PFX_PASS,
  };
  https.createServer(opts, handler).listen(PORT, "0.0.0.0", () => {
    printBanner("https");
  });
}
