# BÁO CÁO KIỂM TOÁN BẢO MẬT & BÍ MẬT (SECURITY AUDIT REPORT)

> Quét toàn bộ lịch sử Git của repository (`git log -p --all`).
> **Tuân thủ quy tắc bảo mật:** Không in giá trị bí mật ra báo cáo.

## 1. Kết quả phát hiện bí mật trong lịch sử Git

⚠️ **Phát hiện 11 điểm lộ bí mật trong lịch sử Git:**

| Commit | File | Dòng (tương đối) | Loại bí mật | Tác giả | Ngày |
|---|---|---|---|---|---|
| `81cb2dac` | `README.md` | 215 | **Generic API Token** | git-triphung <phungtri267@gmail.com> | Tue Sep 15 10:42:36 2026 +0700 |
| `81cb2dac` | `README.vn.md` | 246 | **Generic API Token** | git-triphung <phungtri267@gmail.com> | Tue Sep 15 10:42:36 2026 +0700 |
| `b7b587bd` | `.env` | 2 | **Riot API Key** | git-triphung <phungtri267@gmail.com> | Sat Sep 12 10:18:09 2026 +0700 |
| `b7b587bd` | `.env` | 2 | **Generic API Token** | git-triphung <phungtri267@gmail.com> | Sat Sep 12 10:18:09 2026 +0700 |
| `45231c00` | `.env` | 2 | **Riot API Key** | git-triphung <phungtri267@gmail.com> | Thu Sep 10 17:41:00 2026 +0700 |
| `45231c00` | `.env` | 2 | **Generic API Token** | git-triphung <phungtri267@gmail.com> | Thu Sep 10 17:41:00 2026 +0700 |
| `45231c00` | `.env.example` | 6 | **Generic API Token** | git-triphung <phungtri267@gmail.com> | Thu Sep 10 17:41:00 2026 +0700 |
| `3ee3af0d` | `.env` | 8 | **Riot API Key** | git-triphung <phungtri267@gmail.com> | Thu Sep 10 12:37:47 2026 +0700 |
| `3ee3af0d` | `.env` | 8 | **Generic API Token** | git-triphung <phungtri267@gmail.com> | Thu Sep 10 12:37:47 2026 +0700 |
| `3ee3af0d` | `.env.example` | 8 | **Riot API Key** | git-triphung <phungtri267@gmail.com> | Thu Sep 10 12:37:47 2026 +0700 |
| `3ee3af0d` | `.env.example` | 8 | **Generic API Token** | git-triphung <phungtri267@gmail.com> | Thu Sep 10 12:37:47 2026 +0700 |

## 2. Các tệp nhạy cảm và dữ liệu cá nhân bị Git theo dõi (Tracked Files)

✅ Không có tệp nhạy cảm bị theo dõi trong Git index.

## 3. Khuyến nghị và hành động cần thực hiện

1. **Thu hồi API Key**: Người dùng cần vào Riot Developer Portal và bấm `Regenerate API Key` ngay lập tức.
2. **Gỡ bỏ theo dõi (Local Git)**: Thực thi `git rm --cached` cho `.env`, `output/`, `scratch/`.
3. **Cập nhật `.gitignore`**: Đảm bảo các đường dẫn nhạy cảm được loại trừ triệt để.
4. **Quyết định viết lại lịch sử (Git rewrite)**: Cần người dùng phê duyệt trước khi chạy `git filter-repo` trên remote.
