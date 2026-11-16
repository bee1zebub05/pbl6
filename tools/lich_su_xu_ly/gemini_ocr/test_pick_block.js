/**
 * test_pick_block.js — kiểm tra phần CHỌN NỘI DUNG của engine bằng dữ liệu thật
 * (đúng kiểu Gemini trả về: 1 khối Python ghi file + 1 khối Plaintext nguyên văn).
 *
 * Chạy:  node test_pick_block.js
 *
 * Test này nạp thẳng engine_gemini_pdf.js với 1 DOM giả tối thiểu rồi gọi hàm thuần
 * pickBlockText — không cần Chrome, không cần jsdom.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

// ── DOM giả: đủ để file engine chạy hết mà không nổ ─────────────────────────────
const noop = () => {};
const fakeEl = { querySelectorAll: () => [], querySelector: () => null, closest: () => null,
                 addEventListener: noop, classList: [], innerText: "", textContent: "" };
const sandbox = {
  console: { log: noop, warn: noop, error: noop },
  setTimeout, clearTimeout, setInterval, clearInterval,
  atob: s => Buffer.from(s, "base64").toString("binary"),
  File: class {}, Blob: class {}, DataTransfer: class {}, ClipboardEvent: class {},
  DragEvent: class {}, KeyboardEvent: class {}, InputEvent: class {}, MutationObserver: class { observe() {} disconnect() {} },
  document: { querySelector: () => null, querySelectorAll: () => [], createRange: () => fakeEl,
              createElement: () => fakeEl, body: fakeEl, execCommand: noop,
              dispatchEvent: noop, addEventListener: noop },
  location: { href: "https://gemini.google.com/app" },
  getSelection: () => ({ removeAllRanges: noop, addRange: noop }),
};
sandbox.window = sandbox;
vm.createContext(sandbox);

// Lấy phần thân IIFE rồi chạy trong sandbox, đồng thời chìa hàm nội bộ ra ngoài để test.
let src = fs.readFileSync(path.join(__dirname, "extension", "engine_gemini_pdf.js"), "utf8");
src = src.replace(
  "  log(\"engine loaded\");",
  "  window.__test = { pickBlockText, unwrapPythonString, looksLikeCode, stripLangLine, stripFence };"
);
vm.runInContext(src, sandbox);
const T = sandbox.window.__test;
if (!T) { console.error("✖ không chìa được hàm nội bộ ra — sai chỗ chèn"); process.exit(1); }

// ── Dữ liệu thật, rút gọn từ đúng câu trả lời Gemini bạn gặp ───────────────────
const NOI_DUNG = `CHÍNH PHỦ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
Số: 78/2020/NĐ-CP
Hà Nội, ngày 06 tháng 7 năm 2020

NGHỊ ĐỊNH
Về sĩ quan dự bị Quân đội nhân dân Việt Nam

Điều 1. Phạm vi điều chỉnh
Nghị định này quy định việc tuyển chọn, đào tạo sĩ quan dự bị; đăng ký, quản lý, huấn luyện.
${"Điều lặp lại cho đủ dài. ".repeat(40)}`;

const KHOI_PYTHON = `# Read and prepare the OCR text in UTF-8 file
text_content = """${NOI_DUNG}
"""

filename = "Nghi_dinh_78_2020_ND-CP_Si_quan_du_bi.txt"
with open(filename, "w", encoding="utf-8") as f:
    f.write(text_content)

print(f"File saved successfully as {filename}")`;

// ── Các ca kiểm thử ───────────────────────────────────────────────────────────
let pass = 0, fail = 0;
function check(ten, dieuKien, chiTiet = "") {
  if (dieuKien) { console.log("  ✔ " + ten); pass++; }
  else { console.log("  ✖ " + ten + (chiTiet ? "\n      " + chiTiet : "")); fail++; }
}

console.log("\n[1] Gemini trả 2 khối: Python (dài hơn) + Plaintext — phải chọn Plaintext");
{
  const got = T.pickBlockText([
    { lang: "python", text: KHOI_PYTHON },
    { lang: "plaintext", text: NOI_DUNG },
  ]);
  check("bắt đầu bằng 'CHÍNH PHỦ'", got.startsWith("CHÍNH PHỦ"), "nhận được: " + got.slice(0, 60));
  check("không dính mã Python", !got.includes("text_content") && !got.includes("open(filename"));
  check("khối Python dài hơn thật (nên chọn theo độ dài là sai)", KHOI_PYTHON.length > NOI_DUNG.length);
}

console.log("\n[2] Chỉ có khối Python — phải bóc chuỗi ba nháy ra");
{
  const got = T.pickBlockText([{ lang: "python", text: KHOI_PYTHON }]);
  check("bắt đầu bằng 'CHÍNH PHỦ'", got.startsWith("CHÍNH PHỦ"), "nhận được: " + got.slice(0, 60));
  check("không còn dòng import/with open", !/with open|text_content\s*=/.test(got));
  check("giữ đủ nội dung", got.length > NOI_DUNG.length * 0.9);
}

console.log("\n[3] Khối không có nhãn, nội dung là văn bản — vẫn nhận");
{
  const got = T.pickBlockText([{ lang: "", text: NOI_DUNG }]);
  check("lấy đúng nội dung", got.startsWith("CHÍNH PHỦ"));
}

console.log("\n[4] Nhãn bị đọc nhầm thành chữ trên nút ('tải') — vẫn phải ra text đúng");
{
  const got = T.pickBlockText([
    { lang: "tải", text: KHOI_PYTHON },
    { lang: "tải", text: NOI_DUNG },
  ]);
  check("không dính mã Python", !got.includes("text_content"), "nhận được: " + got.slice(0, 60));
}

console.log("\n[4b] Nút 'Sao chép' cả câu trả lời (markdown) vs nút 'Sao chép mã'");
{
  // Bản markdown DÀI HƠN vì có câu dẫn + dấu rào -> so độ dài là chọn nhầm, rồi ghi cả
  // câu dẫn vào file .txt. Đúng lỗi gặp khi chạy batch thư mục "Khác".
  const md = "Dưới đây là toàn bộ nội dung văn bản được OCR và chuyển đổi sang dạng "
           + "plaintext để bạn dễ dàng sao chép:\n\n```text\n" + NOI_DUNG + "\n```";
  const got = T.pickBlockText([{ lang: "", text: md }, { lang: "", text: NOI_DUNG }]);
  check("không còn câu dẫn 'Dưới đây là'", !got.includes("Dưới đây là"), "nhận được: " + got.slice(0, 60));
  check("không còn dấu rào ```", !got.includes("```"));
  check("bắt đầu bằng 'CHÍNH PHỦ'", got.startsWith("CHÍNH PHỦ"));
}

console.log("\n[4c] Chỉ có bản markdown, rào bị cắt cụt (thiếu ``` đóng)");
{
  const md = "Dưới đây là nội dung:\n\n```text\n" + NOI_DUNG;
  const got = T.pickBlockText([{ lang: "", text: md }]);
  check("vẫn bóc được nội dung", got.startsWith("CHÍNH PHỦ"), "nhận được: " + got.slice(0, 60));
}

console.log("\n[5b] Khối Python BỊ CẮT CỤT (thiếu ba nháy đóng) — vẫn phải bóc ra");
{
  // Gemini hiển thị khối code dài bị cắt: có dấu mở """ nhưng không có dấu đóng.
  // Trước đây gặp ca này là trả về NGUYÊN mã nguồn — đúng lỗi người dùng gặp phải.
  const cut = KHOI_PYTHON.slice(0, KHOI_PYTHON.indexOf(NOI_DUNG) + 900);
  const got = T.pickBlockText([{ lang: "python", text: cut }]);
  check("bắt đầu bằng 'CHÍNH PHỦ'", got.startsWith("CHÍNH PHỦ"), "nhận được: " + got.slice(0, 60));
  check("không còn 'text_content ='", !got.includes("text_content ="));
}

console.log("\n[5] looksLikeCode phân biệt đúng");
{
  check("văn bản hành chính KHÔNG bị coi là code", !T.looksLikeCode(NOI_DUNG));
  check("mã Python bị coi là code", T.looksLikeCode(KHOI_PYTHON));
}

console.log("\n[6] Dòng nhãn lọt vào đầu text thì bị cắt");
{
  check("cắt 'Plaintext\\n'", T.stripLangLine("Plaintext\nCHÍNH PHỦ").startsWith("CHÍNH PHỦ"));
}

console.log(`\n───────── ${pass} đạt, ${fail} hỏng ─────────\n`);
process.exit(fail ? 1 : 0);
