/**
 * background.js — service worker điều phối.
 *
 * 2 chế độ:
 *   TEST  : panel gửi 1 file (base64) → chạy 1 job → trả text về panel để xem/tải .txt
 *   BATCH : poll bridge.py (127.0.0.1:8777) → chạy hàng loạt → POST text về bridge,
 *           bridge ghi vào data/clean_data/<đúng cây thư mục của raw>.txt
 */

const DEFAULTS = {
  bridge: "http://127.0.0.1:8777",
  // Tài khoản Google nhiều profile: /u/0 là tài khoản đầu, /u/2 là tài khoản thứ ba.
  // Sai chỉ số là mở nhầm tài khoản -> Gemini khác, lịch sử chat khác.
  geminiUrl: "https://gemini.google.com/u/2/app",
  prompt: "Đọc PDF này cho tôi và OCR ra txt cho tôi (output dưới dạng plaintext để tôi copy)",
  maxTabs: 1,            // batch: số tab Gemini chạy song song
  jobTimeoutMs: 10 * 60 * 1000,   // mốc cho tài liệu ngắn; dài thì tự nới theo số trang
  perPageMs: 25 * 1000,           // mỗi trang cộng thêm bấy nhiêu
  maxTimeoutMs: 45 * 60 * 1000,   // trần, để 1 file hỏng không giữ chỗ mãi
  stableMs: 6000,        // text đứng yên bao lâu thì coi là xong
  closeTab: true,        // đóng tab sau khi xong (tắt khi debug)
  pollMs: 3000,
};

let CFG = { ...DEFAULTS };
let batchRunning = false;
let vongLapDangChay = false;   // co RIENG: batchRunning là "người dùng muốn chạy",
                               // còn cờ này là "vòng lặp có thật đang sống trong SW này"
let activeJobs = 0;
let stats = { done: 0, failed: 0, lastError: "" };

// ── tiện ích ─────────────────────────────────────────────────────────────────
const sleep = ms => new Promise(r => setTimeout(r, ms));

function emit(type, payload) {
  chrome.runtime.sendMessage({ type, ...payload }, () => void chrome.runtime.lastError);
}
function plog(msg) {
  console.log("[bg]", msg);
  emit("LOG", { msg, ts: Date.now() });
}

async function loadCfg() {
  const d = await chrome.storage.local.get("cfg");
  CFG = { ...DEFAULTS, ...(d.cfg || {}) };
  return CFG;
}

async function withTimeout(p, ms, label) {
  let t;
  try {
    return await Promise.race([
      p,
      new Promise((_, rej) => { t = setTimeout(() => rej(new Error(`timeout: ${label}`)), ms); }),
    ]);
  } finally { clearTimeout(t); }
}

// Gemini là SPA — tab nền hay bị Chrome ngừng render. Xoay focus như vps_ai_worker.
const _jobTabs = new Set();
let _focusTimer = null, _focusIdx = 0;
function addJobTab(id) {
  _jobTabs.add(id);
  if (!_focusTimer) { _focusTimer = setInterval(rotateFocus, 5000); rotateFocus(); }
}
function removeJobTab(id) {
  _jobTabs.delete(id);
  if (!_jobTabs.size && _focusTimer) { clearInterval(_focusTimer); _focusTimer = null; _focusIdx = 0; }
}
async function rotateFocus() {
  const tabs = [..._jobTabs];
  if (!tabs.length) { if (_focusTimer) { clearInterval(_focusTimer); _focusTimer = null; } return; }
  if (tabs.length === 1) return;                 // 1 tab thì khỏi xoay
  _focusIdx = (_focusIdx + 1) % tabs.length;
  try { await chrome.tabs.update(tabs[_focusIdx], { active: true }); } catch (_) { _jobTabs.delete(tabs[_focusIdx]); }
}

// Lỗi do NGƯỜI DÙNG đụng vào trình duyệt, không phải do OCR hỏng. Đừng tính vào 3 lượt thử.
const LOI_TAM_THOI = /No tab with id|Tabs cannot be edited|cannot be edited right now|dragging a tab|Tab was closed|The tab was closed|No window with id/i;

/** Mở tab, thử lại vài lần nếu người dùng đang kéo tab (Chrome khoá thao tác tab lúc đó). */
async function moTab(url) {
  let loiCuoi = null;
  for (let i = 1; i <= 4; i++) {
    try {
      return await chrome.tabs.create({ url, active: true });
    } catch (e) {
      loiCuoi = e;
      if (!LOI_TAM_THOI.test(e.message || "")) throw e;
      plog(`chưa mở được tab (${e.message}) — chờ 3s rồi thử lại ${i}/4`);
      await sleep(3000);
    }
  }
  throw loiCuoi;
}

