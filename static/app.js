// Trusted try-on page. Plain JS, no build step.
const $ = (id) => document.getElementById(id);
const state = { catalog: [], g: null, session: sessionStorage.getItem("tt-session"), polling: null };

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = body.detail;
    const err = new Error((d && (d.message || d)) || "Something went wrong. Try again.");
    err.status = r.status;
    err.findings = d && d.findings;
    throw err;
  }
  return body;
}

function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }

async function init() {
  state.catalog = await api("/api/catalog");
  const want = new URLSearchParams(location.search).get("g");
  state.g = state.catalog.find((x) => x.id === want) || state.catalog[0];
  renderProduct();
  showMode();
  if (state.session) setHaveStep(true);
  if (new URLSearchParams(location.search).get("demo") === "1") {  // judges' one-click story: sample figure + size check
    $("chest").value = 92; $("waist").value = 84; $("hip").value = 96;
    await checkFit();
    document.querySelector('[data-sample="asha"]').click();
  }
}

async function showMode() {
  try {
    const s = await api("/api/status");
    $("mode").innerHTML = s.mode === "live"
      ? `Try-on: <b>live, Clothsy AI</b>${s.credits != null ? `, ${s.credits} credits left` : ""}`
      : `Try-on: <b>mock</b> (no API key set; your own photo gets a pasted stand-in` +
        (s.recorded ? `, sample figures replay recorded live results)` : `)`);
  } catch { $("mode").textContent = "Try-on service status unknown"; }
}

function renderProduct() {
  const g = state.g;
  document.title = `${g.title}: Trusted try-on`;
  $("title").textContent = g.title;
  $("price").textContent = `₹${g.price.toLocaleString("en-IN")}`;
  $("about").textContent = g.about;
  $("productImg").src = `/static/garments/${g.id}.png`;
  $("productImg").alt = `${g.title}, product photo`;
  $("sizes").innerHTML = Object.keys(g.chart).map((s, i) =>
    `<label><input type="radio" name="size" value="${s}"${s === "M" ? " checked" : ""}><span id="size-${s}">${s}</span></label>`).join("");
  $("rail").innerHTML = state.catalog.map((x) =>
    `<li><a href="?g=${x.id}"${x.id === g.id ? ' aria-current="page"' : ""}><img src="/static/garments/${x.id}.png" alt=""><span>${esc(x.title)}</span></a></li>`).join("");
  resetResult();
  if ($("chest").value) checkFit();
}

function resetResult() {
  $("label").hidden = true;
  $("resultImg").hidden = $("photoImg").hidden = $("compare").hidden = true;
  $("productImg").hidden = false;
  $("frame").classList.remove("held");
  $("caption").textContent = "Product photo";
  $("steps").innerHTML = "";
  $("error").textContent = "";
}

function setHaveStep(have) {
  $("photoStep").hidden = have;
  $("haveStep").hidden = !have;
  $("again").textContent = `Try the ${state.g.title.toLowerCase()} on`;
}

async function sendPhoto(blob, sample) {
  const fd = new FormData();
  fd.append("photo", blob, "photo");
  fd.append("adult", sample || $("adult").checked ? "true" : "false");
  fd.append("consent", sample || $("consent").checked ? "true" : "false");
  const out = await api("/api/photo", { method: "POST", body: fd });
  state.session = out.session;
  sessionStorage.setItem("tt-session", out.session);
  state.photoFindings = out.findings;
  setHaveStep(true);
}

async function start(fromPhoto) {
  $("error").textContent = "";
  $("go").disabled = $("again").disabled = true;
  try {
    if (fromPhoto) {
      const file = $("photo").files[0];
      if (!file) throw new Error("Choose a photo first.");
      if (!$("adult").checked || !$("consent").checked) throw new Error("Tick both boxes first. Nothing is sent until you do.");
      await sendPhoto(file);
    }
    resetResult();
    $("steps").innerHTML = '<li class="done">Photo checked</li>';
    const { job } = await api("/api/tryon", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session: state.session, garment: state.g.id }) });
    await follow(job);
  } catch (e) {
    if (e.status === 410) forgetLocal();
    $("error").textContent = e.message;
    if (e.findings) showPhotoFindings(e.findings);
  } finally {
    $("go").disabled = $("again").disabled = false;
  }
}

