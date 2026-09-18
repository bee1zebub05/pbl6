/**
 * visibility_spoof.js — chạy document_start, world MAIN, trên tab ChatGPT/Gemini.
 *
 * VÌ SAO: khi nhiều job chạy SONG SONG, chỉ 1 tab được focus; các tab còn lại ở NỀN
 * bị Chrome/SPA tạm dừng render → ChatGPT/Gemini KHÔNG "vẽ" ảnh kết quả ra DOM → engine
 * đọc không thấy → job bị fail/timeout. Mở tay tab bị đè ra là có ảnh ngay (đúng triệu chứng).
 *
 * CÁCH SỬA: ép trang LUÔN tin rằng nó đang HIỂN THỊ + ĐƯỢC FOCUS, và nuốt các event
 * visibilitychange/blur → SPA tiếp tục render bình thường dù tab ở nền → nhiều job song song
 * đều trả được ảnh, không cần focus từng tab.
 *
 * Chạy ở MAIN world + document_start (khai báo trong manifest) để ghi đè TRƯỚC khi
 * script của trang đọc trạng thái visibility.
 */
(() => {
  try {
    const def = (obj, prop, val) =>
      Object.defineProperty(obj, prop, { configurable: true, get: () => val });

    // 1) document.hidden / visibilityState → luôn "visible"
    def(document, "hidden", false);
    def(document, "webkitHidden", false);
    def(document, "visibilityState", "visible");
    def(document, "webkitVisibilityState", "visible");

    // 2) document.hasFocus() → luôn true (SPA nào chờ focus vẫn chạy)
    document.hasFocus = () => true;

    // 3) Nuốt event khiến SPA tưởng tab bị ẩn / mất focus (bắt ở capture, chặn sớm nhất)
    const swallow = (e) => { e.stopImmediatePropagation(); };
    for (const target of [document, window]) {
      for (const ev of ["visibilitychange", "webkitvisibilitychange", "blur"]) {
        target.addEventListener(ev, swallow, true);
      }
    }
  } catch (_) {
    /* nếu lỗi thì bỏ qua — tuyệt đối không phá trang */
  }
})();