function waitTabReady(tabId, timeout = 30000) {
  return new Promise(resolve => {
    const done = () => { clearTimeout(t); chrome.tabs.onUpdated.removeListener(fn); resolve(); };
    const fn = (id, info) => { if (id === tabId && info.status === "complete") done(); };
    const t = setTimeout(() => { chrome.tabs.onUpdated.removeListener(fn); resolve(); }, timeout);
    chrome.tabs.onUpdated.addListener(fn);
    chrome.tabs.get(tabId, tab => {
      if (chrome.runtime.lastError) return done();
      if (tab?.status === "complete") done();
    });
  });
}

// ── Lấy text qua NÚT TẢI XUỐNG của lớp phủ xem file ──────────────────────────
// Bấm nút tải thì Chrome lưu ra đĩa, mà extension KHÔNG đọc lại được file đó.
// Nên thay vì đọc file, ta chặn ngay từ trong trang: nút tải luôn phải tạo một
// Blob + URL.createObjectURL để tải. Bọc hàm đó lại là giữ được nội dung trong RAM,
// đọc thẳng ra text — không cần đụng tới thư mục Downloads.

// Bấm nút tải thì Chrome VẪN tải file thật về Downloads. Ta chỉ cần nội dung trong RAM,
// nên huỷ luôn để chạy 455 file không rải rác ra thư mục Downloads.
let _dangBatBlob = false;
let _baoUrlTai = null;          // hàm resolve của doiUrlTaiXuong() đang chờ

chrome.downloads?.onCreated?.addListener?.((item) => {
  if (!_dangBatBlob) return;                       // ngoài lúc chạy job thì không đụng vào
  const url = item.finalUrl || item.url || "";
  // Huỷ để chạy 455 file không rải rác ra thư mục Downloads — ta chỉ cần nội dung.
  chrome.downloads.cancel(item.id, () => {
    void chrome.runtime.lastError;
    chrome.downloads.erase({ id: item.id }, () => void chrome.runtime.lastError);
  });
  if (_baoUrlTai) { _baoUrlTai(url); _baoUrlTai = null; }
});

/** Chờ Chrome báo có lượt tải bắt đầu, trả về URL của nó (rỗng nếu quá hạn). */
function doiUrlTaiXuong(ms) {
  return new Promise(resolve => {
    _baoUrlTai = resolve;
    setTimeout(() => { if (_baoUrlTai === resolve) { _baoUrlTai = null; resolve(""); } }, ms);
  });
}

/**
 * Cài móc vào MỌI frame, TRƯỚC khi bấm nút tải / nút sao chép.
 *
 * Nút "Sao chép mã" ghi TOÀN BỘ nội dung khối code vào clipboard — kể cả phần DOM
 * đã cắt cụt. Nhưng đọc lại clipboard thì cần quyền + tab phải đang focus, chạy nền
 * là hỏng. Nên móc thẳng vào chỗ nó GHI (execCommand('copy') của Angular CDK, hoặc
 * navigator.clipboard.writeText) là lấy được nội dung mà không đụng tới clipboard.
 */
async function installPageHooks(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId, allFrames: true }, world: "MAIN",
    func: () => {
      if (window.__ocrBlobHook) return true;
      window.__ocrBlobHook = true;
      window.__ocrBlobs = [];
      window.__ocrCopied = "";

      // — móc CLIPBOARD —
      // Angular CDK copy: tạo <textarea> ẩn -> set value -> select -> execCommand('copy')
      const ecGoc = document.execCommand.bind(document);
      document.execCommand = (cmd, ...r) => {
        const ok = ecGoc(cmd, ...r);
        if (/^copy$/i.test(cmd)) {
          try {
            const ae = document.activeElement;
            const t = (ae && ae.value !== undefined ? ae.value : "")
                   || String(window.getSelection() || "");
            if (t && t.length > (window.__ocrCopied || "").length) window.__ocrCopied = t;
          } catch (_) {}
        }
        return ok;
      };
      try {
        const wGoc = navigator.clipboard?.writeText?.bind(navigator.clipboard);
        if (wGoc) navigator.clipboard.writeText = (t) => {
          try { if (t && t.length > (window.__ocrCopied || "").length) window.__ocrCopied = String(t); } catch (_) {}
          return wGoc(t);
        };
        const w2 = navigator.clipboard?.write?.bind(navigator.clipboard);
        if (w2) navigator.clipboard.write = async (items) => {
          try {
            for (const it of items || []) {
              if (it.types?.includes("text/plain")) {
                const t = await (await it.getType("text/plain")).text();
                if (t.length > (window.__ocrCopied || "").length) window.__ocrCopied = t;
              }
            }
          } catch (_) {}
          return w2(items);
        };
      } catch (_) {}
      // trang tự đặt nội dung trong sự kiện copy
      document.addEventListener("copy", (e) => {
        try {
          const t = e.clipboardData?.getData("text/plain") || String(window.getSelection() || "");
          if (t && t.length > (window.__ocrCopied || "").length) window.__ocrCopied = t;
        } catch (_) {}
      }, true);
      const goc = URL.createObjectURL.bind(URL);
      URL.createObjectURL = (obj) => {
        try { if (obj instanceof Blob) window.__ocrBlobs.push(obj); } catch (_) {}
        return goc(obj);
      };
      // Nút tải có thể dùng <a download href="..."> (data:, blob:, hoặc https:)
      document.addEventListener("click", (e) => {
        const a = e.target?.closest?.("a[download]");
        if (a?.href) window.__ocrDlHref = a.href;
      }, true);
      // ...hoặc mở URL bằng window.open / gán location cho iframe ẩn
      const moGoc = window.open?.bind(window);
      if (moGoc) window.open = (u, ...r) => { if (u) window.__ocrDlHref = String(u); return moGoc(u, ...r); };
      return true;
    },
  }).catch(() => {});
}

