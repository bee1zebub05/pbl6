/**
 * frame_grabber.js — chạy trong MỌI frame của tab Gemini.
 *
 * Khi bấm "Đang mở", file .txt được render bởi trình xem Drive — thường nằm trong IFRAME
 * (docs.google.com / drive.google.com). Content script của trang cha KHÔNG đọc được qua đó,
 * nên phải inject vào all frames rồi lấy frame nào có text dài nhất.
 *
 * Giá trị TRẢ VỀ = biểu thức cuối cùng (chuỗi text tìm được).
 */
(() => {
  const pick = [];

  // 0) Trình xem Drive tạo MỘT <pre class="drive-viewer-text-page"> cho MỖI TRANG.
  //    Phải GHÉP hết theo thứ tự — lấy "pre dài nhất" là chỉ được đúng 1 trang.
  const trang = [...document.querySelectorAll("pre.drive-viewer-text-page")];
  if (trang.length) {
    pick.push(trang.map(p => (p.innerText || "").replace(/\s+$/, "")).join("\n"));
  }

  // 1) Trình xem text của Drive
  document.querySelectorAll(
    ".drive-viewer-text-content, .drive-viewer-paginated-page, [class*='drive-viewer'] pre, .ndfHFb-c4YZDc-cYSp0e-DARUcf"
  ).forEach(el => pick.push(el.innerText || ""));

  // 2) Canvas / immersive panel của chính Gemini
  document.querySelectorAll(
    "code-immersive-panel, .immersive-editor, [data-test-id='immersive-panel'], .ProseMirror"
  ).forEach(el => pick.push(el.innerText || ""));

  // 3) <pre> bất kỳ (viewer text thuần thường bọc trong pre)
  document.querySelectorAll("pre").forEach(el => pick.push(el.innerText || ""));

  // 4) Cả body — chỉ dùng khi frame này rõ ràng là viewer (không phải app Gemini)
  const isViewerFrame = /docs\.google\.com|drive\.google\.com/.test(location.href)
    || document.body?.classList?.contains("drive-viewer");
  if (isViewerFrame) pick.push(document.body?.innerText || "");

  let best = "";
  for (const t of pick) {
    const s = (t || "").trim();
    if (s.length > best.length) best = s;
  }
  return best;      // giá trị này chính là result của executeScript cho frame đó
})();
