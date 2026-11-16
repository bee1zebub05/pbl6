/**
 * engine_gemini_pdf.js — inject vào gemini.google.com (ISOLATED world).
 *
 * Nhiệm vụ: đính 1 file PDF/DOC vào khung chat → gõ prompt → gửi → chờ trả lời xong
 *           → móc TEXT đầy đủ ra (ưu tiên code block "Plaintext", rồi tới file artifact).
 *
 * Thiết kế bám theo engine_gemini.js của vps_ai_worker:
 *   - selector fallback CHAIN, không cứng 1 selector (Gemini đổi UI liên tục)
 *   - nhiều phương pháp đính file, thử lần lượt, xác nhận bằng DELTA (số chip tăng)
 *   - trạng thái để ở window.__ocrEngine, background.js poll qua executeScript
 */

(function () {
  if (window.__ocrEngine) { console.log("[OCR] engine đã có sẵn"); return; }

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const log = (...a) => console.log("[OCR]", ...a);

  // ── Selector chains ────────────────────────────────────────────────────────
  const SEL = {
    input: [
      "rich-textarea .ql-editor",
      "div[contenteditable='true'][aria-placeholder]",
      "div[contenteditable='true'][role='textbox']",
      "div[contenteditable='true'][aria-label]",
      "div[contenteditable='true']",
    ],
    send: [
      "button:has(mat-icon[fonticon='arrow_upward'])",
      "button:has(mat-icon[data-mat-icon-name='arrow_upward'])",
      "button[aria-label='Send message']",
      "button[aria-label='Gửi tin nhắn']",
      "button.send-button",
    ],
    sendReady: [
      ".send-button-container:not(.disabled) button[aria-label]",
      "gem-icon-button[aria-disabled='false'] button:has(mat-icon[fonticon='arrow_upward'])",
      "button:has(mat-icon[fonticon='arrow_upward']):not([disabled])",
      "button:has(mat-icon[data-mat-icon-name='arrow_upward']):not([disabled])",
      "button[aria-label='Send message']:not([disabled])",
      "button[aria-label='Gửi tin nhắn']:not([disabled])",
    ],
    // Nút mở menu "+" / đính kèm. Nhiều biến thể ngôn ngữ + version UI.
    uploadMenu: [
      "button[aria-label='Open upload file menu']",
      "button[aria-label='Mở trình đơn tải tệp lên']",
      "button[aria-label*='upload' i]",
      "button[aria-label*='tải lên' i]",
      "button[aria-label*='tệp' i]",
      "button[aria-label*='attach' i]",
      "uploader button",
      "toolbox-drawer button:has(mat-icon[fonticon='add'])",
      "button:has(mat-icon[fonticon='add_2'])",
      "button:has(mat-icon[fonticon='add'])",
    ],
    // Item trong menu vừa mở
    uploadItem: [
      "button[data-test-id='local-image-file-uploader-button']",
      "button[data-test-id*='file-uploader']",
      "[role='menuitem'][data-test-id*='upload']",
    ],
    // Vùng response của model
    response: [
      "model-response",
      "message-content",
      ".model-response-text",
    ],
    markdown: [
      "message-content .markdown-main-panel",
      "message-content .markdown",
      ".model-response-text .markdown-main-panel",
      "model-response .markdown",
    ],
    // Nút "Đang mở" của file artifact Gemini sinh ra
    openArtifact: [
      "button[data-test-id='open-button']",
      "button.open-button",
    ],
    stop: [
      "button[aria-label*='Stop' i]",
      "button[aria-label*='Dừng' i]",
      "button:has(mat-icon[fonticon='stop'])",
    ],
  };

  const qs = (chain) => {
    for (const s of chain) {
      try { const el = document.querySelector(s); if (el) return el; } catch (_) {}
    }
    return null;
  };
  const qsAll = (chain) => {
    for (const s of chain) {
      try { const all = document.querySelectorAll(s); if (all.length) return [...all]; } catch (_) {}
    }
    return [];
  };
  const findEl = async (chain, timeout = 8000) => {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const el = qs(chain);
      if (el) return el;
      await sleep(400);
    }
    return null;
  };

  const visible = (el) => !!(el && el.offsetParent !== null);
  const sendEnabled = () => SEL.sendReady.some(s => {
    try {
      const el = document.querySelector(s);
      return !!el && !el.disabled && el.getAttribute("aria-disabled") !== "true";
    } catch (_) { return false; }
  });

  function dismissPopups() {
    document.querySelectorAll("button").forEach(btn => {
      const t = (btn.textContent || "").trim().toLowerCase();
      if (["not now", "dismiss", "close", "skip", "để sau", "bỏ qua", "đã hiểu", "got it"].includes(t) && visible(btn)) {
        try { btn.click(); } catch (_) {}
      }
    });
  }

  // ── State ──────────────────────────────────────────────────────────────────
  let _state = {
    phase: "idle",       // idle | uploading | sending | waiting | done | error
    done: false,
    text: "",
    error: null,
    hasArtifact: false,
    lastLen: 0,
    stableSince: 0,
    startedAt: 0,
    diag: [],
  };
  const note = (m) => { _state.diag.push(`${new Date().toISOString().slice(11, 19)} ${m}`); if (_state.diag.length > 60) _state.diag.shift(); log(m); };

  // ── Nhập text vào ô chat ───────────────────────────────────────────────────
  async function insertText(text) {
    const editor = qs(SEL.input);
    if (!editor) return false;
    const target = editor.classList?.contains("ql-editor")
      ? editor
      : (editor.querySelector(".ql-editor") || editor);

    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        target.focus();
        target.click();
        await sleep(120);
        // đặt con trỏ cuối nội dung
        const range = document.createRange();
        range.selectNodeContents(target);
        range.collapse(false);
        const selc = window.getSelection();
        selc.removeAllRanges();
        selc.addRange(range);

        let ok = document.execCommand("insertText", false, text);
        if (!ok || !(target.innerText || "").includes(text.slice(0, 12))) {
          // fallback: gán trực tiếp + báo cho Angular biết
          target.innerHTML = "";
          const p = document.createElement("p");
          p.textContent = text;
          target.appendChild(p);
          target.dispatchEvent(new InputEvent("input", { bubbles: true, data: text, inputType: "insertText" }));
        }
        await sleep(250);
        if ((target.innerText || "").trim().length >= Math.min(10, text.length)) return true;
      } catch (e) { note("insertText lỗi: " + e.message); }
      await sleep(400);
    }
    return false;
  }

  // ── Đính file ──────────────────────────────────────────────────────────────
  function b64ToFile(b64, filename, mime) {
    const raw = atob(b64);
    const buf = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
    return new File([buf], filename, { type: mime || "application/pdf" });
  }

  const CHIP_SEL = [
    "[data-test-id*='file'], [data-test-id*='attachment']",
    ".file-preview, .uploaded-file, .attachment-container, [class*='file-chip']",
    "rich-textarea img, img[src^='blob:'], [class*='thumbnail'], [class*='attachment']",
  ].join(", ");
  const countChips = () => document.querySelectorAll(CHIP_SEL).length;

  function inputAreaText() {
    const area = document.querySelector("input-container, .input-area, rich-textarea")?.closest("input-container, .input-area, form, .chat-input")
      || document.querySelector("input-container, .input-area");
    return (area?.innerText || "").toLowerCase();
  }

  function setFilesOn(inputEl, file) {
    const dt = new DataTransfer();
    dt.items.add(file);
    try { inputEl.files = dt.files; } catch (_) {
      Object.defineProperty(inputEl, "files", { value: dt.files, configurable: true, writable: true });
    }
    inputEl.dispatchEvent(new Event("change", { bubbles: true }));
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
  }

  async function attachFile(file) {
    const baseName = file.name.replace(/\.[^.]+$/, "").slice(0, 24).toLowerCase();
    const chips0 = countChips();
    const sendWasOn = sendEnabled();

    const confirmAttached = async (ms) => {
      const deadline = Date.now() + ms;
      while (Date.now() < deadline) {
        if (countChips() > chips0) return true;
        if (baseName.length > 6 && inputAreaText().includes(baseName.slice(0, 12))) return true;
        if (!sendWasOn && sendEnabled()) return true;
        await sleep(300);
      }
      return false;
    };

    // — Cách 1: input[type=file] có sẵn trong DOM (không cần click gì) —
    try {
      const inputs = [...document.querySelectorAll("input[type='file']")];
      const fi = inputs.find(i => {
        const acc = (i.accept || "").toLowerCase();
        return !acc || acc.includes("pdf") || acc.includes("*") || acc.includes("application");
      }) || inputs[0];
      if (fi) {
        setFilesOn(fi, file);
        if (await confirmAttached(4000)) { note("✅ đính bằng input[type=file] có sẵn"); return true; }
      }
    } catch (e) { note("cách 1 lỗi: " + e.message); }

    // — Cách 2: bấm menu "+" → chọn "Tải tệp lên" → bắt input[type=file] mới mount —
    try {
      const waitNewInput = new Promise(resolve => {
        const seen = new Set([...document.querySelectorAll("input[type='file']")]);
        const obs = new MutationObserver(() => {
          const fresh = [...document.querySelectorAll("input[type='file']")].find(i => !seen.has(i));
          if (fresh) { obs.disconnect(); resolve(fresh); }
        });
        obs.observe(document.body, { childList: true, subtree: true });
        setTimeout(() => { obs.disconnect(); resolve(document.querySelector("input[type='file']")); }, 6000);
      });

      const menuBtn = qs(SEL.uploadMenu);
      if (menuBtn) {
        menuBtn.click();
        await sleep(700);
        // item trong menu: ưu tiên data-test-id, sau đó bắt theo text
        let item = qs(SEL.uploadItem);
        if (!item) {
          item = [...document.querySelectorAll("[role='menuitem'], button, .mat-mdc-menu-item")]
            .find(b => /tải tệp lên|tải lên tệp|upload file|thêm tệp|from computer|tệp từ máy/i.test(b.textContent || "") && visible(b));
        }
        if (item) { item.click(); note("đã bấm item 'Tải tệp lên'"); }
      }
      const fi = await waitNewInput;
      if (fi) {
        setFilesOn(fi, file);
        if (await confirmAttached(6000)) { note("✅ đính qua menu upload"); return true; }
      }
    } catch (e) { note("cách 2 lỗi: " + e.message); }

    // — Cách 3: giả lập paste (ClipboardEvent) — chạy được cả khi tab nền —
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      const editor = qs(SEL.input);
      if (editor) {
        editor.focus();
        await sleep(200);
        editor.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: dt }));
        if (await confirmAttached(4000)) { note("✅ đính bằng paste"); return true; }
      }
    } catch (e) { note("cách 3 lỗi: " + e.message); }

    // — Cách 4: giả lập kéo-thả —
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      const zone = document.querySelector("input-container, .input-area, rich-textarea") || document.body;
      for (const type of ["dragenter", "dragover", "drop"]) {
        zone.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }));
        await sleep(150);
      }
      if (await confirmAttached(4000)) { note("✅ đính bằng drag-drop"); return true; }
    } catch (e) { note("cách 4 lỗi: " + e.message); }

    return false;
  }

  // ── Chờ Gemini upload xong file (nút gửi sáng lại, hết spinner) ────────────
  async function waitUploadFinished(timeoutMs) {
    const deadline = Date.now() + timeoutMs;
    let stable = 0;
    while (Date.now() < deadline) {
      const uploading = !!document.querySelector(
        "input-container mat-progress-bar, input-container .uploading, [class*='upload-progress'], .file-preview [class*='spinner']"
      );
      if (!uploading && sendEnabled()) {
        stable++;
        if (stable >= 3) return true;      // ổn định ~1.5s
      } else {
        stable = 0;
      }
      await sleep(500);
    }
    return sendEnabled();
  }

  // ── Đọc kết quả ────────────────────────────────────────────────────────────
  function lastResponseEl() {
    const nodes = qsAll(SEL.response);
    return nodes.length ? nodes[nodes.length - 1] : null;
  }

  function isStreaming() {
    if (document.querySelector("[aria-live='polite'][aria-busy='true']")) return true;
    if (qs(SEL.stop) && visible(qs(SEL.stop))) return true;
    if (document.querySelector(".shimmer-overlay:not(.done-generating), .loading-indicator, .response-loading")) return true;
    return false;
  }

  // Chữ trên các NÚT của code block ("Tải mã xuống", "Sao chép"...) — không phải tên ngôn ngữ.
  const BTN_TEXT_RE = /tải|sao chép|copy|download|chỉnh sửa|edit|chạy|run|mở/i;

  /** Nhận diện ngôn ngữ của 1 code block: nhãn ở header ("Python"/"Plaintext") hoặc class. */
  function blockLang(codeEl) {
    const holder = codeEl.closest("code-block, .code-block") || codeEl;

    // 1) class language-xxx (chuẩn highlight.js) — đáng tin nhất khi có
    const cls = [...(codeEl.classList || []), ...(holder.classList || [])].join(" ");
    const m = cls.match(/language-([a-z+#]+)/i);
    if (m) return m[1].toLowerCase();

    // 2) nhãn ở header. Duyệt nhiều ứng viên, bỏ những chuỗi là chữ trên nút bấm.
    const cands = [
      ...holder.querySelectorAll(".code-block-decoration span, .code-block-decoration, header span, [class*='language'], [class*='code-block-title']"),
    ];
    for (const el of cands) {
      const t = (el.textContent || "").trim();
      if (!t || t.length > 24 || BTN_TEXT_RE.test(t)) continue;
      return t.toLowerCase().split(/\s+/)[0];
    }

    // 3) dòng đầu của cả khối thường chính là nhãn ngôn ngữ
    const first = (holder.innerText || "").split("\n")[0].trim();
    if (first && first.length <= 24 && !BTN_TEXT_RE.test(first) && /^[a-zA-ZÀ-ỹ+#]+$/.test(first)) {
      return first.toLowerCase();
    }
    return "";
  }

  const CODE_RE = /^\s*(#\s|import\s|from\s+\w+\s+import|def\s|with\s+open|print\(|[a-z_]+\s*=\s*("""|'''|f?"))/m;

  /**
   * Gemini rất hay "hiểu nhầm" yêu cầu OCR ra txt thành: viết code Python ghi file.
   * Khi đó code block chứa nội dung thật nằm trong chuỗi ba nháy — bóc nó ra.
   */
  function unwrapPythonString(t) {
    if (!CODE_RE.test(t)) return t;

    // 1) chuỗi ba nháy ĐÓNG đầy đủ — lấy cái dài nhất
    let best = "";
    const re = /("""|''')([\s\S]*?)\1/g;
    let m;
    while ((m = re.exec(t))) if (m[2].length > best.length) best = m[2];

    // 2) KHÔNG có nháy đóng: Gemini hay hiển thị khối code bị cắt cụt (nội dung dài, DOM
    //    ảo hoá). Khi đó lấy tất cả những gì đứng sau dấu mở. Thiếu còn hơn trả về mã nguồn.
    if (best.length <= 200) {
      const mo = t.match(/(?:"""|''')/);
      if (mo) {
        const sau = t.slice(mo.index + 3);
        if (sau.length > best.length) best = sau;
      }
    }

    if (best.length > 200) {
      // chuỗi Python có thể chứa \n dạng escape nếu Gemini dùng nháy đơn
      return best.replace(/\\n/g, "\n").trim();
    }
    return t;
  }

  // Tiêu đề mở đầu văn bản hành chính VN — chỉ xét ở NGAY ĐẦU text.
  // (Không được dùng cờ /m: khối mã Python có "CHÍNH PHỦ" nằm trong chuỗi ba nháy,
  //  khớp giữa chừng là tưởng nhầm mã nguồn thành văn bản — đã dính ở test [5].)
  const DOC_HEAD_RE = /^(BỘ |CHÍNH PHỦ|CỘNG H[OÒ]À|ỦY BAN|QUỐC HỘI|THỦ TƯỚNG|NGHỊ ĐỊNH|QUYẾT ĐỊNH|THÔNG TƯ|LUẬT\b)/;

  const looksLikeCode = (t) => {
    const s = (t || "").trimStart();
    if (DOC_HEAD_RE.test(s)) return false;
    return CODE_RE.test(s.slice(0, 400));   // mã thì dấu hiệu nằm ngay mấy dòng đầu
  };

  const stripLangLine = s => s.replace(/^(plaintext|text|txt|markdown|md|json|python|py)\s*\n/i, "").trim();

  /**
   * Bóc nội dung ra khỏi rào ```…``` của markdown.
   *
   * Nút "Sao chép" (cả câu trả lời) trả về markdown: câu dẫn + ```text + nội dung + ```.
   * Bản này DÀI HƠN bản của nút "Sao chép mã" nên nếu chỉ so độ dài là chọn nhầm, rồi
   * ghi thẳng cả câu dẫn lẫn dấu rào vào file .txt (đã dính đúng lỗi này).
   */
  function stripFence(t) {
    if (!t || !t.includes("```")) return t;
    let best = "";
    const re = /```[a-zA-Z]*[ \t]*\r?\n([\s\S]*?)```/g;
    let m;
    while ((m = re.exec(t))) if (m[1].length > best.length) best = m[1];
    if (best.length > 200) return best.trim();

    // rào MỞ mà không có rào đóng (câu trả lời bị cắt) -> lấy hết phần sau dấu mở
    const mo = t.match(/```[a-zA-Z]*[ \t]*\r?\n/);
    if (mo) {
      const sau = t.slice(mo.index + mo[0].length).replace(/```[\s\S]*$/, "").trim();
      if (sau.length > 200) return sau;
    }
    return t;
  }

  /**
   * HÀM THUẦN (test được, không đụng DOM): chọn nội dung OCR từ danh sách code block.
   *
   * Gemini hay trả lời 1 lượt gồm 2 khối: khối `Python` (mã nó chạy để ghi file) và khối
   * `Plaintext` (nguyên văn nội dung). Khối Python CHỨA CẢ nội dung trong chuỗi ba nháy nên
   * nó thường DÀI HƠN — chọn theo độ dài là dính nhầm mã. Vì vậy phải xét NHÃN trước.
   *
   * @param {{lang:string,text:string}[]} blocks
   */
  function pickBlockText(blocks) {
    if (!blocks || !blocks.length) return "";
    // Bóc rào markdown TRƯỚC khi so sánh, nếu không bản "cả câu trả lời" (dài hơn vì có
    // thêm câu dẫn + dấu rào) sẽ luôn thắng bản nội dung thuần.
    blocks = blocks.map(b => ({ ...b, text: stripFence(b.text) }));
    const byLen = (a, b) => b.text.length - a.text.length;

    // 1) khối có nhãn văn bản thuần — đúng thứ cần, ưu tiên tuyệt đối
    const plain = blocks
      .filter(b => /^(plaintext|text|txt|markdown|md|none)$/.test(b.lang))
      .sort(byLen)[0];
    if (plain && plain.text.length > 200) return stripLangLine(plain.text);

    // 2) khối không nhãn nhưng nội dung không có mùi code
    const noLang = blocks
      .filter(b => !b.lang && !looksLikeCode(b.text))
      .sort(byLen)[0];
    if (noLang && noLang.text.length > 200) return stripLangLine(noLang.text);

    // 3) chỉ còn khối code -> lấy khối dài nhất rồi bóc chuỗi ba nháy bên trong ra
    return stripLangLine(unwrapPythonString(blocks.slice().sort(byLen)[0].text));
  }

  /** Gom code block trong response cuối rồi giao cho pickBlockText chọn. */
  function longestCodeBlock(root) {
    if (!root) return "";
    const blocks = [];
    const seen = new Set();
    root.querySelectorAll("pre code, pre, code-block, .code-block, [class*='code-container']").forEach(el => {
      const raw = (el.innerText || "").trim();
      if (raw.length < 50) return;                       // bỏ code inline ngắn
      if (seen.has(raw)) return;                         // pre và code lồng nhau -> trùng
      seen.add(raw);
      blocks.push({ lang: blockLang(el), text: raw });
    });
    return pickBlockText(blocks);
  }

  function markdownText(root) {
    if (!root) return "";
    const el = root.querySelector(".markdown-main-panel, .markdown") || root;
    return (el.innerText || "").trim();
  }

  /** Bỏ câu dẫn kiểu "Dưới đây là toàn bộ nội dung..." khi phải fallback lấy cả response. */
  function stripPreamble(t) {
    return t.replace(
      /^(chắc chắn|dưới đây|đây là|sure|here is|here's)[^\n]{0,160}\n+/i, ""
    ).trim();
  }

  function collectText() {
    const root = lastResponseEl();
    if (!root) return { text: "", hasArtifact: false };
    const hasArtifact = !!qs(SEL.openArtifact);
    const code = longestCodeBlock(root);
    const md = markdownText(root);
    // code block luôn ưu tiên: nó là nội dung OCR thuần, không lẫn câu dẫn của Gemini
    let text = code.length > 200 ? code : stripPreamble(md);
    if (!text && md) text = md;
    // Vẫn còn mùi code (Gemini viết Python ghi file, bóc chuỗi không ra) -> báo cho
    // background biết để ưu tiên lấy nội dung từ file artifact thay vì khối chat này.
    return { text, hasArtifact, looksCode: looksLikeCode(text), codeLen: code.length, mdLen: md.length };
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  window.__ocrEngine = {
    version: 1,

    async attachAndSend(prompt, b64, filename, mime) {
      try {
        _state = { phase: "uploading", done: false, text: "", error: null, hasArtifact: false,
                   lastLen: 0, stableSince: 0, startedAt: Date.now(), diag: _state.diag || [] };
        dismissPopups();
        await sleep(300);

        const file = b64ToFile(b64, filename, mime);
        note(`bắt đầu: ${filename} (${(file.size / 1024).toFixed(0)} KB)`);

        const ok = await attachFile(file);
        if (!ok) {
          _state.phase = "error";
          _state.error = "Không đính được file vào Gemini (đã thử 4 cách)";
          return { ok: false, error: _state.error, diag: _state.diag };
        }

        note("chờ Gemini upload xong...");
        const up = await waitUploadFinished(180000);
        if (!up) note("⚠️ hết 180s vẫn chưa thấy nút gửi sáng — thử gửi luôn");
        await sleep(1200);

        _state.phase = "sending";
        dismissPopups();
        const typed = await insertText(prompt);
        if (!typed) note("⚠️ không chắc đã gõ được prompt — vẫn thử gửi");
        await sleep(600);

        // chờ nút gửi sáng rồi bấm
        const deadline = Date.now() + 20000;
        let btn = null;
        while (Date.now() < deadline) {
          btn = qs(SEL.sendReady) || (sendEnabled() ? qs(SEL.send) : null);
          if (btn) break;
          await sleep(400);
        }
        if (btn) {
          await sleep(800);
          btn.click();
          note("✅ đã bấm gửi");
        } else {
          const ed = qs(SEL.input);
          ed?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", keyCode: 13, bubbles: true }));
          note("✅ gửi bằng Enter (fallback)");
        }

        _state.phase = "waiting";
        _state.startedAt = Date.now();
        return { ok: true, diag: _state.diag };
      } catch (e) {
        _state.phase = "error";
        _state.error = e.message;
        return { ok: false, error: e.message, diag: _state.diag };
      }
    },

    /** background gọi mỗi 3s. Xong = hết stream + độ dài text đứng yên >= 6s. */
    getResult(stableMs = 6000) {
      if (_state.done) return { ..._state };
      if (_state.phase !== "waiting") return { ..._state };

      const streaming = isStreaming();
      const { text, hasArtifact, looksCode, codeLen, mdLen } = collectText();
      _state.hasArtifact = hasArtifact;
      _state.looksCode = looksCode;
      _state.text = text;

      const len = text.length;
      if (len !== _state.lastLen) {
        _state.lastLen = len;
        _state.stableSince = Date.now();
        return { ..._state, streaming, codeLen, mdLen };
      }
      if (len < 20) return { ..._state, streaming, codeLen, mdLen };
      if (!_state.stableSince) _state.stableSince = Date.now();

      if (!streaming && Date.now() - _state.stableSince >= stableMs) {
        _state.done = true;
        _state.phase = "done";
        note(`✅ xong: ${len} ký tự (code=${codeLen}, md=${mdLen}, artifact=${hasArtifact})`);
      }
      return { ..._state, streaming, codeLen, mdLen };
    },

    /** Bấm nút "Đang mở" để mở file artifact (khi text trong chat bị cắt). */
    async openArtifact() {
      const btn = qs(SEL.openArtifact);
      if (!btn) return { ok: false, error: "không thấy nút mở file" };
      btn.click();
      note("đã bấm nút mở artifact");
      await sleep(3500);
      return { ok: true };
    },

    /**
     * Chọn bản tốt nhất trong các đoạn text lấy từ nút "Sao chép mã".
     * Dùng lại pickBlockText nên hưởng luôn mọi quy tắc đã kiểm thử:
     * ưu tiên văn bản thuần, khối Python thì bóc chuỗi ba nháy ra (kể cả bị cắt cụt).
     */
    pickFromTexts(list) {
      const blocks = (list || [])
        .filter(t => typeof t === "string" && t.trim().length > 50)
        .map(t => ({ lang: "", text: t.trim() }));
      return pickBlockText(blocks);
    },

    /**
     * Cuộn lớp phủ xuống đáy để ép trình xem render HẾT các trang.
     * Trình xem Drive chỉ dựng <pre> cho trang đã cuộn tới — không cuộn thì file 19 trang
     * chỉ đọc được vài trang đầu, mà vẫn "có text" nên không ai phát hiện ra là thiếu.
     */
    async scrollViewerToEnd(maxVong = 40) {
      const dem = () => document.querySelectorAll("pre.drive-viewer-text-page").length;
      const dau = document.querySelector("pre.drive-viewer-text-page, [class*='drive-viewer']");
      if (!dau) return { trang: 0, vong: 0 };

      let sc = dau.parentElement;
      while (sc && sc.scrollHeight <= sc.clientHeight + 5) sc = sc.parentElement;
      if (!sc) sc = document.scrollingElement || document.documentElement;

      let truoc = -1, vong = 0;
      while (vong < maxVong) {
        vong++;
        sc.scrollTop = Math.min(sc.scrollTop + sc.clientHeight * 0.9, sc.scrollHeight);
        await sleep(320);
        const n = dem();
        if (sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 5 && n === truoc) break;
        truoc = n;
      }
      await sleep(500);
      const trang = dem();
      note(`cuộn lớp phủ ${vong} nhịp → ${trang} trang`);
      return { trang, vong };
    },

    /** Text nằm ngay trong panel/canvas của Gemini (không phải iframe Drive). */
    artifactTextInPage() {
      let best = "";
      const take = (el) => {
        const t = (el?.innerText || "").trim();
        if (t.length > best.length) best = t;
      };

      // Mỗi trang một <pre class="drive-viewer-text-page"> -> GHÉP hết theo thứ tự.
      const trang = [...document.querySelectorAll("pre.drive-viewer-text-page")];
      if (trang.length) {
        best = trang.map(p => (p.innerText || "").replace(/\s+$/, "")).join("\n").trim();
      }

      // 1) container quen thuộc của trình xem / canvas
      document.querySelectorAll(
        "code-immersive-panel, .immersive-editor, [data-test-id='immersive-panel'], " +
        ".drive-viewer-text-content, .drive-viewer-paginated-page, [class*='drive-viewer'] pre, .ProseMirror"
      ).forEach(take);

      // 2) pre bất kỳ (viewer text thuần hay bọc trong pre)
      document.querySelectorAll("pre").forEach(take);

      // 3) Trình xem có thể là overlay ngay trong trang (không phải iframe). Lấy dialog
      //    đang mở rồi bỏ các dòng UI (tên file, nút bấm) ở đầu.
      if (best.length < 500) {
        document.querySelectorAll("[role='dialog'], [aria-modal='true']").forEach(d => {
          const t = (d.innerText || "").trim();
          if (t.length > best.length && t.length > 500) best = t;
        });
      }
      return best;
    },

    closeArtifact() {
      const close = [...document.querySelectorAll("button, [role='button']")]
        .find(b => /close|đóng/i.test(b.getAttribute("aria-label") || "") && visible(b));
      if (close) { try { close.click(); } catch (_) {} }
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", keyCode: 27, bubbles: true }));
      return { ok: true };
    },

    getDiag() { return _state.diag.join("\n"); },
  };

  log("engine loaded");
})();
