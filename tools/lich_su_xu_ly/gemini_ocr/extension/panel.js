/* panel.js — UI điều khiển: test 1 file, chạy batch, chỉnh cấu hình. */

const $ = id => document.getElementById(id);
let pickedFile = null;
let resultText = "";

// ── tabs ─────────────────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach(t => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
    t.classList.add("on");
    for (const name of ["test", "batch", "cfg"]) {
      $("tab-" + name).classList.toggle("hide", name !== t.dataset.tab);
    }
    if (t.dataset.tab === "batch") refreshStats();
  });
});

const pill = (el, text, cls) => { el.textContent = text; el.className = "pill " + (cls || ""); };

// ── chọn file ────────────────────────────────────────────────────────────────
const drop = $("drop");
drop.addEventListener("click", () => $("file").click());
drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("hot"); });
drop.addEventListener("dragleave", () => drop.classList.remove("hot"));
drop.addEventListener("drop", e => {
  e.preventDefault(); drop.classList.remove("hot");
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});
$("file").addEventListener("change", e => { if (e.target.files[0]) setFile(e.target.files[0]); });

function setFile(f) {
  pickedFile = f;
  $("fileinfo").innerHTML = `<b>${f.name}</b> — ${(f.size / 1024).toFixed(0)} KB`;
  $("run").disabled = false;
}

function fileToB64(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result).split(",")[1]);
    fr.onerror = () => reject(new Error("đọc file thất bại"));
    fr.readAsDataURL(file);
  });
}

// ── chạy test 1 file ─────────────────────────────────────────────────────────
$("run").addEventListener("click", async () => {
  if (!pickedFile) return;
  $("run").disabled = true; $("dl").disabled = true;
  pill($("status"), "đang chạy…", "run");
  $("out").textContent = "⏳ Đang mở tab Gemini, đính file và chờ trả lời…";
  addLog(`▶ test: ${pickedFile.name}`);

  try {
    const b64 = await fileToB64(pickedFile);
    const res = await chrome.runtime.sendMessage({
      type: "RUN_TEST",
      name: pickedFile.name,
      mime: pickedFile.type || "application/pdf",
      b64,
      cfg: await readCfg(),
    });

    if (res?.ok) {
      resultText = res.text;
      $("out").textContent = res.text;
      $("chars").textContent = res.text.length.toLocaleString("vi-VN");
      pill($("status"), "✔ xong", "ok");
      $("dl").disabled = false;
    } else {
      $("out").textContent = "❌ " + (res?.error || "lỗi không rõ") +
        (res?.diag ? "\n\n── nhật ký engine ──\n" + res.diag : "");
      pill($("status"), "✖ lỗi", "err");
    }
  } catch (e) {
    $("out").textContent = "❌ " + e.message;
    pill($("status"), "✖ lỗi", "err");
  }
  $("run").disabled = false;
});

$("dl").addEventListener("click", () => {
  const name = pickedFile.name.replace(/\.[^.]+$/, "") + ".txt";
  const blob = new Blob([resultText], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
});

// ── batch ────────────────────────────────────────────────────────────────────
async function bridgeUrl() { return $("bridge").value.trim().replace(/\/$/, ""); }

async function refreshStats() {
  try {
    const r = await fetch(await bridgeUrl() + "/api/stats");
    const d = await r.json();
    $("s-total").textContent = d.total;
    $("s-done").textContent = d.done;
    $("s-pending").textContent = d.pending;
    $("s-failed").textContent = d.failed;
    $("paths").textContent = `nguồn: ${d.src}  →  đích: ${d.out}`;
    pill($("bstatus"), "bridge OK", "ok");
    return d;
  } catch (e) {
    pill($("bstatus"), "chưa thấy bridge", "err");
    $("paths").textContent = "Chạy: python bridge.py (trong project/gemini_ocr)";
    return null;
  }
}

$("check").addEventListener("click", refreshStats);

$("start").addEventListener("click", async () => {
  const d = await refreshStats();
  if (!d) { addLog("✖ chưa chạy bridge.py — không bắt đầu được"); return; }
  const res = await chrome.runtime.sendMessage({ type: "START_BATCH", cfg: await readCfg() });
  if (res?.ok) {
    $("start").classList.add("hide"); $("stop").classList.remove("hide");
    pill($("bstatus"), "đang chạy", "run");
    addLog("▶ batch bắt đầu");
  } else addLog("✖ " + (res?.error || "không bắt đầu được"));
});

$("stop").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "STOP_BATCH" });
  $("stop").classList.add("hide"); $("start").classList.remove("hide");
  pill($("bstatus"), "đã dừng", "");
  addLog("■ dừng batch (job đang chạy vẫn chạy nốt)");
});

