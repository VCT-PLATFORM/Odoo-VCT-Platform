# Dựng lại tính năng Enterprise (Community) — theo dõi

Enterprise-only trong bản này **không có code trên đĩa** (bản ghi ir_module_module mồ côi:
sign/sale_subscription/quality_control/mrp_plm/stock_barcode/web_studio/hr_appraisal/voip
"uninstallable"; documents/approvals/subscription/quality/sale_renting/hr_payroll/whatsapp
thiếu hẳn). → Dựng lại dạng module `vct_*` THẬT (có test, live), không stub. Studio ngoài phạm vi
(quy mô sản phẩm); VoIP cần vendor.

**Đã có sẵn (Enterprise-equiv, không cần dựng):** kế toán đầy đủ (account_reports/accountant/asset/
budget/followup/reconciliation), helpdesk (+7 module CS `vct_helpdesk*`), knowledge, appointment,
planning, industry_fsm, timesheet_grid, mass_mailing, hr_recruitment, website_slides, event.

## Trạng thái
| # | Tính năng Enterprise | Module | Trạng thái |
|---|---|---|---|
| 1 | Approvals (Phê duyệt) | `vct_approvals` | ✅ **Xong + live** (7/7 test) |
| 2 | Sign (Ký điện tử) | `vct_sign` | ✅ **Xong + live** (3/3 test) |
| 3 | Subscriptions (Thuê bao/định kỳ) | `vct_subscription` | ✅ **Xong + live** (6/6 test) |
| 4 | Rental (Cho thuê) | `vct_rental` | ✅ **Xong + live** (6/6 test) |
| 5 | Quality (Kiểm tra chất lượng) | `vct_quality` | ⏳ Kế tiếp |
| 6 | Documents (DMS) | `vct_documents` | ⬜ |
| 7 | Barcode (Quét mã kho) | `vct_barcode` | ⬜ |
| 8 | Appraisal (Đánh giá NV) | `vct_appraisal` | ⬜ |
| 9 | PLM (Thay đổi kỹ thuật) | `vct_plm` | ⬜ |
| 10 | Payroll (Lương) | `vct_payroll` | ⬜ |
| 11 | Social / Marketing Automation | `vct_*` | ⬜ (lớn) |
| — | Studio | — | ❌ ngoài phạm vi (product-scale) |
| — | VoIP | — | ⬜ cần vendor VN |

## Đã làm
- 2026-07-22: **#1 `vct_approvals`** — approval.category/request/approver, duyệt đa cấp (ngưỡng tối thiểu),
  hoạt động nhắc người duyệt, record-rule (thấy yêu cầu của mình/mình duyệt), nhóm quản trị, app menu. 7/7 test.
  - Odoo 19 gotchas gặp: `res.groups` bỏ `category_id`; `res.users.groups_id` → **`group_ids`**;
    computed phụ thuộc user PHẢI có **`@api.depends_context('uid')`** (cache không key theo user).

- 2026-07-22: **#2 `vct_sign`** — sign.template (PDF + vùng ký vị trí tỉ lệ 0–1) / sign.item (chữ ký/họ tên/ngày) /
  sign.request (draft→sent→signed). Ký = đóng giá trị lên PDF bằng **reportlab overlay + pypdf merge** → PDF đã ký
  (attachment) + **hash SHA-256** lưu vết. Nhóm quản trị + record-rule (yêu cầu của mình). 3/3 test (tạo PDF thật bằng reportlab).
  - Defer: trình đặt vùng ký trực quan (Studio-like), ký qua portal token (người ngoài), chữ ký vẽ tay/ảnh, đa người ký.
  - Venv có: reportlab 4.1, pypdf 6.14, PIL 10.2 (không có PyMuPDF/fitz).

- 2026-07-22: **#3 `vct_subscription`** — `vct.subscription.plan` (chu kỳ tuần/tháng/năm), `vct.subscription`
  (khách+gói+dòng SP, state draft/progress/paused/closed, sequence TB#####, next_invoice_date, recurring_total, **MRR** quy đổi/tháng),
  `vct.subscription.line`. `_create_invoice` → account.move out_invoice (journal sale + product income account); cron `_cron_generate_invoices`
  (progress + đến hạn → hoá đơn nháp + đẩy next_invoice_date). account.move += `vct_subscription_id`. 2 gói mẫu. 6/6 test (kèm kế toán tối thiểu).
  - Odoo 19: hoá đơn nháp (không tự post — người duyệt); DB test không có COA → test tự tạo account/journal/product-income-account.
  - Defer: upsell/gia hạn/churn analytics, pro-rata, tự động post hoá đơn, cổng khách tự đăng ký.

- 2026-07-22: **#4 `vct_rental`** — product.template += rental_ok/rental_price_day/rental_stock; `vct.rental.order`
  (khách + kỳ nhận–trả, duration_days, amount_total, state draft/confirmed/picked_up/returned/cancel, seq RENT#####),
  `vct.rental.order.line` (giá = giá/ngày × ngày × SL). `_check_availability` chặn cho thuê quá tồn khi kỳ trùng nhau.
  `_create_invoice` → account.move (qty×ngày). account.move += vct_rental_order_id. 6/6 test.
  - Defer: phí trả trễ tự động, đặt cọc, tích hợp stock reservation thật, giá theo giờ/tuần.

## Việc kế tiếp → #5 `vct_quality`
Kiểm tra chất lượng: điểm kiểm tra (quality point) theo sản phẩm/thao tác, phiếu kiểm (quality check) pass/fail,
cảnh báo chất lượng (quality alert). Gắn vào stock/mrp nếu có, hoặc độc lập trên sản phẩm.