/**
 * ĐƯỜNG CHÍNH lấy nội dung: đưa khối mã ra rồi bấm nút copy của nó.
 *
 * Gemini trả lời theo 2 kiểu, hàm này lo cả hai trong MỘT vòng lặp:
 *   a) khối mã GẬP LẠI  -> bấm "Hiện mã" (span.action-button) để dựng nút copy
 *   b) khối mã HIỆN SẴN -> chỉ có nút copy (aria-label "Sao chép mã"), không có "Hiện mã"
 *
 * Bấm hết các nút copy rồi mới chọn: trong một câu trả lời có cả nút copy của khối mã
 * lẫn nút copy cả câu trả lời (bản này kèm câu dẫn, dài gần gấp đôi) — dừng ở nút đầu
 * tiên là dễ vớ nhầm bản rác.
 *
 * @returns {Promise<{texts:string[], nhat:string[], soNut:number}>}
 */
async function hienMaRoiCopy(tabId) {
  const [r] = await chrome.scripting.executeScript({
    target: { tabId }, world: "MAIN",
    func: async () => {
      const nghi = ms => new Promise(r => setTimeout(r, ms));

      // "Nhìn thấy được" — offsetParent null với position:fixed nên phải đo cả kích thước.
      const hien = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
      };

      // CHỮ CỦA CHÍNH NÓ: chỉ gộp text node con TRỰC TIẾP.
      // <mat-icon> dùng ligature font nên textContent của thẻ cha ra "Hiện mãcode" —
      // so khớp bằng textContent là trượt. Đây chính là lỗi đã gặp.
      const chuRieng = (el) => {
        let t = "";
        for (const n of el.childNodes) if (n.nodeType === 3) t += n.nodeValue;
        return t.trim();
      };

      // Angular Material nghe pointerdown/mousedown chứ không chỉ click.
      const bamThat = (el) => {
        const r = el.getBoundingClientRect();
        const o = { bubbles: true, cancelable: true, composed: true,
                    clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 };
        try { el.scrollIntoView({ block: "center" }); } catch (_) {}
        for (const ev of ["pointerover", "pointerenter", "pointerdown", "mousedown",
                          "pointerup", "mouseup", "click"]) {
          try {
            el.dispatchEvent(ev.startsWith("pointer")
              ? new PointerEvent(ev, o) : new MouseEvent(ev, o));
          } catch (_) {}
        }
        try { el.click(); } catch (_) {}
      };

      const timTheoChu = (re) => {
        for (const el of document.querySelectorAll("span, div, button, a, [role='button']")) {
          if (!re.test(chuRieng(el))) continue;
          const bam = el.closest(".action-button, button, [role='button']") || el.parentElement || el;
          if (hien(bam)) return bam;
          if (hien(el)) return el;
        }
        return null;
      };
      // Nút copy của khối mã. Nhận diện bằng CẢ HAI cách vì Gemini có lúc đổi:
      //   - aria-label "Sao chép mã" / "Copy code"
      //   - icon <mat-icon fonticon="copy">
      const iconCopy = () => {
        const ra = [];
        for (const b of document.querySelectorAll(
          "button[aria-label*='Sao chép mã' i], button[aria-label*='Copy code' i]")) {
          if (hien(b) && !ra.includes(b)) ra.push(b);
        }
        for (const ic of document.querySelectorAll(
          "mat-icon[fonticon='copy'], mat-icon[data-mat-icon-name='copy']")) {
          const b = ic.closest("button, [role='button']");
          if (b && hien(b) && !ra.includes(b)) ra.push(b);
        }
        return ra;
      };

      const nhat = [];
      // Log ra console CỦA TRANG (chỗ đang thấy "[OCR] ..."), không phải console service
      // worker — để soi lỗi khỏi phải mở hai cửa sổ devtools.
      const ghi = (m) => { nhat.push(m); try { console.log("[OCR-copy] " + m); } catch (_) {} };
      const RE_HIEN = /^(hiện mã|show code)$/i;
      const RE_AN = /^(ẩn mã|hide code)$/i;

      // ── BƯỚC 1: chờ & bấm "Hiện mã" ──────────────────────────────────────
      let daBam = false, daMoSan = false;
      for (let i = 0; i < 20 && !daBam; i++) {       // chờ tối đa 10s, kiểm tra mỗi 500ms
        if (timTheoChu(RE_AN)) { daMoSan = true; ghi("thấy 'Ẩn mã' → khối mã đang mở sẵn"); break; }
        const nut = timTheoChu(RE_HIEN);
        if (nut) {
          bamThat(nut);
          daBam = true;
          ghi("đã bấm 'Hiện mã' sau " + (i * 0.5) + "s");
          break;
        }
        await nghi(500);
      }
      if (!daBam && !daMoSan) ghi("HẾT 10s KHÔNG THẤY 'Hiện mã'");

      // ── BƯỚC 2: chờ nút copy hiện ra rồi bấm ─────────────────────────────
      let nut = [];
      for (let i = 0; i < 16; i++) {                 // chờ tối đa 8s
        nut = iconCopy();
        if (nut.length) break;
        await nghi(500);
      }
      ghi("thấy " + nut.length + " nút copy");

      const texts = [];
      for (const b of nut) {
        window.__ocrCopied = "";
        bamThat(b);
        for (let i = 0; i < 12; i++) {               // chờ tối đa 3s cho nội dung vào
          await nghi(250);
          if ((window.__ocrCopied || "").length > 100) break;
        }
        const t = window.__ocrCopied || "";
        ghi("bấm nút copy → bắt được " + t.length + " ký tự");
        // Gom ĐỦ rồi mới chọn: trong khối có cả nút copy của code block lẫn nút copy
        // cả câu trả lời. Dừng ở nút đầu tiên là dễ vớ nhầm bản có kèm câu dẫn.
        if (t.length > 100) texts.push(t);
      }

      return { daBamHienMa: daBam, daMoSan, soNut: nut.length, texts, nhat,
               soIconCopy: document.querySelectorAll("mat-icon[fonticon='copy']").length };
    },
  }).catch(e => [{ result: { daBamHienMa: false, daMoSan: false, soNut: 0, texts: [],
                             nhat: ["executeScript lỗi: " + e.message], soIconCopy: 0 } }]);
  return r?.result || { daBamHienMa: false, daMoSan: false, soNut: 0, texts: [], nhat: [], soIconCopy: 0 };
}

