# Build tính năng kiểu Pancake — theo dõi

Pancake (pancake.vn) = nền tảng **bán hàng đa kênh mạng xã hội** VN. Bộ sản phẩm: inbox hợp nhất
(FB/IG/Zalo/TikTok tin+bình luận), **chốt đơn từ hội thoại**, POS, kho, livestream bán, Botcake (chatbot),
Webcake (landing), CRM, Pancake Work (task nội bộ), Fintab (kế toán), tích hợp vận chuyển.

## Đã có sẵn ở hệ thống (Pancake-equiv, không cần dựng)
| Pancake | Ở hệ thống bạn |
|---|---|
| POS | `point_of_sale` + `pos_online_payment` |
| Webcake (storefront/landing) | `website_sale` (Odoo eCommerce + website builder) |
| Pancake CRM | `crm` |
| Kho | `stock` |
| Fintab (kế toán) | `account` + account_reports/accountant + module VCT |
| Pancake Work (task nội bộ) | `project` + Discuss |
| Botcake (chatbot) | `im_livechat` + `vct_helpdesk_ai` (RAG) + `vct_ai_agent` |
| Broadcast marketing | `mass_mailing` |
| Kênh Zalo/Messenger | `vct_helpdesk_zalo` + `vct_helpdesk_messenger` |
| Nền vận chuyển | `delivery` (generic — chưa có carrier VN) |

## Trạng thái build (phần Pancake-đặc-trưng còn thiếu)
| # | Tính năng | Module | Trạng thái |
|---|---|---|---|
| 1 | **Chốt đơn từ hội thoại** | `vct_social_sales` | ✅ **Xong + live** (4/4 test) |
| 2 | Tích hợp vận chuyển VN (GHN/GHTK/ViettelPost) | `vct_shipping_vn` | ✅ **Xong + live** (6/6 test) |
| 3 | Inbox bán hàng hợp nhất (1 workspace đa kênh) | `vct_social_inbox` | ✅ **Xong + live** (4/4 test) |
| 4 | Quản lý bình luận bài đăng FB → ẩn/trả lời/chốt đơn | `vct_social_comment` | ✅ **Xong + live** (5/5 test) |
| 5 | Livestream: bình luận → đơn | `vct_livestream` | ⛔ **Bỏ** (chủ dự án quyết) |
| 6 | Chia sẻ nhanh sản phẩm/bảng giá vào chat | `vct_social_catalog` | ✅ **Xong + live** (4/4 test) |

## Đã làm
- 2026-07-22: **#1 `vct_social_sales`** — `action_create_order` trên hội thoại Zalo & Messenger → wizard
  `vct.social.order.wizard` (partner từ hội thoại + dòng sản phẩm + ghi chú giao) → tạo `sale.order` (draft),
  đánh dấu `sale.order.social_source`. App menu "Bán hàng đa kênh" (Đơn từ chat + hội thoại Zalo/Messenger).
  4/4 test. deps: vct_helpdesk_zalo + vct_helpdesk_messenger + sale_management.
  - Defer: đồng bộ hội thoại 2 chiều realtime trong 1 inbox, giữ tồn khi chốt, COD/đối soát.

- 2026-07-22: **#2 `vct_shipping_vn`** — `vct.shipping.carrier` (provider ghn/ghtk/viettelpost + token/shop_id credential),
  `vct.shipment` (người nhận/COD/khối lượng/mã vận đơn/phí/state, seq VD#####). Adapter `_provider_<x>_create` build payload
  theo tài liệu từng hãng, HTTP tách ở `_http_request` (mock). Nút "Tạo vận đơn VN" trên sale.order + smart button; sale.order += shipment_ids.
  3 hãng mẫu. 6/6 test (mock). deps: sale + stock.
  - **Cần chủ dự án khi dùng thật:** nhập Token/Shop ID ở Vận chuyển VN → Nhà vận chuyển; GHN cần mã quận (to_district_id) + phường (to_ward_code).
  - Defer: tra cứu trạng thái tự động (cron webhook), in phiếu/label PDF, tính phí trước, map địa chỉ→mã hành chính tự động.

- 2026-07-22: **#3 `vct_social_inbox`** — `vct.social.thread` (`_auto=False`, SQL view UNION vct_zalo_conversation +
  vct_messenger_conversation; id messenger +1000000 để không đụng). List/search theo kênh/trạng thái + nút "Chốt đơn"
  (dùng lại wizard #1) + "Mở" (dispatch về hội thoại gốc qua res_model/res_id_ref). Menu dưới "Bán hàng đa kênh". 4/4 test.
  - Defer: gõ trả lời trực tiếp trong inbox (hiện mở hội thoại gốc để trả lời), realtime bus, gộp thêm kênh mới.

- 2026-07-22: **#4 `vct_social_comment`** — `vct.fb.post` (bài đăng theo dõi, dùng token Page của vct.messenger.account,
  `action_fetch_comments` qua Graph API) + `vct.fb.comment` (phát hiện ý định mua theo từ khoá VN → is_order_intent stored,
  action_hide/action_open_reply/action_create_order dùng lại wizard #1) + `vct.fb.comment.reply.wizard`. HTTP tách để mock.
  Menu dưới "Bán hàng đa kênh". 5/5 test.
  - Defer: webhook feed realtime (hiện kéo thủ công), auto-reply theo kịch bản, ẩn/xoá hàng loạt, private-reply (chuyển comment→inbox).

- 2026-07-22: **#6 `vct_social_catalog`** — nút "📤 Chia sẻ SP" trên hội thoại Zalo/Messenger →
  `vct.social.share.wizard` (chọn product_ids + kèm giá + lời nhắn) → gửi thẻ SP (tên/giá/mô tả) cho khách qua
  `conversation._send_text` (dùng lại `_send_message` của kênh). 4/4 test. deps: vct_social_sales.
  - #5 Livestream: **bỏ** theo yêu cầu chủ dự án.

## Trạng thái Pancake: HOÀN TẤT các tính năng đặc trưng đã chọn
5/6 làm (1 chốt-đơn · 2 vận-chuyển · 3 inbox · 4 bình-luận · 6 chia-sẻ-SP), #5 livestream bỏ.
Mở rộng thêm nếu muốn: đồng bộ 2 chiều realtime trong inbox, auto-reply kịch bản (Botcake sâu hơn),
đối soát COD, đồng bộ tồn kho khi chốt đơn, kênh TikTok/Instagram.