function showPhotoFindings(f) {
  $("steps").innerHTML = f.map((x) => `<li class="${x.ok ? "done" : ""}">${esc(x.text)}</li>`).join("");
}

async function follow(job) {
  for (let i = 0; i < 160; i++) {
    const j = await api(`/api/tryon/${job}`);
    $("steps").innerHTML = '<li class="done">Photo checked</li>' +
      (j.replay ? `<li class="done">Recorded live result for this sample figure (${esc(j.recorded_at)}), replayed: no credit used</li>`
        : j.cached ? '<li class="done">Made earlier for this photo, shown from memory</li>' : "") +
      j.steps.map((s) => `<li class="${s.state}">${esc(s.text)}</li>`).join("");
    if (j.done) return showResult(job, j);
    await new Promise((r) => setTimeout(r, 900));
  }
  throw new Error("This is taking much longer than usual. Try again.");
}

function showResult(job, j) {
  if (j.error) { $("error").textContent = j.error.message; return; }
  const g = state.g;
  const res = $("resultImg"), photo = $("photoImg");
  res.src = `/api/tryon/${job}/image`;
  res.alt = `AI-generated preview of you wearing the ${g.title}`;
  photo.src = `/api/photo/${state.session}`;
  photo.alt = "Your photo";
  $("productImg").hidden = true;
  res.hidden = photo.hidden = false;
  $("slider").value = 100;
  photo.style.setProperty("--reveal", "100%");
  $("compare").hidden = false;
  const mock = j.mode === "mock" ? " Mock: pasted, not generated."
    : j.replay ? ` Made by the Clothsy AI API on ${j.recorded_at}, replayed.` : "";
  $("caption").textContent = `AI-generated try-on. The real fit may differ.${mock}`;

  const stamp = $("stamp");
  const verdicts = {
    shown: ["shown", "Checked", "matches the product"],
    retried: ["retried", "Checked twice", "first try was off, retried"],
    "held back": ["held", "Held back", "doesn't match the product"],
  };
  const [cls, big, small] = verdicts[j.verdict];
  stamp.className = `stamp ${cls}`;
  stamp.innerHTML = `${big}<small>${small}</small>`;
  if (j.verdict === "held back") {
    $("frame").classList.add("held");
    $("caption").innerHTML = `We don't think this preview is accurate, so it's blurred. <button class="link" type="button" id="showAnyway">Show it anyway</button>`;
    $("showAnyway").onclick = () => { $("frame").classList.remove("held"); $("caption").textContent = `AI-generated try-on, held back by our check: colours differ from the product.${mock}`; };
  }
  const photoF = (state.photoFindings || []).filter((f) => f.level !== "pass" || f.id === "light");
  $("facts").innerHTML = [...photoF, ...j.findings].map((f) => `<li class="${f.level}">${esc(f.text)}</li>`).join("");
  $("swatches").innerHTML = (j.swatches || []).map((w) =>
    `<li class="${w.found ? "found" : "missing"}"><span class="dot" style="background:${w.hex}"></span>${esc(w.name)}` +
    `<span class="visually-hidden">${w.found ? ": found" : ": missing"}</span></li>`).join("");
  state.description = j.description || "";
  describe();
  $("cant").innerHTML = j.cant_tell.map((t) => `<li>${esc(t)}</li>`).join("");
  const n = j.attempts.length;
  $("speed").textContent = j.replay
    ? `Live, on ${j.recorded_at}: ready in ${j.total_seconds} s, ${n} ${n === 1 ? "attempt" : "attempts"}. Replayed now, instantly.`
    : j.cached
    ? `Instant: this photo and item were made earlier (first time took ${j.total_seconds} s).`
    : `Ready in ${j.total_seconds} s, ${n} ${n === 1 ? "attempt" : "attempts"}` +
      (n > 1 ? ` (${j.attempts.map((a) => a.seconds + " s").join(" + ")})` : "") + ".";
  $("label").hidden = false;
  $("steps").insertAdjacentHTML("beforeend", `<li class="done">${j.verdict === "held back"
    ? "Done. This preview didn't match the product, so it's held back. The care label below says why."
    : "Done. Your preview is shown, with its care label below."}</li>`);
}