/** Tìm và bấm nút tải xuống trong lớp phủ (mọi frame). Trả về số nút đã bấm. */
async function clickViewerDownload(tabId) {
  const res = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true }, world: "MAIN",
    func: () => {
      const KHOP = /tải xuống|tải về|download/i;
      const ungVien = [
        ...document.querySelectorAll(
          "[aria-label],[data-tooltip],[title],button,[role='button'],.drive-viewer-download-icon"
        ),
      ];
      for (const e of ungVien) {
        const nhan = e.getAttribute?.("aria-label") || e.getAttribute?.("data-tooltip")
                  || e.getAttribute?.("title") || "";
        const laIconTai = (e.className || "").toString().includes("drive-viewer-download-icon");
        if (!KHOP.test(nhan) && !laIconTai) continue;
        // icon nằm trong div[role=button] -> bấm thằng bọc ngoài mới ăn
        const btn = e.closest("[role='button'], button") || e;
        if (btn.offsetParent === null) continue;
        btn.click();
        return nhan || "drive-viewer-download-icon";
      }
      return null;
    },
  }).catch(() => []);
  return (res || []).map(r => r?.result).filter(Boolean);
}

/**
 * Tải 1 URL BÊN TRONG TRANG (mọi frame). Bắt buộc với URL `blob:` — blob chỉ sống trong
 * origin của trang đã tạo ra nó, service worker fetch sẽ luôn hỏng.
 */
async function fetchInPage(tabId, url) {
  const res = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true }, world: "MAIN",
    func: async (u) => {
      try {
        const r = await fetch(u);
        if (!r.ok) return "";
        return await r.text();
      } catch (_) { return ""; }
    },
    args: [url],
  }).catch(() => []);
  let best = "";
  for (const r of res || []) {
    const t = typeof r?.result === "string" ? r.result : "";
    if (t.length > best.length) best = t;
  }
  return best;
}

