// Order 90: the multi-step countdown + ads page. Steps, timers and ad code come from the admin panel.
const config = require("../lib/config");

const esc = (s) => String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

const settings = [
  { key: "steps", label: "Number of steps (1-3)", type: "number", default: 2 },
  { key: "siteName", label: "Site name (shown at the top)", type: "text", default: "Your site" }
];
for (const n of [1, 2, 3]) {
  settings.push({ key: `wait${n}`, label: `Step ${n}: wait seconds`, type: "number", default: 10 });
  for (const p of ["head", "top", "bottom"]) {
    settings.push({ key: `ad${n}_${p}`, label: `Step ${n}: ad code (${p})`, type: "textarea", default: "" });
  }
}

const wait = (c, n) => Math.max(0, Number(c[`wait${n}`]) || 0);
const ad = (c, n, p) => c[`ad${n}_${p}`] || (n === 1 ? config[`AD_${p.toUpperCase()}`] || "" : "");

function render(ctx, c, n, steps) {
  const ts = Date.now();
  const sig = ctx.sign(ctx.code, n, ts);
  const W = wait(c, n);
  const last = n >= steps;
  const dots = Array.from({ length: steps }, (_, i) =>
    `<i style="background:${i < n ? "var(--accent)" : "var(--off)"}"></i>`).join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${esc(c.siteName)}</title>
${ad(c, n, "head")}
<style>
:root{--bg:#f5f6f8;--card:#fff;--text:#1b1f27;--muted:#6b7280;--accent:#1a6dff;--off:#b9c4d6}
@media(prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--text:#e8ebf0;--muted:#98a1b0;--accent:#4d8dff;--off:#3a4455}}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;display:flex;flex-direction:column;align-items:center;padding:16px;gap:20px}
.brand{display:flex;align-items:center;gap:8px;font-weight:600}.brand svg{width:22px;height:22px;stroke:var(--accent);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.card{width:100%;max-width:440px;background:var(--card);border-radius:14px;padding:28px 22px;text-align:center}
.dots{display:flex;justify-content:center;gap:6px;margin-bottom:14px}.dots i{width:8px;height:8px;border-radius:50%}
h1{font-size:1.1rem;margin:0 0 4px}p{margin:0 0 14px;color:var(--muted);font-size:.92rem}
#count{font-size:3rem;font-weight:700;line-height:1;margin:6px 0 18px}
button{width:100%;border:0;border-radius:10px;padding:14px;font-size:1rem;font-weight:600;color:#fff;background:var(--accent);cursor:pointer}
button:disabled{background:var(--off);cursor:not-allowed}.ad{width:100%;max-width:440px;text-align:center;overflow:hidden}
</style></head>
<body>
<div class="brand"><svg viewBox="0 0 24 24"><path d="M13 3L4 14h7l-1 7 9-11h-7z"/></svg>${esc(c.siteName)}</div>
<div class="ad">${ad(c, n, "top")}</div>
<div class="card">
<div class="dots">${dots}</div>
<h1>Step ${n} of ${steps}</h1>
<p>${last ? "Almost done. Wait for the timer." : "Wait for the timer, then continue."}</p>
<div id="count">${W}</div>
<button id="go" disabled>Please wait...</button>
</div>
<div class="ad">${ad(c, n, "bottom")}</div>
<script>
(function(){
  var left=${W},c=document.getElementById('count'),b=document.getElementById('go');
  var href='/api/go?code=${ctx.code}&n=${n}&t=${ts}&s=${sig}';
  function ready(){c.textContent='0';b.disabled=false;b.textContent='${last ? "Get link" : "Continue"}';}
  if(left<=0)ready();
  var timer=setInterval(function(){
    if(document.visibilityState!=='visible')return;
    left--;
    if(left<=0){clearInterval(timer);ready();}else c.textContent=left;
  },1000);
  b.addEventListener('click',function(){if(!b.disabled)location.href=href;});
})();
</script>
</body></html>`;
}

module.exports = {
  name: "ad-flow",
  title: "Ad flow",
  description: "Countdown pages with ads. Each step has its own timer and ad code.",
  order: 90,
  settings,

  async handle(ctx, c) {
    const steps = Math.min(3, Math.max(1, Math.round(Number(c.steps) || 1)));
    const q = ctx.query;
    let step = 1;

    if (q.s) {
      const done = Number(q.n), ts = Number(q.t);
      const age = (Date.now() - ts) / 1000;
      const valid = Number.isInteger(done) && done >= 1 && done <= steps && Number.isFinite(ts) &&
        ctx.safeEq(ctx.sign(ctx.code, done, ts), String(q.s)) &&
        age >= Math.max(0, wait(c, done) - 1) && age <= 900;

      if (!valid) return ctx.redirect(`/${ctx.code}`);

      if (done >= steps) {
        await ctx.inc("clicks");
        await ctx.emit("complete");
        return ctx.redirect(ctx.link.url);
      }
      step = done + 1;
    }
    return ctx.html(render(ctx, c, step, steps));
  }
};
