# Trang gán nhãn văn bản sinh viên

Trang web để nhóm 4 người gán tay 103 văn bản trong `data/clean/sinh_vien_103/`: bôi đen một đoạn,
chọn loại node/quan hệ của knowledge graph, rồi xuất JSON đúng `src/legal_knowledge_graph/schema/document.schema.json`.

Bản đang chạy (chia sẻ qua menu Share, quyền Contributor): https://claude.ai/artifact/HsHAhg16vzYdS4ZqRqucgE

| File | Nội dung |
|---|---|
| `index.html` | Mã nguồn trang. Nhãn lưu trong cơ sở dữ liệu dùng chung của artifact (capability `db`), không lưu trong repo |
| `build_data.py` | Dựng `data/` (text, bản nháp v2, chỉ mục, người phụ trách) từ `data/clean/sinh_vien_103/` |

```powershell
python tools/labeler/build_data.py
```

## Loại highlight và node tương ứng

| Phím | Highlight | Ghi vào JSON |
|---|---|---|
| 1 | Cơ quan ban hành | `organization` → `ISSUED_BY` |
| 2 | Người ký | `signers[]` → `SIGNED_BY` |
| 3 | Đối tượng áp dụng | `document.targetGroups` → `APPLIES_TO` |
| 4 | Trích dẫn văn bản | `citations[]` (BASED_ON / REFERENCES / REPLACES / AMENDS / REPEALS) |
| 5 | Tổ chức được nhắc | `mentions[]` |
| 6 | Nội dung quy phạm | `normativeContents[]` → `PROMULGATES` |
| 7 | Điều | `articles[]` → `HAS_ARTICLE`, gắn vào nội dung quy phạm gần nhất phía trên |

Thông tin văn bản (số hiệu, loại, ngày, lĩnh vực, tóm tắt) điền ở cột phải, không cần highlight.

## Phân công

Cố định theo cột `nguoi_gan` của `danh_sach.csv`: Nguyên 28, Đức 25, Tùng 25, Kiên 25. Chia riêng mức A và B,
trong mỗi mức cân theo tổng số ký tự để khối lượng gần bằng nhau.

## Tự host (lưu nhãn xuống SQLite trên máy mình)

Bản artifact lưu nhãn trong kho dùng chung của claude.ai. Nếu tự host trang này
như file tĩnh thì không có kho đó, nhãn chỉ nằm trong bộ nhớ tab và mất khi tải
lại — chính trang sẽ hiện băng-rôn *"Bản xem thử: nhãn chỉ lưu tạm trong tab
này"*.

`server.py` dựng lại đúng phần API mà trang cần và lưu xuống SQLite. Nó phục vụ
luôn file tĩnh nên chỉ cần một tiến trình. **Chỉ dùng thư viện chuẩn của
Python**, không phải cài gì.

```bash
python3 tools/labeler/build_data.py                  # sinh tools/labeler/data/
python3 tools/labeler/server.py                      # cổng 8002, chỉ nghe 127.0.0.1
python3 tools/labeler/server.py --db /mnt/ssd/nhan.db --cong 8002
```

Trang tự dò: chạy trong artifact thì dùng kho chung của artifact, chạy sau
`server.py` thì dùng SQLite, không có cả hai thì vẫn rơi về bộ nhớ như cũ.
Đường chạy artifact **không đổi gì**.

Khi tự host, danh tính lấy từ ô *"Tôi là"* ở góc trên, nên `assignee` và
`updatedBy` vẫn ghi đúng ai làm. Mỗi người chọn tên mình một lần, trình duyệt
nhớ.

Mặc định chỉ nghe `127.0.0.1` — đủ cho cloudflared chạy cùng máy, và không lòi
trang ra mạng LAN. Muốn mở rộng thì `--dia-chi 0.0.0.0`.

File `.db` nằm trong `.gitignore`: đó là dữ liệu thật, sao lưu bằng cách copy
file, đừng commit.

### Chạy nền bằng systemd

```ini
# /etc/systemd/system/pbl6-labeler.service
[Unit]
Description=PBL6 labeler
After=network.target

[Service]
User=dqkin625
WorkingDirectory=/home/dqkin625/pbl6
ExecStart=/usr/bin/python3 tools/labeler/server.py --cong 8002 --db /home/dqkin625/pbl6-nhan.db
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now pbl6-labeler
```
