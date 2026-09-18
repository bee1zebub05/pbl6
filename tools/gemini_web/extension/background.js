/* background.js — điều phối 10 luồng song song.
 *
 * Mỗi luồng giữ một tab Gemini riêng, xin việc độc lập ở cầu. Ngoài ra có một
 * "vòng xoay focus" liên tục đổi tab đang active — vì tab nền bị Chrome bóp render,
 * Gemini không vẽ câu trả lời ra DOM và engine đọc không thấy. che_an_tab.js đã ép
 * document.hidden=false nhưng Chrome vẫn hạ ưu tiên tab nền, nên vẫn cần quay focus.
 *
 * CHECKPOINT: mọi tiến độ nằm ở phía cầu (trang_thai_sua_txt.json), ghi đĩa ngay sau
 * mỗi file xong. Tắt máy giữa chừng thì bật lại chạy tiếp, file nào xong rồi bỏ qua.
 * Việc đang dở lúc tắt máy sẽ tự quay lại hàng chờ (cầu không thấy ai nộp).
 */

// Một cổng duy nhất. Cầu nào đang nghe ở đây thì tự khai chế độ qua /api/stats
// (sửa txt hay xuất JSON) — extension không cần biết, nó chỉ gõ prompt cầu đưa.
const CAU = "http://127.0.0.1:8779";
const SO_LUONG_MAC_DINH = 10;
const URL_GEMINI = "https://gemini.google.com/u/1/app?pageId=none";
const NHIP_XOAY_FOCUS = 3500;   // ms — mỗi tab được "ngó" tới sau chừng này

// ── trạng thái ────────────────────────────────────────────────────────────────
const S = {
  async lay() {
    const d = await chrome.storage.local.get(
      ["chay", "soLuong", "tabs", "dangLam", "nhatKy", "soLieu"]);
    return {
      chay: d.chay || false,
      soLuong: d.soLuong || SO_LUONG_MAC_DINH,
      tabs: d.tabs || [],                 // [tabId,...]
      dangLam: d.dangLam || {},           // luongId -> {id, ten}
      nhatKy: d.nhatKy || [],
      soLieu: d.soLieu || { xong: 0, hong: 0 },
    };
  },
  async dat(o) { await chrome.storage.local.set(o); },
};

async function ghi(muc, ...phan) {
  const s = await S.lay();
  const dong = `[${new Date().toLocaleTimeString("vi-VN")}] ${muc} ${phan.join(" ")}`;
  await S.dat({ nhatKy: [dong, ...s.nhatKy].slice(0, 300) });
  console.log(dong);
  // sendMessage tra ve Promise: popup dong thi no REJECT bat dong bo,
  // try/catch khong bat duoc -> phai .catch, khong thi Console day
  // "Could not establish connection. Receiving end does not exist."
  try {
    const p = chrome.runtime.sendMessage({ kieu: "nhat_ky_moi" });
    if (p && p.catch) p.catch(() => {});
  } catch (_) {}
}

// ── nói chuyện với cầu ────────────────────────────────────────────────────────
/** Địa chỉ cầu theo chế độ đang chọn. Đọc thẳng storage chứ không nhớ vào biến
 *  toàn cục: service worker MV3 ngủ dậy là biến bay, storage thì còn. */
async function diaChiCau() {
  return CAU;
}

async function cauGET(duong) {
  const goc = await diaChiCau();
  const r = await fetch(goc + duong, { cache: "no-store" });
  if (!r.ok) throw new Error(`cầu trả ${r.status}`);
  return r.json();
}

