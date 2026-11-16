/* Dán vào DevTools Console của tab Gemini KHI LỚP PHỦ ĐANG MỞ.
   In ra: lớp phủ nằm ở đâu, text đọc được bao nhiêu, nút tải xuống là element nào. */
(() => {
  const r = { url: location.href, iframes: [], text: {}, nutTai: [] };

  document.querySelectorAll("iframe").forEach(f => {
    let sameOrigin = false, len = 0;
    try { sameOrigin = !!f.contentDocument; len = f.contentDocument?.body?.innerText?.length || 0; } catch (_) {}
    r.iframes.push({ src: (f.src || "(không src)").slice(0, 90), sameOrigin, textLen: len });
  });

  const do1 = (sel) => {
    let best = 0, el = null;
    document.querySelectorAll(sel).forEach(e => {
      const n = (e.innerText || "").trim().length;
      if (n > best) { best = n; el = e; }
    });
    return { len: best, el };
  };
  for (const sel of ["pre", "[role='dialog']", "[aria-modal='true']",
                     "[class*='drive-viewer']", "code-immersive-panel, .immersive-editor"]) {
    r.text[sel] = do1(sel).len;
  }

  const KHOP = /tải xuống|download|tải về/i;
  document.querySelectorAll("[aria-label],[data-tooltip],[title],button,[role='button']").forEach(e => {
    const nhan = e.getAttribute("aria-label") || e.getAttribute("data-tooltip") || e.getAttribute("title") || "";
    if (KHOP.test(nhan)) {
      r.nutTai.push({
        nhan, tag: e.tagName.toLowerCase(),
        cls: (e.className || "").toString().slice(0, 70),
        hien: e.offsetParent !== null,
      });
    }
  });

  console.log("URL         :", r.url);
  console.log("IFRAME      :", r.iframes.length ? r.iframes : "KHÔNG có iframe → lớp phủ nằm ngay trong trang ✅");
  console.log("TEXT đọc được:", r.text);
  console.log("NÚT TẢI     :", r.nutTai.length ? r.nutTai : "không thấy ở document này");
  return r;
})();
