/* TEST v2 — CÀI MÓC VÀO CẢ CÁC IFRAME (bản v1 chỉ cài ở frame trên cùng nên bắt hụt).
 *
 * Dán vào DevTools Console của tab Gemini KHI LỚP PHỦ XEM FILE ĐANG MỞ.
 * Cho biết chính xác nút "Tải xuống" đi đường nào: Blob, data:, blob-URL hay URL server.
 */
(async () => {
  const nghi = ms => new Promise(r => setTimeout(r, ms));

  // Gom mọi window đọc được: trên cùng + các iframe CÙNG ORIGIN
  const cacWin = [window];
  document.querySelectorAll("iframe").forEach(f => {
    try { if (f.contentWindow && f.contentDocument) cacWin.push(f.contentWindow); } catch (_) {}
  });
  console.log(`① đọc được ${cacWin.length}/${document.querySelectorAll("iframe").length + 1} frame`);

  for (const w of cacWin) {
    if (w.__ocrHook2) continue;
    w.__ocrHook2 = true;
    w.__blobs = [];
    w.__hrefs = [];
    try {
      const goc = w.URL.createObjectURL.bind(w.URL);
      w.URL.createObjectURL = (o) => {
        try { if (o instanceof w.Blob || o instanceof Blob) w.__blobs.push(o); } catch (_) {}
        const u = goc(o);
        w.__hrefs.push("createObjectURL -> " + u);
        return u;
      };
      const moGoc = w.open?.bind(w);
      if (moGoc) w.open = (u, ...r) => { w.__hrefs.push("window.open -> " + u); return moGoc(u, ...r); };
      w.document.addEventListener("click", (e) => {
        const a = e.target?.closest?.("a[download], a[href]");
        if (a?.href) w.__hrefs.push("a.click -> " + a.href);
      }, true);
      const fGoc = w.fetch?.bind(w);
      if (fGoc) w.fetch = (u, ...r) => { w.__hrefs.push("fetch -> " + String(u).slice(0, 120)); return fGoc(u, ...r); };
    } catch (e) { console.warn("  không móc được 1 frame:", e.message); }
  }
  console.log("② đã cài móc (Blob + window.open + a.click + fetch)");

  // Tìm và bấm nút
  const KHOP = /tải xuống|tải về|download/i;
  let btn = null, nhan = "";
  for (const w of cacWin) {
    for (const e of w.document.querySelectorAll("[aria-label],[data-tooltip],[title],button,[role='button']")) {
      const n = e.getAttribute?.("aria-label") || e.getAttribute?.("data-tooltip") || e.getAttribute?.("title") || "";
      if (!KHOP.test(n)) continue;
      const b = e.closest("[role='button'], button") || e;
      if (b.offsetParent === null) continue;
      btn = b; nhan = n; break;
    }
    if (btn) break;
  }
  if (!btn) { console.error("✖ không thấy nút tải"); return; }
  console.log("③ bấm nút:", nhan);
  btn.click();
  await nghi(3500);

  // Kết quả
  let best = "", nguon = "";
  for (const w of cacWin) {
    for (const b of w.__blobs || []) {
      try { const t = await b.text(); if (t.length > best.length) { best = t; nguon = "Blob"; } } catch (_) {}
    }
  }
  const moiHref = [];
  for (const w of cacWin) moiHref.push(...(w.__hrefs || []));
  console.log("④ các URL đã đi qua:", moiHref.length ? moiHref : "(không có)");

  if (best.length < 200) {
    for (const h of moiHref) {
      const u = h.split(" -> ")[1];
      if (!u || /googleapis|gstatic|logs|batchexecute/.test(u)) continue;
      try {
        const t = await (await fetch(u)).text();
        if (t.length > best.length) { best = t; nguon = h.split(" -> ")[0]; }
      } catch (_) {}
    }
  }

  if (best.length > 200) {
    console.log(`✅ LẤY ĐƯỢC ${best.length} ký tự (nguồn: ${nguon})`);
    console.log("--- 400 ký tự đầu ---\n" + best.slice(0, 400));
    window.__ketQua = best;
    console.log("Gõ  copy(__ketQua)  để chép toàn bộ.");
  } else {
    console.warn("✖ vẫn không lấy được. Gửi tôi danh sách ở dòng ④ và mở chrome://downloads");
    console.warn("   xem lượt tải vừa rồi nguồn URL là gì.");
  }
})();