async function cauPOST(duong, body) {
  const goc = await diaChiCau();
  const r = await fetch(goc + duong, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json().catch(() => ({ ok: false, error: "trả về không phải JSON" }));
}

/** Tải bản gốc của một việc về.
 *
 *  Cầu trả về văn bản thuần (.txt của kho đã sạch), dùng cho mọi chế độ.
 */
async function cauTaiFile(id) {
  const goc = await diaChiCau();
  const r = await fetch(`${goc}/api/file/${id}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`không tải được bản gốc (${r.status})`);
  return r.text();
}

// ── quản lý tab ───────────────────────────────────────────────────────────────
async function tabConSong(id) {
  if (id == null) return false;
  try {
    const t = await chrome.tabs.get(id);
    return !!t && /^https:\/\/gemini\.google\.com\//.test(t.url || "");
  } catch (_) { return false; }
}

/** Mở đủ N tab Gemini, trả về mảng tabId theo thứ tự luồng. */
async function chuanBiTabs(soLuong) {
  const s = await S.lay();
  const tabs = [];
  for (let i = 0; i < soLuong; i++) {
    let id = s.tabs[i];
    if (!(await tabConSong(id))) {
      const t = await chrome.tabs.create({ url: URL_GEMINI, active: i === 0 });
      id = t.id;
      await ghi("＋", `mở tab luồng ${i + 1}`);
      await new Promise((r) => setTimeout(r, 900));   // giãn ra, đừng mở dồn một lúc
    }
    tabs.push(id);
  }
  await S.dat({ tabs });

  // Đếm lại: nếu số tab Gemini nhiều hơn số luồng thì có tab lạc, báo ngay
  // thay vì để nó âm thầm sinh sôi.
  const tatCa = await chrome.tabs.query({ url: "https://gemini.google.com/*" });
  if (tatCa.length > soLuong) {
    await ghi("⚠", `có ${tatCa.length} tab Gemini nhưng chỉ cần ${soLuong}`,
      "— bấm \"Đóng hết tab\" rồi Bật lại nếu không phải tab bạn tự mở");
  }
  return tabs;
}

async function bomMay(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId }, world: "MAIN", files: ["may_gemini.js"],
  });
}

async function chayTrenTrang(tabId, ham, doiSo) {
  const [kq] = await chrome.scripting.executeScript({
    target: { tabId }, world: "MAIN",
    func: (ten, ds) => window.__PBL6_SUA_TXT__[ten](...ds),
    args: [ham, doiSo || []],
  });
  return kq && kq.result;
}


/** Kéo nhật ký của máy trên trang về Console service worker, 4 giây một lần.
 *  Phải kéo TRONG LÚC chayMotFile còn chạy: đợi nó trả về thì lúc treo chẳng
 *  bao giờ thấy gì. Trả về hàm dừng, nhớ gọi trong finally. */
function theoDoiNhatKy(luongId, tabId) {
  let song = true;
  const keo = async () => {
    try {
      const [r] = await chrome.scripting.executeScript({
        target: { tabId }, world: "MAIN",
        func: () => (window.__PBL6_SUA_TXT__ && window.__PBL6_SUA_TXT__.layNhatKy)
          ? window.__PBL6_SUA_TXT__.layNhatKy() : [],
      });
      for (const d of (r && r.result) || []) console.log(`  L${luongId} · ${d}`);
    } catch (_) {}
  };
  const id = setInterval(() => { if (song) keo(); }, 4000);
  return async () => { song = false; clearInterval(id); await keo(); };
}

// ── vòng xoay focus ───────────────────────────────────────────────────────────
// Chrome chỉ render đầy đủ tab đang active. Quay vòng để tab nào cũng được vẽ.
let xoayDangChay = false;
async function vongXoayFocus() {
  if (xoayDangChay) return;
  xoayDangChay = true;
  let i = 0;
  try {
    while ((await S.lay()).chay) {
      const { tabs } = await S.lay();
      if (tabs.length) {
        const id = tabs[i % tabs.length];
        i++;
        if (await tabConSong(id)) {
          try { await chrome.tabs.update(id, { active: true }); } catch (_) {}
        }
      }
      await new Promise((r) => setTimeout(r, NHIP_XOAY_FOCUS));
    }
  } finally { xoayDangChay = false; }
}

// ── một việc ──────────────────────────────────────────────────────────────────
async function lamMotViec(luongId, tabId) {
  const { job } = await cauGET(`/api/next?worker=luong${luongId}`);
  if (!job) return false;                       // hết việc

  const s0 = await S.lay();
  await S.dat({ dangLam: { ...s0.dangLam, [luongId]: { id: job.id, ten: job.ten_file } } });
  await ghi("▶", `L${luongId}`, job.id, job.ten_file.slice(0, 48));

  try {
    if (!(await tabConSong(tabId))) throw new Error("tab đã đóng");
    await bomMay(tabId);
    const noiDung = await cauTaiFile(job.id);
    const dungTheoDoi = theoDoiNhatKy(luongId, tabId);
    let kq;
    try {
      kq = await chayTrenTrang(tabId, "chayMotFile", [{
        id: job.id, ten_file: job.ten_file, prompt: job.prompt,
        ten_dinh_kem: job.ten_dinh_kem || job.ten_file,
        noi_dung: noiDung, so_ky_tu_goc: job.so_ky_tu_goc,
      }]);
    } finally { await dungTheoDoi(); }

    if (!kq || !kq.ok) {
      const loi = (kq && kq.loi) || "máy trên trang không trả lời";
      await cauPOST("/api/fail", { id: job.id, error: loi, tam_thoi: !!(kq && kq.tam_thoi) });
      const s = await S.lay();
      await S.dat({ soLieu: { ...s.soLieu, hong: s.soLieu.hong + 1 } });
      await ghi(kq && kq.tam_thoi ? "⏳" : "✖", `L${luongId}`, job.id, loi.slice(0, 110));
    } else {
      const nop = await cauPOST("/api/done",
        { id: job.id, text: kq.text, nguon: kq.nguon });
      const s = await S.lay();
      if (nop.ok) {
        await S.dat({ soLieu: { ...s.soLieu, xong: s.soLieu.xong + 1 } });
        await ghi(nop.nghi_ngo ? "⚠" : "✔", `L${luongId}`, job.id,
          `${kq.text.length} ký tự` +
          (nop.canh_bao && nop.canh_bao.length ? " — " + nop.canh_bao.join("; ") : ""));
      } else {
        await S.dat({ soLieu: { ...s.soLieu, hong: s.soLieu.hong + 1 } });
        await ghi("✖", `L${luongId}`, job.id, "cầu từ chối: " + (nop.error || "?"));
      }
    }
  } catch (e) {
    await cauPOST("/api/fail", { id: job.id, error: String(e), tam_thoi: true });
    await ghi("⏳", `L${luongId}`, job.id, String(e).slice(0, 120));
  } finally {
    const s = await S.lay();
    const dl = { ...s.dangLam }; delete dl[luongId];
    await S.dat({ dangLam: dl });
  }
  return true;
}

// ── một luồng ─────────────────────────────────────────────────────────────────
/** Lấy tab của luồng này, mở lại nếu chết.
 *
 *  Ô tab của mỗi luồng nằm trong chrome.storage chứ KHÔNG phải biến cục bộ.
 *  Bản trước giữ tabId trong tham số hàm rồi đọc lại nó mỗi vòng, nên tab gốc
 *  chết một lần là mỗi file lại đẻ thêm một tab — Chrome ngập tab không kiểm soát.
 */
async function baoDamTabCuaLuong(luongId) {
  const s = await S.lay();
  const cu = s.tabs[luongId - 1];
  if (await tabConSong(cu)) return cu;

  const t = await chrome.tabs.create({ url: URL_GEMINI, active: false });
  const s2 = await S.lay();
  const tabs = [...s2.tabs];
  tabs[luongId - 1] = t.id;                 // ghi đè ĐÚNG ô của luồng này
  await S.dat({ tabs });
  await ghi("＋", `L${luongId} mở lại tab`);
  await new Promise((r) => setTimeout(r, 4000));
  return t.id;
}

async function chayLuong(luongId) {
  // lệch giờ khởi động để 10 luồng không đâm vào Gemini cùng một giây
  await new Promise((r) => setTimeout(r, luongId * 2500));
  while ((await S.lay()).chay) {
    let con;
    try {
      const tab = await baoDamTabCuaLuong(luongId);
      con = await lamMotViec(luongId, tab);
    } catch (e) {
      await ghi("✖", `L${luongId} lỗi vòng:`, String(e).slice(0, 110));
      con = true;
      await new Promise((r) => setTimeout(r, 10000));
    }
    if (!con) {                                  // hàng chờ rỗng
      await ghi("✔", `L${luongId} hết việc`);
      return;
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  await ghi("■", `L${luongId} dừng`);
}

// ── tổng điều phối ────────────────────────────────────────────────────────────
let dangChay = false;
async function batDau() {
  if (dangChay) return;
  dangChay = true;
  try {
    const { soLuong } = await S.lay();

    // Không mở nhiều tab hơn số việc đang chờ. Hàng chờ 1 file mà mở 10 tab thì
    // 9 tab kia bật lên, xin việc, "hết việc", rồi nằm đó — nhìn như lỗi.
    let cd = "";
    let can = soLuong;
    try {
      const st = await cauGET("/api/stats");
      cd = st.che_do || "";
      const conLai = (st.cho || 0) + (st.dang_lam || 0);
      if (conLai > 0) can = Math.min(soLuong, conLai);
    } catch (_) {}
    if (can < soLuong) {
      await ghi("≡", `hàng chờ còn ${can} việc — chỉ mở ${can} tab thay vì ${soLuong}`);
    }

    const tabs = await chuanBiTabs(can);
    await ghi("▶", `chạy ${can} luồng`, cd ? `· chế độ ${cd}` : "");
    vongXoayFocus();
    await Promise.all(tabs.map((_t, i) => chayLuong(i + 1)));
    await ghi("✔", "tất cả luồng đã nghỉ");
    await S.dat({ chay: false });

    // Xong xuôi thì dọn tab. Chạy 455 file mà để 10 tab Gemini nằm lại là phiền.
    // NHƯNG còn việc hỏng thì GIỮ NGUYÊN — lúc đó cần mở tab ra xem Gemini trả
    // lời gì, đóng đi là mất dấu vết duy nhất.
    let conHong = 0;
    try { conHong = (await cauGET("/api/stats")).hong || 0; } catch (_) {}
    if (conHong) {
      await ghi("⚠", `còn ${conHong} file hỏng — giữ tab lại để soi`);
    } else {
      for (const id of tabs) { try { await chrome.tabs.remove(id); } catch (_) {} }
      await S.dat({ tabs: [] });
      await ghi("✕", `đã đóng ${tabs.length} tab`);
    }
  } catch (e) {
    await ghi("✖", "điều phối chết:", String(e));
    await S.dat({ chay: false });
  } finally { dangChay = false; }
}

chrome.runtime.onMessage.addListener((m, _s, traLoi) => {
  (async () => {
    if (m.kieu === "bat") {
      await S.dat({
        chay: true, soLuong: m.soLuong || SO_LUONG_MAC_DINH,
      });
      batDau();
      traLoi({ ok: true });
    } else if (m.kieu === "tat") {
      await S.dat({ chay: false });
      await ghi("■", "tắt — các luồng dừng sau khi xong file đang chạy");
      traLoi({ ok: true });
    } else if (m.kieu === "trang_thai") {
      const s = await S.lay();
      let cau = null;
      try { cau = await cauGET("/api/stats"); } catch (_) {}
      traLoi({ ...s, cau, diaChi: CAU });
    } else if (m.kieu === "day_lai_hong") {
      traLoi(await cauPOST("/api/requeue", {}));
    } else if (m.kieu === "dong_tabs") {
      const s = await S.lay();
      for (const id of s.tabs) { try { await chrome.tabs.remove(id); } catch (_) {} }
      await S.dat({ tabs: [] });
      traLoi({ ok: true });
    }
  })();
  return true;
});

// Service worker MV3 hay bị ngủ. Alarm đánh thức để nối lại vòng chạy.
chrome.alarms.create("nhip", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(async () => {
  const s = await S.lay();
  if (s.chay && !dangChay) { await ghi("↻", "nối lại sau khi service worker ngủ"); batDau(); }
  if (s.chay && !xoayDangChay) vongXoayFocus();
});
