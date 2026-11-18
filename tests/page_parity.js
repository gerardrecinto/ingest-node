// Runs the page's gate() on the embedded CI results for a grid of limits.
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const code = html.match(/const DATA=[\s\S]*?\n<\/script>/)[0].replace(/\n<\/script>$/, "");
const { DATA, gate } = new Function(code + "; return {DATA, gate};")();
const out = {};
for (const bw of [0, 0.1, 0.2, 0.5, 0.9]) for (const p of [0, 0.5, 1, 5]) {
  out[`${bw}|${p}`] = gate(DATA.tier, DATA.capped, bw, p).length;
}
console.log(JSON.stringify({ data: DATA, out }));