/** Đọc nội dung blob/data-url đã bắt được (mọi frame), lấy bản dài nhất. */
async function readCapturedBlob(tabId) {
  const res = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true }, world: "MAIN",
    func: async () => {
      let best = "";
      for (const b of window.__ocrBlobs || []) {
        try {
          if (b.size > 20 * 1024 * 1024) continue;
          const t = await b.text();
          if (t.length > best.length) best = t;
        } catch (_) {}
      }
      if (window.__ocrDlHref) {
        try {
          const t = await (await fetch(window.__ocrDlHref)).text();
          if (t.length > best.length) best = t;
        } catch (_) {}
      }
      return best;
    },
  }).catch(() => []);
  let best = "";
  for (const r of res || []) {
    const t = typeof r?.result === "string" ? r.result : "";
    if (t.length > best.length) best = t;
  }
  return best;
}

// ── Chạy 1 job trên 1 tab Gemini ─────────────────────────────────────────────
/**
 * @param {{name:string,b64:string,mime:string,label:string}} job
 * @returns {Promise<{ok:boolean,text?:string,error?:string,diag?:string}>}
 */
async function runOne(job) {
  await loadCfg();
  let tab = null, watchdog = null;
  activeJobs++;
  // Tài liệu 45 trang không thể xong trong 10 phút — timeout cố định là fail oan.
  // Nới theo số trang (bridge gửi kèm), có trần để không giữ chỗ vô hạn.
  const JOB_MS = Math.min(
    CFG.maxTimeoutMs || DEFAULTS.maxTimeoutMs,
    (CFG.jobTimeoutMs || DEFAULTS.jobTimeoutMs) + (job.pages || 0) * (CFG.perPageMs || DEFAULTS.perPageMs)
  );
  try {
    plog(`▶ ${job.label || job.name}`
       + (job.pages ? ` (${job.pages} trang, hạn ${Math.round(JOB_MS / 60000)} phút)` : "")
       + (job.attempt > 1 ? ` — lần thử ${job.attempt}` : ""));
    emit("JOB_STATE", { label: job.label || job.name, phase: "opening" });

    tab = await moTab(CFG.geminiUrl || DEFAULTS.geminiUrl);
    watchdog = setTimeout(() => {
      removeJobTab(tab.id);
      chrome.tabs.remove(tab.id, () => void chrome.runtime.lastError);
    }, JOB_MS + 60000);
    addJobTab(tab.id);

    await waitTabReady(tab.id, 30000);
    await sleep(4000);                              // SPA mount xong

    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["engine_gemini_pdf.js"] });
    await sleep(500);

    emit("JOB_STATE", { label: job.label || job.name, phase: "uploading" });
    const [fill] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (prompt, b64, name, mime) => window.__ocrEngine.attachAndSend(prompt, b64, name, mime),
      args: [CFG.prompt, job.b64, job.name, job.mime || "application/pdf"],
    });
    if (!fill?.result?.ok) {
      throw new Error(fill?.result?.error || "attachAndSend thất bại");
    }
    plog("đã gửi, chờ Gemini trả lời...");

    // ── poll kết quả ──
    const deadline = Date.now() + JOB_MS;
    let res = null;
    while (Date.now() < deadline) {
      await sleep(CFG.pollMs);
      const [r] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (ms) => window.__ocrEngine?.getResult?.(ms) ?? null,
        args: [CFG.stableMs],
      }).catch(() => [null]);
      res = r?.result || res;
      if (res) {
        emit("JOB_STATE", {
          label: job.label || job.name, phase: res.phase,
          chars: res.lastLen, streaming: !!res.streaming,
        });
      }
      if (res?.done) break;
      if (res?.phase === "error") throw new Error(res.error || "engine lỗi");
    }
    if (!res?.done) throw new Error(`Hết ${Math.round(JOB_MS / 60000)} phút mà Gemini chưa trả lời xong`
                                    + (res?.lastLen ? ` (mới ra ${res.lastLen} ký tự)` : ""));

    let text = res.text || "";

    // ── ĐƯỜNG 1: "Hiện mã" → copy khối Python ─────────────────────────────────
    // Gemini gói nội dung OCR trong đoạn Python ghi file, và THU GỌN đoạn đó lại.
    // Trình tự: bấm "Hiện mã" để dựng khối code -> bấm nút copy của khối -> bắt nội
    // dung ngay lúc trang ghi clipboard. Được TRỌN VẸN cả phần DOM hiển thị cắt cụt;
    // vỏ Python thì sach_hoa.py bên bridge (và pickBlockText ở đây) bóc ra.
    try {
      emit("JOB_STATE", { label: job.label || job.name, phase: "hiện mã rồi sao chép" });
      await installPageHooks(tab.id);
      const cop = await hienMaRoiCopy(tab.id);
      if (cop.texts.length) {
        const [chon] = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: (ds) => window.__ocrEngine.pickFromTexts(ds),
          args: [cop.texts],
        }).catch(() => [null]);
        const t = chon?.result || "";
        plog(`copy: ${(cop.nhat || []).join(" | ")} → chọn ${t.length} ký tự`);
        if (t.length > text.length) text = t;
      } else if (cop.soNut) {
        plog(`bấm ${cop.soNut} nút copy nhưng không bắt được nội dung`);
      } else {
        plog(`không thấy nút copy (Hiện mã: ${cop.daBamHienMa ? "đã bấm" : cop.daMoSan ? "mở sẵn" : "KHÔNG THẤY"})`
           + ` | icon copy trong DOM: ${cop.soIconCopy}`
           + ` | các nhãn có chữ "mã": ${JSON.stringify(cop.nhinThay || [])}`);
      }
    } catch (e) { plog("đường nút sao chép hỏng (bỏ qua): " + e.message); }

    // ── ĐƯỜNG 2: file artifact — CHỈ chạy khi đường 1 không lấy được ──────────
    // Mở artifact + cuộn + bấm tải + chờ Chrome báo lượt tải mất ~30s MỖI FILE, mà đo
    // thực tế chỉ hơn bản copy khoảng 1% (17551 so với 17335 ký tự). Với 462 file thì
    // đó là gần 4 tiếng đổi lấy 1% — không đáng. Copy được là xong.
    const copyDuocRoi = text.length >= 500;
    if (copyDuocRoi) {
      plog(`copy đủ dùng (${text.length} ký tự) → bỏ qua đường artifact cho nhanh`);
    }
    if (!copyDuocRoi && res.hasArtifact) {
      try {
        emit("JOB_STATE", { label: job.label || job.name, phase: "mở file artifact" });
        await installPageHooks(tab.id);          // phải cài TRƯỚC khi lớp phủ dựng nút tải
        await chrome.scripting.executeScript({
          target: { tabId: tab.id }, func: () => window.__ocrEngine.openArtifact(),
        });
        await sleep(4000);
        await installPageHooks(tab.id);          // lớp phủ có thể mount iframe mới sau khi mở

        // Ép trình xem render hết mọi trang TRƯỚC khi đọc. Không cuộn thì file nhiều trang
        // chỉ ra vài trang đầu — vẫn "có text" nên rất dễ tưởng là chạy đúng.
        const cuon = await chrome.scripting.executeScript({
          target: { tabId: tab.id }, func: () => window.__ocrEngine.scrollViewerToEnd(),
        }).catch(() => [null]);
        if (cuon?.[0]?.result?.trang) plog(`lớp phủ có ${cuon[0].result.trang} trang sau khi cuộn`);

        let best = "";

        // ── ƯU TIÊN 1: bấm nút "Tải xuống" của lớp phủ ───────────────────────
        // Đây mới là FILE THẬT Gemini tạo ra. Đọc DOM chỉ là ảnh chụp giao diện:
        // dễ lẫn chữ trên nút, dễ thiếu phần chưa cuộn tới. Bấm tải rồi bắt Blob/URL
        // là lấy đúng bytes của file, không cần file rơi xuống thư mục Downloads.
        _dangBatBlob = true;
        try {
          const chuoiUrl = doiUrlTaiXuong(8000);       // chờ sự kiện download (8s là đủ; trước để 20s, mà đo thực tế nút này thường KHÔNG tạo lượt tải nào nên chờ dài là phí)
          const daBam = await clickViewerDownload(tab.id);
          if (daBam.length) {
            plog(`đã bấm nút tải (${daBam.join(", ")}), chờ lấy nội dung...`);
            await sleep(2500);

            const viaBlob = await readCapturedBlob(tab.id);
            if (viaBlob.length > best.length) {
              best = viaBlob;
              plog(`✔ lấy được từ Blob của nút tải: ${viaBlob.length} ký tự`);
            }

            // Nút tải có thể trỏ thẳng tới URL trên máy chủ (không tạo Blob).
            // Khi đó tự tải nội dung đó về trong service worker.
            if (best.length < 200) {
              const url = await chuoiUrl;
              if (url) {
                plog(`nút tải đi bằng URL: ${url.slice(0, 60)}…`);
                try {
                  // blob: chỉ đọc được TỪ TRONG TRANG; http(s) thì service worker tải được
                  const t = /^blob:/.test(url)
                    ? await fetchInPage(tab.id, url)
                    : await (await withTimeout(fetch(url, { credentials: "include" }), 30000, "tải artifact")).text();
                  if (t.length > best.length) {
                    best = t;
                    plog(`✔ lấy được từ URL của nút tải: ${t.length} ký tự`);
                  }
                } catch (e) { plog("tải URL của nút hỏng: " + e.message); }
              } else {
                plog("bấm nút nhưng Chrome không báo lượt tải nào");
              }
            }
          } else {
            plog("không tìm thấy nút tải xuống trong lớp phủ");
          }
        } finally { _dangBatBlob = false; }

        // ── ƯU TIÊN 2: đọc text ngay trong DOM lớp phủ (mọi frame) ───────────
        if (best.length < 200) {
          const grabs = await chrome.scripting.executeScript({
            target: { tabId: tab.id, allFrames: true },
            files: ["frame_grabber.js"],
          }).catch(() => []);
          for (const g of grabs || []) {
            const t = typeof g?.result === "string" ? g.result : "";
            if (t.length > best.length) best = t;
          }
          const [inPage] = await chrome.scripting.executeScript({
            target: { tabId: tab.id }, func: () => window.__ocrEngine.artifactTextInPage(),
          }).catch(() => [null]);
          if ((inPage?.result || "").length > best.length) best = inPage.result;
          if (best.length > 200) plog(`lấy được từ DOM lớp phủ: ${best.length} ký tự`);
        }

        // Gemini rất hay trả lời bằng CODE PYTHON ghi file (chat hiện mã, text thật nằm
        // trong file). Khối code đó cũng dài -> so độ dài là chọn nhầm. Nên:
        //   - chat có mùi code  -> LUÔN lấy bản artifact (chỉ cần đủ dài)
        //   - còn lại           -> lấy bản nào dài hơn
        // File artifact LÀ bản txt thật Gemini tạo ra -> có là dùng, không so độ dài với
        // chat nữa (khối code Python trong chat luôn dài hơn mà lại là thứ ta không muốn).
        if (best.length > 200) {
          plog(`dùng bản từ file artifact: ${best.length} ký tự (chat: ${text.length})`);
          text = best;
        } else if (res.looksCode) {
          plog(`⚠️ chat là code mà artifact không lấy được text (${best.length} ký tự) → dùng bản bóc từ code`);
        }
        await chrome.scripting.executeScript({
          target: { tabId: tab.id }, func: () => window.__ocrEngine.closeArtifact(),
        }).catch(() => {});
      } catch (e) { plog("mở artifact lỗi (bỏ qua): " + e.message); }
    }

    const [diag] = await chrome.scripting.executeScript({
      target: { tabId: tab.id }, func: () => window.__ocrEngine?.getDiag?.() ?? "",
    }).catch(() => [null]);

    if (text.trim().length < 20) throw new Error("Text lấy về quá ngắn — coi như thất bại");

    plog(`✔ ${job.label || job.name} → ${text.length} ký tự`);
    return { ok: true, text, diag: diag?.result || "" };
  } catch (e) {
    plog(`✖ ${job.label || job.name}: ${e.message}`);
    let diag = "";
    if (tab) {
      const [d] = await chrome.scripting.executeScript({
        target: { tabId: tab.id }, func: () => window.__ocrEngine?.getDiag?.() ?? "",
      }).catch(() => [null]);
      diag = d?.result || "";
    }
    return { ok: false, error: e.message, diag, tamThoi: LOI_TAM_THOI.test(e.message || "") };
  } finally {
    activeJobs--;
    if (watchdog) clearTimeout(watchdog);
    if (tab) {
      removeJobTab(tab.id);
      if (CFG.closeTab) chrome.tabs.remove(tab.id, () => void chrome.runtime.lastError);
    }
  }
}

