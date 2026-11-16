/* TEST CƠ CHẾ LẤY FILE TXT QUA NÚT "TẢI XUỐNG"
 *
 * Dán vào DevTools Console của tab Gemini KHI LỚP PHỦ XEM FILE ĐANG MỞ.
 * Nó làm đúng những gì extension làm: bọc URL.createObjectURL -> bấm nút tải ->
 * đọc lại Blob. Chrome vẫn tải file thật về Downloads (trong extension thì bị huỷ),
 * ở đây kệ nó, mục đích chỉ để xem có bắt được nội dung không.
 *
 * Kết quả mong đợi: in ra "✅ BẮT ĐƯỢC ... ký tự" và 400 ký tự đầu là nội dung công văn.
 */
(async () => {
  const nghi = ms => new Promise(r => setTimeout(r, ms));

  // 1) Bọc createObjectURL để giữ lại Blob
  if (!window.__ocrBlobHook) {
    window.__ocrBlobHook = true;
    window.__ocrBlobs = [];
    const goc = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (obj) => {
      try { if (obj instanceof Blob) window.__ocrBlobs.push(obj); } catch (_) {}
      return goc(obj);
    };
    document.addEventListener("click", (e) => {
      const a = e.target?.closest?.("a[download]");
      if (a?.href?.startsWith("data:")) window.__ocrDataUrl = a.href;
    }, true);
    console.log("① đã cài móc bắt Blob");
  } else {
    console.log("① móc đã có sẵn");
  }

  // 2) Tìm và bấm nút tải
  const KHOP = /tải xuống|tải về|download/i;
  let btn = null, nhan = "";
  for (const e of document.querySelectorAll(
    "[aria-label],[data-tooltip],[title],button,[role='button'],.drive-viewer-download-icon"
  )) {
    const n = e.getAttribute?.("aria-label") || e.getAttribute?.("data-tooltip")
           || e.getAttribute?.("title") || "";
    const laIcon = (e.className || "").toString().includes("drive-viewer-download-icon");
    if (!KHOP.test(n) && !laIcon) continue;
    const b = e.closest("[role='button'], button") || e;
    if (b.offsetParent === null) continue;
    btn = b; nhan = n || "drive-viewer-download-icon";
    break;
  }
  if (!btn) { console.error("✖ KHÔNG tìm thấy nút tải — lớp phủ đã mở chưa?"); return; }
  console.log("② tìm thấy nút:", nhan, btn);

  const truoc = (window.__ocrBlobs || []).length;
  btn.click();
  console.log("③ đã bấm, chờ 3s...");
  await nghi(3000);

  // 3) Đọc lại nội dung
  let best = "";
  for (const b of window.__ocrBlobs || []) {
    try { const t = await b.text(); if (t.length > best.length) best = t; } catch (_) {}
  }
  if (window.__ocrDataUrl) {
    try { const t = await (await fetch(window.__ocrDataUrl)).text(); if (t.length > best.length) best = t; } catch (_) {}
  }

  console.log("④ số Blob bắt thêm được:", (window.__ocrBlobs || []).length - truoc);
  if (best.length > 200) {
    console.log(`✅ BẮT ĐƯỢC ${best.length} ký tự`);
    console.log("--- 400 ký tự đầu ---\n" + best.slice(0, 400));
    console.log("--- 200 ký tự cuối ---\n" + best.slice(-200));
    window.__ketQua = best;      // gõ copy(__ketQua) để chép ra clipboard
    console.log("Gõ  copy(__ketQua)  để chép toàn bộ ra clipboard.");
  } else {
    console.warn("✖ không bắt được Blob → nút tải trỏ thẳng tới URL server.");
    console.warn("   Extension vẫn xử lý được (nó bắt URL qua chrome.downloads).");
    console.warn("   Báo lại tôi dòng này để tôi biết đường nào đang chạy.");
  }
})();
