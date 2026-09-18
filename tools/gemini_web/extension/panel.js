/* panel.js — bảng điều khiển nhỏ trong popup của extension. */

const $ = (id) => document.getElementById(id);

function hoi(kieu, them) {
  return new Promise((r) => chrome.runtime.sendMessage({ kieu, ...(them || {}) }, r));
}

async function ve() {
  const s = await hoi("trang_thai");
  if (!s) return;

  const c = s.cau;
  const cheDo = s.cheDo === "anh" ? "anh" : "txt";
  const ten = cheDo === "anh" ? "đọc ảnh" : "sửa txt";
  // Địa chỉ lấy từ background để panel không tự đoán cổng của chế độ nào.
  const dc = (s.diaChi || "").replace(/^https?:\/\//, "") || "127.0.0.1:8779";

  $("sCho").textContent = c ? c.cho : "–";
  $("sXong").textContent = c ? c.xong : "–";
  $("sNghi").textContent = c ? c.nghi_ngo : "–";
  $("cauSong").textContent = c
    ? `${ten} · cầu ${dc} OK · tổng ${c.tong} · hỏng ${c.hong}`
    : `⚠ ${ten} · chưa thấy cầu ở ${dc}`;
  $("cauSong").style.color = c ? "#8b949e" : "#e0a030";

  // Đang chạy thì khoá công tắc: đổi cầu giữa chừng là trộn hai hàng chờ.
  $("cheDo").disabled = s.chay;
  if (document.activeElement !== $("cheDo")) $("cheDo").value = cheDo;

  const dl = Object.entries(s.dangLam || {});
  $("dangLam").innerHTML = s.chay
    ? (dl.length
        ? dl.map(([k, v]) => `<div>L${k} · ${v.id} · ${(v.ten || "").slice(0, 40)}</div>`).join("")
        : "đang xin việc…")
    : "đã dừng";

  $("nk").textContent = (s.nhatKy || []).join("\n");
  $("bat").disabled = s.chay;
  $("tat").disabled = !s.chay;
  // ve() chạy lại mỗi 2 giây. KHÔNG ghi đè khi người dùng đang gõ vào ô này,
  // nếu không thì vừa sửa 10 -> 5 là 2 giây sau bị kéo về 10.
  if (document.activeElement !== $("soLuong")) {
    $("soLuong").value = s.soLuong || 10;
  }
}

$("bat").onclick = async () => {
  await hoi("bat", {
    soLuong: Math.max(1, Math.min(20, +$("soLuong").value || 10)),
    cheDo: $("cheDo").value === "anh" ? "anh" : "txt",
  });
  ve();
};
$("tat").onclick = async () => { await hoi("tat"); ve(); };
$("dayLai").onclick = async () => {
  const r = await hoi("day_lai_hong");
  alert(r && r.ok ? `Đã đẩy lại ${r.day_lai} file vào hàng chờ.` : "Không gọi được cầu.");
  ve();
};
// Nhớ lựa chọn ngay khi đổi, khỏi phải bấm Bật mới được ghi nhận
$("soLuong").onchange = () => {
  const n = Math.max(1, Math.min(20, +$("soLuong").value || 10));
  $("soLuong").value = n;
  chrome.storage.local.set({ soLuong: n });
};

$("cheDo").onchange = async () => {
  const r = await hoi("doi_che_do", { cheDo: $("cheDo").value });
  if (!(r && r.ok)) alert((r && r.error) || "Không đổi được chế độ.");
  ve();
};

$("dongTabs").onclick = async () => { await hoi("dong_tabs"); ve(); };

chrome.runtime.onMessage.addListener((m) => { if (m.kieu === "nhat_ky_moi") ve(); });
ve();
setInterval(ve, 2000);