// ── Chế độ BATCH (qua bridge.py) ─────────────────────────────────────────────
function bufToB64(buf) {
  const bytes = new Uint8Array(buf);
  let s = "";
  const CH = 0x8000;
  for (let i = 0; i < bytes.length; i += CH) {
    s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
  }
  return btoa(s);
}

// ── Giữ batch sống qua việc Chrome giết service worker ───────────────────────
// MV3 tắt service worker sau ~30s không có việc, cuốn theo cả vòng lặp batch — chạy
// 462 file mất nhiều giờ nên chắc chắn dính. Cách chống: ghi ý định vào storage, rồi
// dùng chrome.alarms (alarm ĐÁNH THỨC được service worker đã tắt) để dựng lại vòng lặp.
const TEN_ALARM = "batch-song";

async function datYDinhChay(muon) {
  await chrome.storage.local.set({ batchMuonChay: !!muon });
  if (muon) {
    chrome.alarms.create(TEN_ALARM, { periodInMinutes: 0.5 });
  } else {
    chrome.alarms.clear(TEN_ALARM, () => void chrome.runtime.lastError);
  }
}

chrome.alarms.onAlarm.addListener(async (a) => {
  if (a.name !== TEN_ALARM) return;
  const d = await chrome.storage.local.get("batchMuonChay");
  if (!d.batchMuonChay) { chrome.alarms.clear(TEN_ALARM, () => void chrome.runtime.lastError); return; }
  if (vongLapDangChay) return;                 // còn sống thì thôi
  plog("service worker vừa bị Chrome tắt rồi bật lại — dựng lại vòng lặp batch");
  batchRunning = true;
  batchLoop();
});

