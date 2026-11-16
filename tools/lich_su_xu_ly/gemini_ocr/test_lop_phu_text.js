/* SOI LỚP PHỦ XEM FILE — lấy text thuần được không, và có đủ mọi trang không?
 *
 * Dán vào DevTools Console của tab Gemini KHI LỚP PHỦ ĐANG MỞ (sau khi bấm "Đang mở").
 *
 * Trình xem Drive tạo MỘT <pre class="drive-viewer-text-page"> cho MỖI TRANG, và chỉ
 * render trang nào đã cuộn tới. Nên script này: đếm pre -> cuộn hết -> đếm lại ->
 * ghép mọi trang theo đúng thứ tự.
 */
(async () => {
  const nghi = ms => new Promise(r => setTimeout(r, ms));

  // Gom frame trên cùng + iframe cùng origin
  const cacDoc = [document];
  document.querySelectorAll("iframe").forEach(f => {
    try { if (f.contentDocument) cacDoc.push(f.contentDocument); } catch (_) {}
  });

  const SEL = "pre.drive-viewer-text-page";
  const SEL_DP = "pre[class*='drive-viewer'], .drive-viewer-text-content, pre";

  const layPre = () => {
    for (const d of cacDoc) {
      const a = [...d.querySelectorAll(SEL)];
      if (a.length) return { ds: a, sel: SEL, doc: d };
    }
    for (const d of cacDoc) {
      const a = [...d.querySelectorAll(SEL_DP)].filter(e => (e.innerText || "").trim().length > 100);
      if (a.length) return { ds: a, sel: SEL_DP, doc: d };
    }
    return { ds: [], sel: null, doc: document };
  };

  let { ds, sel, doc } = layPre();
  if (!ds.length) {
    console.error("✖ Không thấy <pre> nào — lớp phủ đã mở chưa?");
    return;
  }
  const soDau = ds.length;
  const chuDau = ds.map(p => p.innerText).join("\n").length;
  console.log(`① selector dùng được: ${sel}`);
  console.log(`② lúc chưa cuộn: ${soDau} trang, tổng ${chuDau} ký tự`);

  // Tìm phần tử cuộn được bọc ngoài <pre> đầu tiên
  let sc = ds[0].parentElement;
  while (sc && sc.scrollHeight <= sc.clientHeight + 5) sc = sc.parentElement;
  if (!sc) sc = doc.scrollingElement || doc.documentElement;
  console.log("③ khung cuộn:", sc.className || sc.tagName,
              `(cao ${sc.scrollHeight}px / nhìn thấy ${sc.clientHeight}px)`);

  // Cuộn dần xuống đáy để ép render hết các trang
  let truoc = -1, vong = 0;
  while (vong < 40) {
    vong++;
    sc.scrollTop = Math.min(sc.scrollTop + sc.clientHeight * 0.9, sc.scrollHeight);
    await nghi(350);
    const n = layPre().ds.length;
    const chamDay = sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 5;
    if (chamDay && n === truoc) break;
    truoc = n;
  }
  await nghi(600);

  ds = layPre().ds;
  const toanBo = ds.map(p => p.innerText.replace(/\s+$/, "")).join("\n");
  console.log(`④ sau khi cuộn ${vong} nhịp: ${ds.length} trang, tổng ${toanBo.length} ký tự`);

  if (ds.length > soDau) {
    console.warn(`⚠️ CÓ LAZY-RENDER: lúc đầu chỉ ${soDau} trang, cuộn xong mới đủ ${ds.length}.`);
    console.warn("   => extension BẮT BUỘC phải cuộn trước khi đọc, không thì mất trang.");
  } else {
    console.log("✔ không lazy-render: đọc thẳng là đủ.");
  }
  if (ds.length > 1) {
    console.warn(`⚠️ CÓ ${ds.length} <pre> (mỗi trang một cái) => phải GHÉP hết,`);
    console.warn("   lấy 'pre dài nhất' là chỉ được 1 trang.");
    console.table(ds.map((p, i) => ({ trang: i + 1, ky_tu: p.innerText.length })));
  }

  console.log("--- 300 ký tự ĐẦU ---\n" + toanBo.slice(0, 300));
  console.log("--- 300 ký tự CUỐI ---\n" + toanBo.slice(-300));
  window.__ketQua = toanBo;
  console.log(`\n✅ Tổng cộng ${toanBo.length} ký tự. Gõ  copy(__ketQua)  để chép ra clipboard.`);
})();
