// Order 90: Multi-step countdown + ads page
// UI redesigned as: Verify -> Read -> Get link
// Backend flow, timers, signatures and admin ad settings remain unchanged.

const config = require("../lib/config");

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[m]));

const settings = [
  {
    key: "steps",
    label: "Number of steps (1-3)",
    type: "number",
    default: 2
  },
  {
    key: "siteName",
    label: "Site name (shown at the top)",
    type: "text",
    default: "Your site"
  }
];

for (const n of [1, 2, 3]) {
  settings.push({
    key: `wait${n}`,
    label: `Step ${n}: wait seconds`,
    type: "number",
    default: 10
  });

  for (const p of ["head", "top", "bottom"]) {
    settings.push({
      key: `ad${n}_${p}`,
      label: `Step ${n}: ad code (${p})`,
      type: "textarea",
      default: ""
    });
  }
}

const wait = (c, n) =>
  Math.max(0, Number(c[`wait${n}`]) || 0);

const ad = (c, n, p) =>
  c[`ad${n}_${p}`] ||
  (n === 1 ? config[`AD_${p.toUpperCase()}`] || "" : "");

function render(ctx, c, n, steps) {
  const ts = Date.now();
  const sig = ctx.sign(ctx.code, n, ts);
  const W = wait(c, n);
  const last = n >= steps;

  /*
   * Step labels:
   * 1 = Verify
   * 2 = Read
   * 3 = Get link
   */
  const stepLabels = ["Verify", "Read", "Get link"];

  const indicators = Array.from(
    { length: steps },
    (_, i) => {
      const stepNumber = i + 1;

      let state = "upcoming";

      if (stepNumber < n) {
        state = "done";
      } else if (stepNumber === n) {
        state = "active";
      }

      return `
        <div class="step-item ${state}">
          <div class="step-circle">
            ${state === "done" ? "✓" : stepNumber}
          </div>
          <div class="step-label">
            ${esc(stepLabels[i] || `Step ${stepNumber}`)}
          </div>
        </div>
        ${
          stepNumber < steps
            ? `<div class="step-line"></div>`
            : ""
        }
      `;
    }
  ).join("");

  const title =
    n === 1
      ? "Check you're human"
      : n === steps
        ? "Almost done"
        : "Please continue";

  const description =
    n === 1
      ? "Wait for the timer, then continue."
      : last
        ? "Almost done. Wait for the timer."
        : "Wait for the timer, then continue.";

  const buttonText = last ? "GET LINK" : "CONTINUE";

  return `<!doctype html>
<html lang="en">

<head>
<meta charset="utf-8">

<meta name="viewport"
      content="width=device-width,
      initial-scale=1,
      maximum-scale=1">

<meta name="robots" content="noindex">

<title>${esc(c.siteName)}</title>

${ad(c, n, "head")}

<style>

:root{
  --bg:#f7f6fb;
  --card:#ffffff;
  --text:#17142d;
  --muted:#777487;
  --accent:#6252d9;
  --accent-light:#f0edff;
  --line:#ddd9ea;
  --off:#d9d6e3;
  --button:#6252d9;
}

*{
  box-sizing:border-box;
}

html,body{
  margin:0;
  padding:0;
  min-height:100%;
}

body{
  min-height:100vh;
  background:
    linear-gradient(
      180deg,
      #faf9fd 0%,
      #f5f3fa 100%
    );

  color:var(--text);

  font-family:
    system-ui,
    -apple-system,
    "Segoe UI",
    Roboto,
    Arial,
    sans-serif;

  display:flex;
  flex-direction:column;
  align-items:center;

  padding:22px 15px 35px;

  -webkit-font-smoothing:antialiased;
}

/* TOP BRAND */

.brand{
  width:100%;
  max-width:460px;

  display:flex;
  align-items:center;
  justify-content:center;

  gap:9px;

  font-size:16px;
  font-weight:700;

  color:var(--text);

  margin-bottom:14px;
}

.brand-icon{
  width:34px;
  height:34px;

  border-radius:10px;

  background:var(--accent-light);

  display:flex;
  align-items:center;
  justify-content:center;

  color:var(--accent);
}

.brand-icon svg{
  width:19px;
  height:19px;

  stroke:currentColor;
  fill:none;
  stroke-width:2.2;

  stroke-linecap:round;
  stroke-linejoin:round;
}

/* MAIN CARD */

.card{
  width:100%;
  max-width:460px;

  background:var(--card);

  border:1px solid rgba(35,25,70,.07);

  border-radius:22px;

  padding:
    26px 20px
    24px;

  text-align:center;

  box-shadow:
    0 10px 35px rgba(47,38,91,.06);
}

/* STEPS */

.steps{
  width:100%;

  display:flex;
  align-items:flex-start;
  justify-content:center;

  margin-bottom:30px;

  overflow:hidden;
}

.step-item{
  min-width:58px;

  display:flex;
  flex-direction:column;
  align-items:center;

  position:relative;

  z-index:2;
}

.step-circle{
  width:30px;
  height:30px;

  border-radius:50%;

  display:flex;
  align-items:center;
  justify-content:center;

  font-size:13px;
  font-weight:800;

  background:#f0eef5;
  color:#8d899b;
}

.step-label{
  margin-top:7px;

  font-size:12px;

  font-weight:600;

  white-space:nowrap;

  color:#9b97a7;
}

.step-item.active .step-circle{
  background:var(--accent);
  color:#fff;

  box-shadow:
    0 0 0 5px rgba(98,82,217,.10);
}

.step-item.active .step-label{
  color:var(--accent);
  font-weight:800;
}

.step-item.done .step-circle{
  background:var(--accent);
  color:#fff;
}

.step-item.done .step-label{
  color:var(--text);
}

.step-line{
  height:2px;

  width:44px;

  margin-top:14px;

  background:var(--line);
}

.step-item.done + .step-line{
  background:var(--accent);
}

/* ICON */

.hero-icon{
  width:74px;
  height:74px;

  margin:0 auto 17px;

  border-radius:22px;

  background:var(--accent-light);

  display:flex;
  align-items:center;
  justify-content:center;

  color:var(--accent);
}

.hero-icon svg{
  width:38px;
  height:38px;

  stroke:currentColor;
  fill:none;

  stroke-width:1.8;

  stroke-linecap:round;
  stroke-linejoin:round;
}

/* TITLE */

h1{
  margin:0;

  font-size:30px;

  line-height:1.15;

  letter-spacing:-.5px;

  font-weight:800;
}

.description{
  margin:10px auto 0;

  max-width:350px;

  color:var(--muted);

  font-size:14px;

  line-height:1.55;
}

/* TIMER */

.timer{
  margin:23px 0 18px;
}

#count{
  font-size:58px;

  line-height:1;

  font-weight:800;

  letter-spacing:-2px;

  color:var(--text);
}

/* AD */

.ad{
  width:100%;

  max-width:460px;

  text-align:center;

  overflow:hidden;

  margin:17px auto;

  min-height:0;
}

.card .ad{
  margin-top:22px;
  margin-bottom:19px;
}

/*
 * The ad container is intentionally separated
 * from the navigation button.
 */

.ad-label{
  display:block;

  font-size:10px;

  color:#aaa6b4;

  margin-bottom:6px;

  letter-spacing:.3px;
}

/* BUTTON */

button{
  width:100%;

  min-height:54px;

  border:0;

  border-radius:13px;

  padding:15px 18px;

  font-size:15px;

  font-weight:800;

  letter-spacing:.2px;

  color:#fff;

  background:var(--button);

  cursor:pointer;

  transition:
    transform .15s ease,
    opacity .15s ease,
    background .15s ease;
}

button:not(:disabled):active{
  transform:scale(.985);
}

button:disabled{
  background:#dddce5;

  color:#aaa8b2;

  cursor:not-allowed;
}

/* SMALL NOTE */

.note{
  margin-top:16px;

  color:#8b8797;

  font-size:12px;

  line-height:1.5;
}

/* MOBILE */

@media(max-width:380px){

  body{
    padding:15px 10px 28px;
  }

  .card{
    padding:22px 15px;
    border-radius:19px;
  }

  h1{
    font-size:26px;
  }

  #count{
    font-size:52px;
  }

  .step-line{
    width:28px;
  }

  .step-item{
    min-width:52px;
  }

  .step-label{
    font-size:11px;
  }
}

</style>
</head>

<body>

<!-- BRAND -->

<div class="brand">

  <div class="brand-icon">

    <svg viewBox="0 0 24 24">
      <path d="M13 3L4 14h7l-1 7 9-11h-7z"/>
    </svg>

  </div>

  <span>${esc(c.siteName)}</span>

</div>


<!-- MAIN CARD -->

<div class="card">

  <!-- STEP INDICATOR -->

  <div class="steps">
    ${indicators}
  </div>


  <!-- HERO ICON -->

  <div class="hero-icon">

    <svg viewBox="0 0 24 24">

      <path d="M12 3l7 3v5c0 4.8-3 8-7 10
               -4-2-7-5.2-7-10V6l7-3z"/>

      <path d="M9 12l2 2 4-4"/>

    </svg>

  </div>


  <!-- TITLE -->

  <h1>${esc(title)}</h1>

  <p class="description">
    ${esc(description)}
  </p>


  <!-- TIMER -->

  <div class="timer">
    <div id="count">${W}</div>
  </div>


  <!-- AD AREA -->

  <div class="ad">
    ${ad(c, n, "top")}
  </div>


  <!-- BUTTON -->

  <button id="go" disabled>
    Please wait...
  </button>


  <div class="note">
    ${
      last
        ? "Your link will be ready when the timer finishes."
        : "Please wait until the timer finishes to continue."
    }
  </div>


  <!-- SECOND AD AREA -->

  <div class="ad">
    ${ad(c, n, "bottom")}
  </div>

</div>


<script>

(function(){

  var left = ${W};

  var c = document.getElementById("count");
  var b = document.getElementById("go");

  var href =
    '/api/go?code=${ctx.code}&n=${n}&t=${ts}&s=${sig}';


  function ready(){

    c.textContent = "0";

    b.disabled = false;

    b.textContent =
      "${buttonText}";
  }


  if(left <= 0){

    ready();

  }


  var timer = setInterval(function(){

    /*
     * Pause countdown when the page
     * is not visible.
     */

    if(document.visibilityState !== "visible"){
      return;
    }

    left--;

    if(left <= 0){

      clearInterval(timer);

      ready();

    }else{

      c.textContent = left;

    }

  },1000);


  b.addEventListener("click",function(){

    if(!b.disabled){

      location.href = href;

    }

  });

})();

</script>

</body>
</html>`;
}

module.exports = {

  name: "ad-flow",

  title: "Ad flow",

  description:
    "Countdown pages with ads. Each step has its own timer and ad code.",

  order: 90,

  settings,

  async handle(ctx, c) {

    const steps =
      Math.min(
        3,
        Math.max(
          1,
          Math.round(Number(c.steps) || 1)
        )
      );

    const q = ctx.query;

    let step = 1;


    if(q.s){

      const done = Number(q.n);
      const ts = Number(q.t);

      const age =
        (Date.now() - ts) / 1000;

      const valid =
        Number.isInteger(done) &&
        done >= 1 &&
        done <= steps &&
        Number.isFinite(ts) &&

        ctx.safeEq(
          ctx.sign(
            ctx.code,
            done,
            ts
          ),
          String(q.s)
        ) &&

        age >=
          Math.max(
            0,
            wait(c, done) - 1
          ) &&

        age <= 900;


      if(!valid){

        return ctx.redirect(`/${ctx.code}`);

      }


      if(done >= steps){

        await ctx.inc("clicks");

        await ctx.emit("complete");

        return ctx.redirect(ctx.link.url);

      }


      step = done + 1;

    }


    return ctx.html(
      render(
        ctx,
        c,
        step,
        steps
      )
    );

  }

};
