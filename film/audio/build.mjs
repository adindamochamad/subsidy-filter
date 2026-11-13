#!/usr/bin/env node
/**
 * Build mix.wav: macOS Daniel VO on an editorial score, loudness-matched.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const DUR = 64.0;
const VOICE = "Daniel";
const RATE = "148";

const lines = [
  {
    t: 0.25,
    text:
      "August twenty twenty-six. Two hundred fifteen thousand six hundred nine reported. " +
      "Sixty-three thousand one hundred thirty-four besides HOT. Twenty-nine percent.",
  },
  {
    t: 9.5,
    text:
      "game dot hot dot tee gee was number one on three hundred seventy-five of three hundred seventy-six days.",
  },
  { t: 17.5, text: "At two point five times the trailing median, six days flag." },
  { t: 26.5, text: "Move the cut to two point four. Sixteenth February joins them." },
  {
    t: 36.5,
    text:
      "February Net Demand is still three point five million. Excluding HOT, the top fifty receivers " +
      "name less than one percent of fifteenth February signers. Most of that day stays unnamed.",
  },
  {
    t: 50.5,
    text:
      "For a long-term thesis, quote a quiet month. Rebuild this page from NEAR's public transaction table.",
  },
];

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  if (r.status !== 0) {
    console.error(`FAILED ${cmd} ${args.join(" ")}`);
    process.exit(r.status ?? 1);
  }
}

const scorePy = path.join(here, "score.py");
run("python3", [scorePy]);

const wavs = [];
lines.forEach((line, i) => {
  const aiff = path.join(here, `line-${i}.aiff`);
  const wav = path.join(here, `line-${i}.wav`);
  run("say", ["-v", VOICE, "-r", RATE, "-o", aiff, line.text]);
  run("ffmpeg", ["-y", "-i", aiff, "-ar", "48000", "-ac", "1", wav], { stdio: "inherit" });
  wavs.push({ wav, delayMs: Math.round(line.t * 1000) });
});

const score = path.join(here, "score.wav");
const mix = path.join(here, "mix.wav");
const inputs = ["-y", "-i", score];
wavs.forEach((v) => inputs.push("-i", v.wav));

const filters = [];
filters.push("[0:a]volume=0.26[sc]");
wavs.forEach((v, i) => {
  filters.push(
    `[${i + 1}:a]aformat=sample_rates=48000:channel_layouts=mono,adelay=${v.delayMs}:all=1,volume=1.22[v${i}]`,
  );
});
const mixInputs = ["[sc]", ...wavs.map((_, i) => `[v${i}]`)].join("");
filters.push(
  `${mixInputs}amix=inputs=${wavs.length + 1}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.90,atrim=0:${DUR},asetpts=PTS-STARTPTS[a]`,
);

run("ffmpeg", [
  ...inputs,
  "-filter_complex",
  filters.join(";"),
  "-map",
  "[a]",
  "-ar",
  "48000",
  "-ac",
  "2",
  mix,
]);

console.log("WROTE", mix);
for (const f of fs.readdirSync(here)) {
  if (/\.(aiff|wav)$/.test(f) && f !== "mix.wav" && f !== "score.wav") {
    fs.unlinkSync(path.join(here, f));
  }
}
