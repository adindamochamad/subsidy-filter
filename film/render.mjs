#!/usr/bin/env node
/**
 * Frame-accurate 1080p render of dashboard/?film=1, muxed with mix.wav.
 */
import { chromium } from "playwright";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..");
const dashboard = path.join(repo, "dashboard", "index.html");
const mix = path.join(here, "audio", "mix.wav");
const mp4 = path.join(here, "subsidy-filter-64s.mp4");
const FPS = 30;
const DURATION = 64.0;
const FRAMES = Math.round(DURATION * FPS);

if (!fs.existsSync(mix)) {
  console.log("Building audio mix…");
  const r = spawnSync("node", [path.join(here, "audio", "build.mjs")], {
    stdio: "inherit",
    cwd: here,
  });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

if (!fs.existsSync(dashboard)) {
  console.error("Missing", dashboard, "— run make dashboard first.");
  process.exit(1);
}

const url = `file://${dashboard}?film=1`;
const browser = await chromium.launch({
  headless: true,
  args: [
    "--disable-dev-shm-usage",
    "--font-render-hinting=none",
    "--enable-font-antialiasing",
    "--hide-scrollbars",
  ],
});
const page = await browser.newPage({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
});
await page.goto(url, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);
await page.evaluate(() => window.__film.prepare());

const ff = spawn("ffmpeg", [
  "-y",
  "-f", "image2pipe",
  "-framerate", String(FPS),
  "-vcodec", "mjpeg",
  "-i", "pipe:0",
  "-i", mix,
  "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p",
  "-c:v", "libx264",
  "-preset", "slow",
  "-tune", "animation",
  "-crf", "16",
  "-profile:v", "high",
  "-pix_fmt", "yuv420p",
  "-color_primaries", "bt709",
  "-color_trc", "bt709",
  "-colorspace", "bt709",
  "-c:a", "aac",
  "-b:a", "192k",
  "-ar", "48000",
  "-ac", "2",
  "-t", String(DURATION),
  "-movflags", "+faststart",
  mp4,
], { stdio: ["pipe", "inherit", "inherit"] });

let ffErr = null;
ff.on("error", (e) => { ffErr = e; });

const t0 = Date.now();
for (let i = 0; i < FRAMES; i++) {
  const t = i / FPS;
  await page.evaluate((time) => window.__film.seek(time), t);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const buf = await page.screenshot({ type: "jpeg", quality: 95, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
  if (!ff.stdin.write(buf)) {
    await new Promise((r) => ff.stdin.once("drain", r));
  }
  if (i % 60 === 0) {
    const sec = ((Date.now() - t0) / 1000).toFixed(0);
    console.log(`frame ${i}/${FRAMES}  t=${t.toFixed(2)}s  elapsed=${sec}s`);
  }
}

ff.stdin.end();
await page.close();
await browser.close();

const code = await new Promise((resolve) => ff.on("close", resolve));
if (ffErr) {
  console.error(ffErr);
  process.exit(1);
}
if (code !== 0) {
  console.error("ffmpeg exited", code);
  process.exit(code);
}
console.log("WROTE", mp4);