async function batchLoop() {
  if (vongLapDangChay) return;
  vongLapDangChay = true;
  await loadCfg();
  const workerId = "ext-" + Math.random().toString(36).slice(2, 8);
  plog(`batch bắt đầu (worker ${workerId}, ${CFG.maxTabs} tab song song)`);

  while (batchRunning) {
    if (activeJobs >= CFG.maxTabs) { await sleep(1500); continue; }
    let job = null;
    try {
      const r = await withTimeout(fetch(`${CFG.bridge}/api/next?worker=${workerId}`), 15000, "next");
      const d = await r.json();
      job = d.job;
    } catch (e) {
      plog("không gọi được bridge: " + e.message + " — thử lại sau 5s");
      await sleep(5000);
      continue;
    }
    if (!job) { plog("hết job — dừng batch"); batchRunning = false; await datYDinhChay(false); break; }

    // chạy job (không await để nhiều tab song song), nhưng vẫn giới hạn bằng activeJobs
    (async () => {
      try {
        const fr = await withTimeout(fetch(`${CFG.bridge}/api/file/${job.id}`), 60000, "file");
        const b64 = bufToB64(await fr.arrayBuffer());
        const out = await runOne({ name: job.name, b64, mime: "application/pdf", label: job.rel,
                                  pages: job.pages || 0, attempt: job.attempt || 1 });
        if (out.ok) {
          await fetch(`${CFG.bridge}/api/done`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: job.id, text: out.text }),
          });
          stats.done++;
        } else {
          await fetch(`${CFG.bridge}/api/fail`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: job.id, error: out.error, tam_thoi: !!out.tamThoi }),
          });
          stats.failed++; stats.lastError = out.error;
        }
      } catch (e) {
        stats.failed++; stats.lastError = e.message;
        plog("job lỗi: " + e.message);
        try {
          await fetch(`${CFG.bridge}/api/fail`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: job.id, error: e.message }),
          });
        } catch (_) {}
      }
      emit("BATCH_STATS", stats);
    })();

    await sleep(2500);      // giãn nhịp mở tab, tránh Gemini nghi ngờ
  }
  vongLapDangChay = false;
  emit("BATCH_DONE", stats);
}

