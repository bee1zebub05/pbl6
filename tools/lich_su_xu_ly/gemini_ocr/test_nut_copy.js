/* TEST ĐƯỜNG "NÚT SAO CHÉP MÃ"
 *
 * Dán vào DevTools Console của tab Gemini, ở màn hình chat (KHÔNG cần mở lớp phủ).
 *
 * Cách làm giống hệt extension: móc vào chỗ trang GHI clipboard (execCommand('copy')
 * của Angular CDK / navigator.clipboard.writeText) rồi bấm lần lượt mọi nút sao chép.
 * Không đọc clipboard nên không cần quyền, không cần tab đang focus.
 */
(async () => {
  const nghi = ms => new Promise(r => setTimeout(r, ms));

  // ① móc chỗ ghi clipboard
  if (!window.__ocrCopyHook) {
    window.__ocrCopyHook = true;
    window.__ocrCopied = "";
    const ecGoc = document.execCommand.bind(document);
    document.execCommand = (cmd, ...r) => {
      const ok = ecGoc(cmd, ...r);
      if (/^copy$/i.test(cmd)) {
        const ae = document.activeElement;
        const t = (ae && ae.value !== undefined ? ae.value : "") || String(window.getSelection() || "");
        if (t && t.length > (window.__ocrCopied || "").length) window.__ocrCopied = t;
      }
      return ok;
    };
    const wGoc = navigator.clipboard?.writeText?.bind(navigator.clipboard);
    if (wGoc) navigator.clipboard.writeText = (t) => {
      if (t && String(t).length > (window.__ocrCopied || "").length) window.__ocrCopied = String(t);
      return wGoc(t);
    };
    document.addEventListener("copy", (e) => {
      const t = e.clipboardData?.getData("text/plain") || String(window.getSelection() || "");
      if (t && t.length > (window.__ocrCopied || "").length) window.__ocrCopied = t;
    }, true);
    console.log("① đã móc chỗ ghi clipboard");
  } else {
    console.log("① móc đã có sẵn");
  }

  // ② tìm nút
  const KHOP = /sao chép mã|sao chép|copy code|copy/i;
  const LOAI = /liên kết|link|url|chia sẻ|share|email|địa chỉ/i;
  const nut = [...document.querySelectorAll("button[aria-label], [role='button'][aria-label]")]
    .filter(b => {
      const n = b.getAttribute("aria-label") || "";
      return KHOP.test(n) && !LOAI.test(n) && b.offsetParent !== null;
    })
    .sort((a, b) => {
      const uu = e => /mã|code/i.test(e.getAttribute("aria-label") || "") ? 0 : 1;
      return uu(a) - uu(b);
    });

  if (!nut.length) { console.error("✖ không thấy nút sao chép nào"); return; }
  console.log(`② thấy ${nut.length} nút:`, nut.map(b => b.getAttribute("aria-label")));

  // ③ bấm lần lượt, đọc nội dung sau mỗi lần
  const ra = [];
  for (const b of nut) {
    window.__ocrCopied = "";
    b.click();
    await nghi(500);
    const t = window.__ocrCopied || "";
    ra.push({ nhan: b.getAttribute("aria-label"), ky_tu: t.length, dau: t.slice(0, 45), text: t });
  }
  console.table(ra.map(({ nhan, ky_tu, dau }) => ({ nhan, ky_tu, dau })));

  // ④ chọn khối văn bản thuần (bỏ khối mã Python)
  const laCode = t => /^\s*(#\s|import\s|from\s+\w+\s+import|def\s|with\s+open|print\(|[a-z_]+\s*=\s*("""|'''|f?"))/m
    .test(t.trimStart().slice(0, 400));
  const van = ra.filter(x => x.ky_tu > 200 && !laCode(x.text)).sort((a, b) => b.ky_tu - a.ky_tu)[0];
  const chon = van || ra.filter(x => x.ky_tu > 200).sort((a, b) => b.ky_tu - a.ky_tu)[0];

  if (!chon) { console.warn("✖ bấm được nút nhưng không bắt được nội dung nào"); return; }
  console.log(`③ CHỌN: "${chon.nhan}" — ${chon.ky_tu} ký tự${van ? " (văn bản thuần ✅)" : " (vẫn là mã ⚠️)"}`);
  console.log("--- 300 ký tự đầu ---\n" + chon.text.slice(0, 300));
  console.log("--- 200 ký tự cuối ---\n" + chon.text.slice(-200));
  window.__ketQua = chon.text;
  console.log("\nGõ  copy(__ketQua)  để chép toàn bộ ra clipboard.");
})();