$("slider").addEventListener("input", (e) => $("photoImg").style.setProperty("--reveal", `${e.target.value}%`));
$("go").addEventListener("click", () => start(true));
$("again").addEventListener("click", () => start(false));
document.querySelectorAll("[data-sample]").forEach((b) => b.addEventListener("click", async () => {
  $("error").textContent = "";
  try {
    const blob = await (await fetch(`/static/models/${b.dataset.sample}.png`)).blob();
    await sendPhoto(blob, true);
    await start(false);
  } catch (e) { $("error").textContent = e.message; }
}));

function forgetLocal() {
  state.session = null;
  sessionStorage.removeItem("tt-session");
  setHaveStep(false);
  resetResult();
}
$("forget").addEventListener("click", async () => {
  if (state.session) await fetch(`/api/session/${state.session}`, { method: "DELETE" });
  forgetLocal();
  $("steps").innerHTML = "<li class=\"done\">Your photo and try-ons are deleted from this server.</li>";
});

// The words under the result: what we know about it, plus fit from the size chart once measurements are in.
function describe() {
  const f = state.fit;
  const fitText = f && f.size ? ` Size guide: ${f.size}, ${f.confidence} confidence. ${f.why}` : " Add your measurements to hear which size fits.";
  $("desc").textContent = (state.description || "") + fitText;
  $("sizetag").innerHTML = f && f.size
    ? `<b>${f.size}</b> <span class="conf ${f.confidence}">${f.confidence} confidence</span>`
    : '<a href="#fitHead">Add your measurements</a> to check the size chart.';
}

async function checkFit() {
  const body = {};
  for (const k of ["chest", "waist", "hip"]) if ($(k).value) body[k] = Number($(k).value);
  const r = await api("/api/fit", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ garment: state.g.id, body }) });
  state.fit = r;
  describe();
  document.querySelectorAll(".sizes span").forEach((s) => s.classList.remove("rec"));
  if (!r.size) { $("fitOut").innerHTML = `<p class="verdict">${esc(r.why)}</p>`; return; }
  $(`size-${r.size}`).classList.add("rec");
  document.querySelector(`.sizes input[value="${r.size}"]`).checked = true;
  const conf = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" }[r.confidence];
  $("fitOut").innerHTML = `<p class="verdict"><b>${r.size}</b>: ${conf}. ${esc(r.why)}</p>
    <ul class="tape">${r.rows.map((x) => tapeRow(x, r.size)).join("")}</ul>`;
}

function tapeRow(x, size) {
  const [lo, hi] = x.range, min = Math.min(lo, x.ease) - 8, max = Math.max(hi, x.ease) + 8;
  const pos = (v) => ((v - min) / (max - min)) * 100;
  return `<li class="row"><span>${x.measure}</span>
    <div class="bar" role="img" aria-label="${x.measure}: ${x.ease} cm of room in ${size}; designed for ${lo} to ${hi} cm. ${x.state}.">
      <span class="zone" style="left:${pos(lo)}%;width:${pos(hi) - pos(lo)}%"></span>
      <span class="mark" style="left:${pos(x.ease)}%"></span></div>
    <span class="note">${x.ease} cm of room (you ${x.body}, garment ${x.garment}). Designed for ${lo}–${hi} cm: ${x.state}.</span></li>`;
}
$("fitForm").addEventListener("submit", (e) => { e.preventDefault(); checkFit().catch((err) => { $("fitOut").textContent = err.message; }); });

init().catch((e) => { $("error").textContent = e.message; });