// ── cấu hình ─────────────────────────────────────────────────────────────────
async function readCfg() {
  return {
    bridge: $("bridge").value.trim().replace(/\/$/, ""),
    geminiUrl: $("geminiUrl").value.trim(),
    prompt: $("prompt").value,
    maxTabs: Math.max(1, +$("maxTabs").value || 1),
    jobTimeoutMs: (+$("jobTimeout").value || 600) * 1000,
    stableMs: (+$("stable").value || 6) * 1000,
    closeTab: $("closeTab").checked,
  };
}

$("savecfg").addEventListener("click", async () => {
  await chrome.storage.local.set({ cfg: await readCfg(), ui: {
    bridge: $("bridge").value, prompt: $("prompt").value, maxTabs: $("maxTabs").value,
    geminiUrl: $("geminiUrl").value,
    jobTimeout: $("jobTimeout").value, stable: $("stable").value, closeTab: $("closeTab").checked,
  } });
  pill($("cfgstatus"), "đã lưu", "ok");
  setTimeout(() => pill($("cfgstatus"), "", ""), 1500);
});

// ── nhật ký + sự kiện từ background ──────────────────────────────────────────
function addLog(msg) {
  const el = $("log");
  const line = document.createElement("div");
  line.textContent = new Date().toLocaleTimeString("vi-VN") + "  " + msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  while (el.childNodes.length > 300) el.removeChild(el.firstChild);
}

// Chép toàn bộ nhật ký ra clipboard — đỡ phải chụp màn hình khi báo lỗi.
$("copylog").addEventListener("click", async () => {
  const t = [...$("log").childNodes].map(n => n.textContent).join("\n");
  try {
    await navigator.clipboard.writeText(t);
    pill($("logstatus"), `đã chép ${t.split("\n").length} dòng`, "ok");
  } catch (e) {
    pill($("logstatus"), "không chép được", "err");
  }
  setTimeout(() => pill($("logstatus"), "", ""), 2500);
});

chrome.runtime.onMessage.addListener(msg => {
  if (msg?.type === "LOG") addLog(msg.msg);
  if (msg?.type === "JOB_STATE") {
    const s = `${msg.label} — ${msg.phase}${msg.chars ? ` (${msg.chars} ký tự${msg.streaming ? ", đang gõ…" : ""})` : ""}`;
    if ($("status").className.includes("run")) pill($("status"), s.slice(0, 70), "run");
    addLog(s);
  }
  if (msg?.type === "BATCH_STATS") { refreshStats(); }
  if (msg?.type === "BATCH_DONE") {
    $("stop").classList.add("hide"); $("start").classList.remove("hide");
    pill($("bstatus"), "hoàn tất", "ok");
    addLog(`✔ batch xong — ${msg.done} thành công, ${msg.failed} lỗi`);
  }
});

// ── khôi phục UI đã lưu ──────────────────────────────────────────────────────
(async () => {
  const d = await chrome.storage.local.get(["ui"]);
  const u = d.ui || {};
  if (u.bridge) $("bridge").value = u.bridge;
  if (u.geminiUrl) $("geminiUrl").value = u.geminiUrl;
  if (u.prompt) $("prompt").value = u.prompt;
  if (u.maxTabs) $("maxTabs").value = u.maxTabs;
  if (u.jobTimeout) $("jobTimeout").value = u.jobTimeout;
  if (u.stable) $("stable").value = u.stable;
  if (typeof u.closeTab === "boolean") $("closeTab").checked = u.closeTab;
  refreshStats();
})();