// ── Router message từ panel ──────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    switch (msg?.type) {
      case "RUN_TEST": {
        await chrome.storage.local.set({ cfg: { ...CFG, ...(msg.cfg || {}) } });
        await loadCfg();
        const out = await runOne({ name: msg.name, b64: msg.b64, mime: msg.mime, label: msg.name });
        sendResponse(out);
        break;
      }
      case "START_BATCH": {
        if (batchRunning) { sendResponse({ ok: false, error: "batch đang chạy" }); break; }
        await chrome.storage.local.set({ cfg: { ...CFG, ...(msg.cfg || {}) } });
        await loadCfg();
        batchRunning = true;
        stats = { done: 0, failed: 0, lastError: "" };
        await datYDinhChay(true);
        batchLoop();
        sendResponse({ ok: true });
        break;
      }
      case "STOP_BATCH":
        batchRunning = false;
        await datYDinhChay(false);
        sendResponse({ ok: true });
        break;
      case "GET_STATE":
        sendResponse({ ok: true, batchRunning, activeJobs, stats, cfg: await loadCfg() });
        break;
      case "OPEN_PANEL":
        chrome.tabs.create({ url: chrome.runtime.getURL("panel.html") });
        sendResponse({ ok: true });
        break;
      default:
        sendResponse({ ok: false, error: "unknown message" });
    }
  })();
  return true;    // giữ kênh cho phản hồi bất đồng bộ
});

chrome.action.onClicked?.addListener?.(() => {
  chrome.tabs.create({ url: chrome.runtime.getURL("panel.html") });
});

// Service worker vừa khởi động lại (Chrome tắt đi bật lại, hoặc mới cài): nếu người
// dùng chưa bấm Dừng thì chạy tiếp ngay, không đợi alarm kế tiếp.
(async () => {
  const d = await chrome.storage.local.get("batchMuonChay");
  if (d.batchMuonChay && !vongLapDangChay) {
    batchRunning = true;
    chrome.alarms.create(TEN_ALARM, { periodInMinutes: 0.5 });
    plog("service worker khởi động lại — tiếp tục batch đang dở");
    batchLoop();
  }
})();

console.log("[bg] Gemini OCR Batch — service worker sẵn sàng");
