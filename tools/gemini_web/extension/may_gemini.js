/* may_gemini.js — chạy trong MAIN world của gemini.google.com.
 *
 * Một file = một lượt: chat mới → đính file → gõ prompt → gửi → chờ trả lời xong
 * → bấm nút "Sao chép mã" → lấy nội dung khối plaintext.
 *
 * File đính kèm có hai kiểu, chọn bằng viec.kieu:
 *   - "txt" (mặc định): .txt bản OCR hỏng, nhờ Gemini sửa — đường cũ, giữ nguyên.
 *   - "anh": ảnh PNG scan một trang, để Gemini tự đọc. Ảnh đi từ background sang
 *     đây dưới dạng chuỗi data URL base64, xem fileTuDataURL().
 *
 * Neo DOM lấy từ bản dump ngày 2026-09-16. Mỗi neo đều có phương án dự phòng vì
 * Gemini đổi class liên tục; chỉ có aria-label và data-test-id là tương đối bền.
 */
(() => {
  if (window.__PBL6_SUA_TXT__) return;           // đã bơm rồi thì thôi

  const nghi = (ms) => new Promise((r) => setTimeout(r, ms));

  // Console của TAB không phải Console của service worker. Gom nhật ký vào đây
  // để background kéo về bằng layNhatKy() — kéo được cả trong lúc đang chạy dở,
  // nên lúc treo vẫn nhìn thấy nó đang kẹt ở bước nào.
  const nhatKy = [];
  const log = (...a) => {
    const d = a.map((x) => (typeof x === "string" ? x : String(x))).join(" ");
    nhatKy.push(new Date().toLocaleTimeString("vi-VN") + " " + d);
    if (nhatKy.length > 500) nhatKy.shift();
    console.log("[sua-txt]", ...a);
  };
  const layNhatKy = () => { const r = nhatKy.slice(); nhatKy.length = 0; return r; };

  /** Chờ cho tới khi ham() trả về giá trị "thật", hoặc hết giờ. */
  async function cho(ham, hanMs, nhipMs = 400, ten = "điều kiện") {
    const het = Date.now() + hanMs;
    for (;;) {
      let v;
      try { v = ham(); } catch (_) { v = null; }
      if (v) return v;
      if (Date.now() > het) throw new Error(`quá hạn chờ ${ten} (${Math.round(hanMs / 1000)}s)`);
      await nghi(nhipMs);
    }
  }

  const hien = (el) => el && el.offsetParent !== null && !el.disabled;
  const tim = (...sels) => {
    for (const s of sels) {
      for (const el of document.querySelectorAll(s)) if (hien(el)) return el;
    }
    return null;
  };

  // ── các neo trên trang ──────────────────────────────────────────────────────
  const O = {
    oNhap: () => tim(
      'rich-textarea .ql-editor[contenteditable="true"]',
      '[contenteditable="true"][role="textbox"]'),
    nutGui: () => tim(
      'button[aria-label="Gửi tin nhắn"]',
      '[data-test-id="send-button-container"] button'),
    nutDung: () => tim('button[aria-label="Ngừng tạo câu trả lời"]'),
    nutChatMoi: () => tim(
      '[data-test-id="new-chat-button"] a',
      'a[aria-label="Cuộc trò chuyện mới"]'),
    nutThem: () => tim('button[aria-label="Nội dung tải lên và công cụ"]'),
    // Trang có nhiều input[type=file] (ảnh, máy ảnh, ổ đĩa...). Vớ cái đầu tiên
    // là có khi nhét .txt vào ô chỉ nhận ảnh — Angular lặng lẽ bỏ qua.
    // anh=true thì tìm ô nhận ảnh, ngược lại tìm ô nhận .txt (mặc định, y như cũ).
    oFile: (anh) => {
      const ds = [...document.querySelectorAll('input[type=file]')];
      const hop = (i) => {
        const a = (i.getAttribute("accept") || "").toLowerCase();
        if (!a || a.indexOf("*/*") >= 0) return true;
        return anh
          ? (a.indexOf("image/") >= 0 || a.indexOf(".png") >= 0)
          : (a.indexOf("text/plain") >= 0 || a.indexOf(".txt") >= 0);
      };
      return ds.find(hop) || ds[0] || null;
    },
    // CHỈ chip ở Ô SOẠN. Không lấy '[data-test-id="uploaded-file"]' — cái đó là
    // chip nằm trong TIN NHẮN ĐÃ GỬI (user-query-file-preview) của lượt trước.
    // Lẫn hai thứ này là tưởng file đã lên xong trong khi chưa đính gì cả.
    chipFile: () => tim('uploader-file-preview', 'gem-attachment'),
    traLoi: () => document.querySelector('div.markdown.markdown-main-panel[aria-busy]'),
    khoiMa: () => document.querySelectorAll('code[data-test-id="code-content"]'),
    nutSaoChepMa: () => {
      // data-test-id nằm trên gem-icon-button, nút thật là <button> con
      const g = document.querySelector('[data-test-id="gem-copy-button"]');
      if (g) { const b = g.querySelector("button") || g; if (hien(b)) return b; }
      return tim('button[aria-label="Sao chép mã"]');
    },
    // Khi bản trả về dài, Gemini bỏ khối mã và mở CANVAS (trình soạn thảo bên phải).
    // Lúc đó không có nút "Sao chép mã" nào để bấm — phải nhận ra và xử lý riêng.
    canvas: () => tim('#extended-response-markdown-content .ProseMirror',
                      '#extended-response-markdown-content > div'),
    chipCanvas: () => tim('immersive-entry-chip inline-preview'),
  };

  // Tên file đang làm — để nhận ra ĐÚNG chip của nó, không nhầm chip sót lại.
  let tenDangLam = "";

  /** Chip đính kèm mang đúng tên file này (không phải chip của lượt trước). */
  // gem-attachment là component dùng chung: nó vừa là chip ở ô soạn, vừa là chip
  // trong TIN NHẮN ĐÃ GỬI. Không loại nhóm thứ hai ra thì máy khớp trúng chip
  // của lượt trước, tưởng file đã lên trong khi ô soạn trống trơn.
  const TRONG_TIN_DA_GUI =
    'user-query, user-query-file-preview, message-content, .conversation-container';
  const dsChip = () => [...document.querySelectorAll(
      'uploader-file-preview, gem-attachment')]
    .filter((el) => hien(el) && !el.closest(TRONG_TIN_DA_GUI));

  // Chip ẢNH ở ô soạn KHÔNG mang tên file — nó chỉ là một thumbnail
  // <img src="blob:..."> (bản dump DOM ngày 17-09 cho thấy chip ảnh trong tin đã
  // gửi là <img data-test-id="uploaded-img">, không có chữ nào). Nên so theo tên
  // như chế độ txt là chờ vô ích tới hết 600s.
  const dsChipAnh = () => [...document.querySelectorAll(
      'img[src^="blob:"], img[data-test-id="uploaded-img"]')]
    .filter((el) => hien(el) && !el.closest(TRONG_TIN_DA_GUI));

  let kieuDangLam = "txt";

  // Gemini cắt GIỮA tên file khi hiện chip ("0148_38_20..., thạc sĩ,"), nên khoá
  // 12 ký tự có thể không bao giờ khớp. Thử thu ngắn dần.
  const chipCuaFile = (ten) => {
    const t = ten || "";
    if (!t) return null;
    const khoas = [t.slice(0, 12), t.slice(0, 10), t.slice(0, 8)];
    for (const el of dsChip()) {
      const chu = el.textContent || "";
      for (const k of khoas) if (k && chu.indexOf(k) >= 0) return el;
    }
    if (kieuDangLam === "anh") {
      // Một trang = một lượt, và chatMoi() đã dọn sạch ô soạn trước đó, nên
      // "có ảnh nào đó ở ô soạn" là đủ chắc. Ưu tiên chip có thumbnail.
      for (const el of dsChip()) if (el.querySelector("img")) return el;
      const a = dsChipAnh()[0];
      if (a) return a.closest("uploader-file-preview, gem-attachment") || a;
    }
    return null;
  };

  /** Xoá sạch chữ nháp trong ô nhập. */
  async function xoaONhap() {
    const o = O.oNhap();
    if (!o || o.textContent.trim() === "") return;
    await datChu(o, "");
  }

  // ── các bước ───────────────────────────────────────────────────────────────

  async function chatMoi() {
    // TUYỆT ĐỐI không dùng location.href ở đây: cả chayMotFile chạy trong MỘT lần
    // executeScript, điều hướng trang là giết luôn frame -> "Frame with ID 0 was
    // removed", mất trắng việc đang làm (đã gặp ở 0112). Không thấy nút thì báo
    // lỗi tạm thời để cầu xếp lại hàng chờ, background sẽ dựng lại tab.
    const a = O.nutChatMoi();
    if (!a) throw new Error("không thấy nút Cuộc trò chuyện mới (tab hỏng?)");
    a.click();
    await nghi(1200);
    // Bấm "Cuộc trò chuyện mới" KHÔNG tự xoá chữ nháp trong ô nhập, cũng không
    // xoá ngay chip file của lượt trước. Phải tự dọn, nếu không:
    //   - chữ nháp còn lại -> lượt sau chờ ô nhập rỗng mãi không được
    //   - chip cũ còn lại  -> dinhFile tưởng file mới đã lên xong (đây là lý do
    //     cả 10 tab đứng im với prompt đã gõ mà không có file nào đính kèm)
    const het = Date.now() + 90000;
    for (;;) {
      const o = O.oNhap();
      if (o && o.textContent.trim() === "" && !O.chipFile()) break;
      if (Date.now() > het) {
        throw new Error("không dọn được ô nhập / chip file của lượt trước");
      }
      await xoaONhap();
      await nghi(700);
    }
    await nghi(500);
  }

  /** Dựng lại File ảnh từ chuỗi data URL mà background gửi sang.
   *
   *  executeScript chỉ truyền được thứ JSON hoá được, Blob/File không đi lọt,
   *  nên background đổi byte PNG thành "data:image/png;base64,..." rồi gửi
   *  chuỗi đó. Ở đây giải base64 về Uint8Array và bọc lại thành File.
   */
  function fileTuDataURL(dataURL, tenFile) {
    const chuoi = String(dataURL || "");
    const phay = chuoi.indexOf(",");
    if (!/^data:/.test(chuoi) || phay < 0) {
      throw new Error("ảnh gửi sang không phải data URL");
    }
    const kieuMime = (chuoi.slice(0, phay).match(/^data:([^;,]+)/) || [])[1]
      || "image/png";
    const tho = atob(chuoi.slice(phay + 1));
    const byte = new Uint8Array(tho.length);
    for (let i = 0; i < tho.length; i++) byte[i] = tho.charCodeAt(i);
    return new File([byte], tenFile, { type: kieuMime });
  }

  async function dinhFile(tenFile, noiDung, kieu) {
    tenDangLam = tenFile;
    kieuDangLam = kieu === "anh" ? "anh" : "txt";
    const laAnh = kieu === "anh";
    const f = laAnh
      ? fileTuDataURL(noiDung, tenFile)
      : new File([noiDung], tenFile, { type: "text/plain" });
    if (laAnh) log("dựng file ảnh " + f.size + " byte, type=" + f.type);
    const dt = new DataTransfer();
    dt.items.add(f);

    // Cách 1 — input[type=file] có sẵn trong DOM (không phải bấm gì)
    let inp = O.oFile(laAnh);
    if (!inp) {
      // Cách 2 — bấm "+" để Angular mount input rồi bắt lấy
      const t = O.nutThem();
      if (t) {
        t.click();
        try {
          inp = await cho(() => O.oFile(laAnh), 4000, 200, "input file");
        } catch (_) {}
        document.body.click();                    // đóng menu lại
      }
    }
    if (inp) {
      log("đính qua input[type=file] accept="
        + JSON.stringify(inp.getAttribute("accept") || ""));
      inp.files = dt.files;
      inp.dispatchEvent(new Event("change", { bubbles: true }));
      inp.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      log("không thấy input[type=file] — thả file vào dropzone");
      // Cách 3 — thả file vào vùng drop
      const vung = document.querySelector(".xap-uploader-dropzone") || document.body;
      for (const kieu of ["dragenter", "dragover", "drop"]) {
        vung.dispatchEvent(new DragEvent(kieu, {
          bubbles: true, cancelable: true, dataTransfer: dt,
        }));
      }
    }
    // Chờ ĐÚNG chip mang tên file này. Chờ "chip bất kỳ" là dính chip còn sót
    // của lượt trước, tưởng xong rồi trong khi Gemini chưa hề nhận file.
    const het = Date.now() + 600000;
    for (let vong = 0; ; vong++) {
      const chip = chipCuaFile(tenFile);
      if (chip) {
        log("khớp chip <" + chip.tagName.toLowerCase() + "> "
          + JSON.stringify((chip.textContent || "").trim().slice(0, 48)));
        break;
      }
      if (Date.now() > het) {
        throw new Error("quá hạn chờ Gemini nhận file " + tenFile.slice(0, 20));
      }
      if (vong && vong % 12 === 0) {            // ~10 giây in một lần
        const cs = dsChip().map((e) => (e.textContent || "").trim().slice(0, 40));
        log("chờ chip file " + Math.round((Date.now() - (het - 600000)) / 1000)
          + "s — chip: " + (cs.length ? JSON.stringify(cs) : "không có")
          + " · ảnh blob ở ô soạn: " + dsChipAnh().length);
      }
      await nghi(800);
    }
    await nghi(1200);
  }

  /** Đặt chữ vào ô soạn. Thử ba đường, đường nào ăn thì dừng.
   *
   *  1. execCommand — ĐƯỜNG CHÍNH, y như bản đầu. Đòi cửa sổ Chrome đang focus.
   *  2. Đối tượng Quill (__quill / Quill.find) — không cần focus, dùng khi (1) trượt.
   *  3. Sự kiện paste giả — bản Quill này dùng div.ql-clipboard ẩn nên thường
   *     không ăn; giữ làm đường lui cuối.
   */
  function timQuill(o) {
    // Quill 1.x gắn instance vào container qua `__quill`; Quill 2.x bỏ đi và
    // tra bằng Quill.find(). Thử cả hai, và dò ngược lên mọi tổ tiên vì không
    // chắc Gemini gắn ở tầng nào.
    const ungVien = [];
    for (let p = o; p; p = p.parentElement) ungVien.push(p);
    for (const sel of ["rich-textarea.ql-container", ".ql-container"]) {
      const el = document.querySelector(sel);
      if (el && ungVien.indexOf(el) < 0) ungVien.push(el);
    }
    for (const el of ungVien) {
      if (el && el.__quill) return el.__quill;
    }
    if (window.Quill && typeof window.Quill.find === "function") {
      for (const el of ungVien) {
        try {
          const q = window.Quill.find(el);
          if (q && typeof q.setText === "function") return q;
        } catch (_) {}
      }
    }
    return null;
  }

  const thoatHtml = (d) => d.replace(/&/g, "&amp;").replace(/</g, "&lt;")
                            .replace(/>/g, "&gt;");
  const thanhP = (text) => text.split("\n")
    .map((d) => "<p>" + (d ? thoatHtml(d) : "<br>") + "</p>").join("");

  // Ghi thẳng vào DOM của ô soạn. Quill 1.x theo dõi ô soạn bằng MutationObserver
  // rồi dựng lại delta từ DOM, nên sửa DOM tay nó vẫn nuốt. Không cần focus,
  // không cần tab đang ở tiền cảnh.
  function datBangDOM(o, text) {
    o.innerHTML = text ? thanhP(text) : "<p><br></p>";
    o.classList.toggle("ql-blank", !text);
    try {
      const r = document.createRange();
      r.selectNodeContents(o);
      r.collapse(false);
      const vc = window.getSelection();
      vc.removeAllRanges();
      vc.addRange(r);
    } catch (_) {}
    o.dispatchEvent(new InputEvent("input", {
      bubbles: true, inputType: "insertText", data: text,
    }));
    o.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // Ô nhập của Gemini là Quill 1.x: theme ql-bubble, có div.ql-clipboard ẩn.
  // Bản Quill này KHÔNG đọc e.clipboardData. Handler onPaste của nó chỉ focus
  // vào div.ql-clipboard rồi 1ms sau đọc innerHTML CỦA CHÍNH DIV ĐÓ và dịch
  // thành delta. Vậy cách chèn chắc nhất — và không cần cửa sổ Chrome được
  // focus — là tự nhét chữ vào div ẩn ấy rồi mới bắn sự kiện paste.
  function datBangKhayDan(o, text) {
    const khay = (o.parentElement && o.parentElement.querySelector(".ql-clipboard"))
      || document.querySelector("div.ql-clipboard");
    if (!khay) return false;

    o.focus();
    // Quill lấy vùng chọn từ DOM thật; không có range thì getSelection() trả
    // null và onPaste ném lỗi ngay. Chọn trọn nội dung cũ để bản dán đè lên.
    try {
      const r = document.createRange();
      r.selectNodeContents(o);
      const vc = window.getSelection();
      vc.removeAllRanges();
      vc.addRange(r);
    } catch (_) { return false; }

    khay.innerHTML = thanhP(text);

    const dt = new DataTransfer();     // phòng khi Gemini nâng lên Quill 2
    dt.setData("text/plain", text);
    o.dispatchEvent(new ClipboardEvent("paste", {
      bubbles: true, cancelable: true, clipboardData: dt,
    }));
    return true;
  }

  async function datChu(o, text) {
    const du = () => text === ""
      ? o.textContent.trim() === ""
      : o.textContent.trim().length > 30;

    // 1) execCommand — ĐƯỜNG CHÍNH, đúng như bản đầu đã chạy xong 172 file.
    //    Điều kiện duy nhất: cửa sổ Chrome phải đang được focus.
    o.focus();
    document.execCommand("selectAll", false, null);
    if (text) document.execCommand("insertText", false, text);
    else document.execCommand("delete", false, null);
    o.dispatchEvent(new InputEvent("input", { bubbles: true }));
    await nghi(400);
    if (du()) return "execCommand";
    log("execCommand trượt — hasFocus=" + document.hasFocus()
      + " activeElement=" + (document.activeElement
          ? document.activeElement.tagName + "." + (document.activeElement.className || "")
              .split(" ")[0]
          : "null")
      + " ô nhập đang có " + o.textContent.trim().length + " ký tự");

    // Mấy đường dưới chỉ chạy khi đường chính trượt (thường vì cửa sổ Chrome
    // mất focus — mở DevTools ra xem là đủ để làm hỏng execCommand).
    const khayChay = datBangKhayDan(o, text);
    if (khayChay) {
      await nghi(500);
      if (du()) { log("đặt chữ bằng khay dán của Quill"); return "khay"; }
      log("khay dán trượt — ô nhập vẫn " + o.textContent.trim().length + " ký tự");
    } else {
      log("không dựng được khay dán (không thấy div.ql-clipboard?)");
    }

    datBangDOM(o, text);
    await nghi(500);
    if (du()) { log("đặt chữ bằng ghi thẳng DOM"); return "dom"; }
    log("ghi thẳng DOM trượt — ô nhập còn " + o.textContent.trim().length + " ký tự");

    const q = timQuill(o);
    if (q) {
      try {
        q.setText(text, "user");
        if (text) q.setSelection(q.getLength() - 1, 0, "user");
        o.dispatchEvent(new InputEvent("input", { bubbles: true }));
        await nghi(400);
        if (du()) { log("đặt chữ bằng Quill API"); return "quill"; }
      } catch (e) { log("Quill API lỗi:", String((e && e.message) || e)); }
    } else { log("không thấy đối tượng Quill (__quill / Quill.find)"); }

    try {
      o.focus();
      const dt = new DataTransfer();
      dt.setData("text/plain", text);
      o.dispatchEvent(new ClipboardEvent("paste", {
        bubbles: true, cancelable: true, clipboardData: dt,
      }));
      o.dispatchEvent(new InputEvent("input", { bubbles: true }));
      await nghi(600);
      if (du()) { log("đặt chữ bằng paste giả"); return "paste"; }
    } catch (_) {}

    return null;
  }

  async function goPrompt(text) {
    const o = await cho(() => O.oNhap(), 60000, 300, "ô nhập");
    for (let lan = 1; lan <= 3; lan++) {
      const cach = await datChu(o, text);
      if (cach) return cach;
      log("gõ prompt hụt, thử lại lần " + lan);
      await nghi(1200);
    }
    throw new Error("không đặt được prompt vào ô nhập (cả 3 cách đều trượt)");
  }

  /** Bấm gửi — CHỈ khi Gemini đã tải xong file.
   *
   *  Chip file hiện ra ngay lúc chọn file, nhưng lúc đó Gemini còn đang tải lên.
   *  Dấu hiệu tải xong là nút "Gửi tin nhắn" bật lên — trước đó nút không tồn tại.
   *  Gửi sớm thì Gemini trả lời chay, không hề đọc file, mà bản trả về vẫn trông
   *  hợp lệ nên chốt an toàn ở cầu khó bắt. Vì vậy phải chờ ở đây cho chắc.
   *
   *  Chip biến mất giữa chừng = Gemini từ chối file; bắt sớm cho khỏi chờ phí.
   */
  async function bamGui(hanMs = 600000) {
    const het = Date.now() + hanMs;
    // Bản đầu lấy "nút gửi sáng lên" làm tín hiệu tải file xong. Sai: nút gửi
    // sáng ngay khi ô nhập CÓ CHỮ. Từ lúc chèn được câu lệnh, tín hiệu đó luôn
    // đúng nên vòng chờ thoát tức thì, gửi khi file còn chưa lên xong.
    // Tín hiệu thật là chính cái chip, và phải đứng yên một lúc.
    let yenTu = 0;
    for (;;) {
      const chip = chipCuaFile(tenDangLam);
      if (!chip) {
        throw new Error("không có chip file của "
          + String(tenDangLam).slice(0, 24) + " ở ô soạn");
      }
      const dangTai = !!chip.querySelector(
        'mat-progress-bar, mat-spinner, [role="progressbar"], .loading');
      const n = O.nutGui();
      if (n && !dangTai) {
        if (!yenTu) yenTu = Date.now();
        if (Date.now() - yenTu > 1500) {
          log("file đã tải xong, gửi");
          n.click();
          break;
        }
      } else { yenTu = 0; }
      if (Date.now() > het) {
        throw new Error("quá hạn chờ Gemini tải xong file ("
          + Math.round(hanMs / 1000) + "s)");
      }
      await nghi(500);
    }
    // Nút "Ngừng tạo câu trả lời" xuất hiện = Gemini đã nhận và đang chạy
    await cho(() => O.nutDung() || O.nutSaoChepMa() || O.canvas(),
              600000, 500, "Gemini bắt đầu trả lời");
  }

  /** Chờ Gemini viết xong. KHÔNG có giới hạn thời gian.
   *
   *  Xong khi hội đủ bốn điều: mất nút "Ngừng tạo câu trả lời", markdown có
   *  aria-busy="false", đã có nội dung, và độ dài đứng yên 3 giây.
   *
   *  Gemini luôn trả về, chỉ là nó xử lý lâu — nhất là khi chạy nhiều luồng.
   *  Nên ở đây không đặt hạn nào theo đồng hồ. Chừng nào còn DẤU HIỆU SỐNG thì
   *  còn chờ, dù mất một tiếng:
   *    - còn nút "Ngừng tạo câu trả lời"   -> Gemini đang chạy
   *    - markdown còn aria-busy="true"     -> đang dựng câu trả lời
   *    - nội dung vừa dài ra               -> đang stream
   *
   *  Chỉ bỏ cuộc khi MẤT SẠCH ba dấu hiệu trên trong 5 phút liền — lúc đó không
   *  phải Gemini chậm mà là tab chết / câu trả lời biến mất.
   */
  async function choTraLoiXong(hanChetMs = 300000) {
    let daiTruoc = -1, yenTu = 0, vanXuoiTu = 0, conSong = Date.now();
    for (;;) {
      const dangChay = !!O.nutDung();
      const tl = O.traLoi();
      const ban = tl && tl.getAttribute("aria-busy") === "false";
      const khoi = O.khoiMa();
      const cv = O.canvas();
      const dai = khoi.length
        ? [...khoi].reduce((s, k) => s + k.textContent.length, 0)
        : (cv ? cv.textContent.length : 0);

      if (dangChay || (tl && !ban) || dai !== daiTruoc) conSong = Date.now();

      if (!dangChay && ban && dai > 0) {
        if (dai === daiTruoc) {
          if (!yenTu) yenTu = Date.now();
          if (Date.now() - yenTu > 3000) return dai;   // đứng yên 3s -> chốt
        } else { yenTu = 0; }
      } else { yenTu = 0; }

      // Trả lời xong mà KHÔNG có khối mã lẫn Canvas, nhưng bảng trả lời lại có
      // chữ -> Gemini đáp bằng văn xuôi. Hầu hết là câu từ chối ("tôi không có
      // quyền truy cập vào nội dung đó"). Bản đầu cứ ngồi đếm khối mã nên mỗi
      // lần từ chối tốn trọn 300s rồi mới bung lỗi mơ hồ. Bắt ngay tại đây.
      if (!dangChay && ban && dai === 0 && tl) {
        const chu = (tl.textContent || "").trim();
        if (chu.length > 40) {
          if (!vanXuoiTu) vanXuoiTu = Date.now();
          if (Date.now() - vanXuoiTu > 3000) {
            // PHAN BIET hai chuyen rat khac nhau, dung goi chung la "tu choi":
            //  - co "```" hoac moc [Trang  -> Gemini DA LAM, chi la rao khoi ma
            //    dat sai cho (dinh vao cuoi cau) nen trinh dung khong tao
            //    <code data-test-id="code-content">. Gap that voi 0112 tren
            //    Flash-Lite: no lam tron 1.042 khoi ma may van bao hong.
            //  - khong co gi trong so do -> moi thuc su la cau tu choi ngan.
            const coHang = chu.indexOf("```") >= 0 || chu.indexOf("[Trang") >= 0;
            if (coHang) {
              // CO noi dung, chi la rao ``` dat sai cho nen khong thanh khoi ma.
              // KHONG duoc nem loi o day: nem thi bamSaoChepVaLay() (noi co ham
              // vot) khong bao gio chay toi. Tra ve de di tiep.
              log("trả lời xong nhưng không có khối mã — sang bước vớt nội dung");
              return 0;
            }
            throw new Error("Gemini đáp bằng văn xuôi, không có khối mã: "
              + JSON.stringify(chu.slice(0, 800)));
          }
        } else { vanXuoiTu = 0; }
      } else { vanXuoiTu = 0; }

      daiTruoc = dai;

      const chet = Date.now() - conSong;
      if (chet > hanChetMs) {
        throw new Error("mất hết dấu hiệu Gemini đang chạy suốt "
          + Math.round(chet / 1000) + "s (đang có " + dai + " ký tự)");
      }
      await nghi(1000);
    }
  }

  /** Bấm nút "Sao chép mã" rồi lấy nội dung khối mã.
   *
   *  Vẫn bấm nút thật, nhưng giá trị lấy về đọc từ textContent của khối mã —
   *  xem ghi chú trong thân hàm.
   */
  /** Dung lai van ban khi Gemini khong dung duoc khoi ma.
   *  Dung innerText chu khong phai textContent: innerText giu xuong dong giua
   *  cac khoi (<p>, <li>, <pre>), textContent thi dinh het lam mot cuc.
   *  CANH BAO: <ol><li> bi mat so thu tu "1." "2." vi Chrome khong dua marker
   *  vao innerText. Nen ban vot ve PHAI coi la nghi ngo, khong cho thang vao
   *  thu muc chinh. */
  function votTuBangTraLoi(pham) {
    if (!pham || !pham.innerText) return "";
    let t = pham.innerText;
    // Bo cau mo dau + rao mo. Rao co the la ```, ```text, ```plaintext...
    const mo = t.search(/```[a-zA-Z]*/);
    if (mo >= 0) {
      t = t.slice(mo).replace(/^```[a-zA-Z]*[ \t]*\r?\n?/, "");
    }
    // Bo rao dong o cuoi neu co.
    t = t.replace(/\r?\n?```[ \t]*$/, "").trim();
    return t.length > 200 ? t : "";
  }

  async function bamSaoChepVaLay() {
    // Văn bản dài thì Gemini CHIA LÀM NHIỀU KHỐI MÃ nối tiếp nhau. Bản đầu lấy
    // khối dài nhất rồi bỏ phần còn lại -> 0411 chỉ lấy được 414/194.886 ký tự
    // (đúng cái trang bìa phụ lục), 0308 lấy 41.742/92.140. Phải ghép hết.
    // Chỉ ghép khối của LƯỢT TRẢ LỜI CUỐI: sau khi xinLaiPlaintext() thì trên
    // trang còn khối của lượt hỏng trước đó.
    const bangTraLoi = [...document.querySelectorAll("div.markdown.markdown-main-panel")];
    const pham = bangTraLoi.length ? bangTraLoi[bangTraLoi.length - 1] : document;
    let khoi = [...pham.querySelectorAll('code[data-test-id="code-content"]')];
    if (!khoi.length) khoi = [...O.khoiMa()];
    if (!khoi.length) {
      // Gemini hay dan rao ```plaintext vao NGAY CUOI mot cau mo dau, kieu
      //   "...khong co kha nang tra loi yeu cau do.```plaintext" roi xuong dong
      // Markdown doi ``` phai dung dau dong, nen trinh dung khong tao
      // <code data-test-id="code-content"> — noi dung van co du, chi la nam
      // duoi dang <p>/<ol> thuong. Xay ra ca tren Flash lan Flash-Lite.
      const vot = votTuBangTraLoi(pham);
      if (vot) {
        log("không có khối mã (rào ``` đặt sai chỗ) — vớt "
          + vot.length + " ký tự từ bảng trả lời");
        return { text: vot, nguon: "vot_markdown" };
      }
      throw new Error("không thấy khối mã nào trong câu trả lời");
    }
    if (khoi.length > 1) {
      log("Gemini chia " + khoi.length + " khối mã: "
        + khoi.map((k) => k.textContent.length).join(" + ") + " ký tự — ghép hết");
    }
    const to = khoi[0];

    const nut = O.nutSaoChepMa();
    if (nut) {
      nut.click();
      log("đã bấm nút Sao chép mã");
      await nghi(700);
    } else {
      log("không thấy nút Sao chép mã — lấy thẳng nội dung khối");
    }

    // KHÔNG đọc clipboard nữa. Tab ở nền thì writeText của chính Gemini ném
    // NotAllowedError ("Document is not focused"), clipboard giữ nguyên text của
    // FILE TRƯỚC -> so độ dài trùng là ghi nhầm file. textContent của khối mã là
    // cùng một chuỗi và không phụ thuộc focus, nên dùng thẳng nó.
    const text = khoi.map((k) => k.textContent).join("\n");
    return { text, nguon: khoi.length > 1 ? "dom (" + khoi.length + " khối)" : "dom" };
  }

  /** Dựng lại văn bản từ Canvas.
   *
   *  Canvas không phải khối mã mà là markdown đã render, nên bản lấy ra KHÔNG bằng
   *  bản gốc: danh sách đánh số mất số thứ tự, bảng bị ép thành dòng có dấu |,
   *  dòng trống bị gộp. Vì vậy phải trả số thứ tự của <ol> lại và phải báo cảnh
   *  báo lên cầu để người đọc duyệt tay. Đây chỉ là đường lui.
   */
  function docCanvas() {
    const goc = O.canvas();
    if (!goc) return "";
    const dong = [];
    for (const con of goc.children) {
      const ten = con.tagName;
      if (ten === "OL") {
        let i = 1;
        for (const li of con.children) dong.push(i++ + ". " + li.innerText);
      } else if (ten === "UL") {
        for (const li of con.children) dong.push("- " + li.innerText);
      } else {
        dong.push(con.innerText);
      }
    }
    return dong.join("\n");
  }

  /** Canvas thì xin Gemini xuất lại thành khối mã plaintext.
   *
   *  Bản trong khối mã là nguyên văn, không bị markdown bóp méo — nên luôn thử
   *  cách này trước khi đành lấy từ Canvas.
   */
  async function xinLaiPlaintext() {
    await goPrompt(
      "Hãy xuất lại TOÀN BỘ nội dung vừa rồi trong MỘT khối mã plaintext duy nhất, " +
      "không dùng Canvas, không dùng bảng markdown, không rút gọn. " +
      "Giữ nguyên từng dòng và mọi mốc trang ----- [Trang N] -----");
    await bamGui();
    await cho(() => O.khoiMa().length > 0, 600000, 1000, "Gemini mở khối mã");
    await choTraLoiXong();
  }

  /** Lấy kết quả, dù Gemini trả bằng khối mã hay bằng Canvas. */
  async function layKetQua() {
    if (O.khoiMa().length) return await bamSaoChepVaLay();

    if (O.canvas()) {
      log("Gemini trả bằng Canvas — xin xuất lại thành khối mã plaintext");
      try {
        await xinLaiPlaintext();
        if (O.khoiMa().length) {
          const r = await bamSaoChepVaLay();
          return { text: r.text, nguon: "khối mã (xin lại sau Canvas)" };
        }
      } catch (e) {
        log("xin lại không được:", String((e && e.message) || e));
      }
      const text = docCanvas();
      if (text.trim().length < 200) throw new Error("đọc Canvas ra rỗng");
      return { text, nguon: "canvas" };
    }

    // Khong khoi ma, khong Canvas — nhung noi dung van co the nam duoi dang
    // <p>/<ol> thuong vi Gemini dan rao ```plaintext vao cuoi cau mo dau.
    // Day la duong cuoi, phai thu truoc khi bao hong.
    const bang = [...document.querySelectorAll("div.markdown.markdown-main-panel")];
    const vot = votTuBangTraLoi(bang.length ? bang[bang.length - 1] : null);
    if (vot) {
      log("không có khối mã lẫn Canvas — vớt " + vot.length
        + " ký tự từ bảng trả lời");
      return { text: vot, nguon: "vot_markdown" };
    }

    throw new Error("không thấy khối mã lẫn Canvas trong câu trả lời");
  }

  // ── một file trọn vẹn ──────────────────────────────────────────────────────
  async function chayMotFile(viec) {
    const t0 = Date.now();
    try {
      log("bắt đầu", viec.id, viec.ten_file,
        viec.kieu === "anh" ? "(ảnh)" : "(txt)");
      await chatMoi();
      log("đã mở chat mới");
      await dinhFile(viec.ten_file, viec.noi_dung, viec.kieu);
      log("đã đính file");
      const cach = await goPrompt(viec.prompt);
      log("đã chèn câu lệnh bằng", cach);
      await bamGui();
      log("đã bấm gửi");

      const dai = await choTraLoiXong();
      log("trả lời xong,", dai, "ký tự");

      const { text, nguon } = await layKetQua();
      log("lấy được", text.length, "ký tự từ", nguon,
        `(${Math.round((Date.now() - t0) / 1000)}s)`);
      return { ok: true, text, nguon, nhat_ky: layNhatKy() };
    } catch (e) {
      const loi = String((e && e.message) || e);
      // Quá hạn / quá tải là tạm thời -> cho cầu xếp lại hàng chờ, không đánh hỏng hẳn
      // "văn xuôi" = Gemini từ chối đọc ảnh. Từ chối là ngẫu nhiên (cùng một
      // tài liệu, trang được trang không) nên phải cho thử lại, không đánh hỏng hẳn.
      const tamThoi = /quá hạn|dấu hiệu|văn xuôi|khối mã|quota|429|503|network|fetch|Frame/i
        .test(loi);
      log("LỖI:", loi);
      return { ok: false, loi, tam_thoi: tamThoi, nhat_ky: layNhatKy() };
    }
  }

  window.__PBL6_SUA_TXT__ = { chayMotFile, layNhatKy, O };
  log("máy đã sẵn sàng");
})();
