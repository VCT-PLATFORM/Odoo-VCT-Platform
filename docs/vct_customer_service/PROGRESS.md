# VCT Customer Service — PROGRESS

Trạng thái sống để phiên sau tiếp tục ngay. Xem thiết kế đầy đủ: [DESIGN.md](DESIGN.md).

## Chốt (Phase 0)
- Build: **mở rộng `helpdesk`** · LLM: **Hybrid** · Zalo: **có OA+API** · Ưu tiên: **cả 4 differentiator, tuần tự**.
- DB live `vct-erp-odoo` trên `postgres:18.4-alpine` (Docker `vct-postgres`). Đã cài: helpdesk, helpdesk_repair,
  im_livechat, website_helpdesk, knowledge, crm/sale/account/account_followup/stock/repair/industry_fsm,
  vct_llm_assistant/vct_ai_workflow/vct_ai_task.

## Trạng thái phase
| Phase | Module | Trạng thái |
|---|---|---|
| 0 Thiết kế | — | ✅ Xong — đã duyệt |
| 1 Lõi ERP-native | `vct_helpdesk` | ✅ **Xong + live** (6/6 test pass) |
| 2 Zalo OA | `vct_helpdesk_zalo` | ✅ **Xong + live** (7/7 test pass) |
| 3 AI khách | `vct_helpdesk_ai` | ✅ **Xong + live** (8/8 test pass) |
| 4 Copilot + AutoQA | `vct_helpdesk_ai` | ✅ **Xong + live** (15/15 test tổng) |
| 5 AI write-actions | `vct_helpdesk_actions` | ✅ **Xong + live** (4/4 test pass) |
| 6 Data-masking (NĐ13) | `vct_helpdesk_privacy` | ✅ **Xong + live** (7/7 test pass) |
| 7 Facebook Messenger | `vct_helpdesk_messenger` | ✅ **Xong + live** (6/6 test pass) |
| 8 Report builder CS×ERP | `vct_helpdesk_report` | ✅ **Xong + live** (2/2 test pass) |
| — Voice/WFM/REST API | *(tương lai)* | ⬜ defer — chưa làm |

## Đã làm
- 2026-07-22: Khảo sát codebase, chốt 4 quyết định, viết DESIGN.md + PROGRESS.md.
- 2026-07-22: **Phase 1 `vct_helpdesk` xong + live.** deps: helpdesk, helpdesk_repair, sale, account.
  - `helpdesk.ticket` (+): commercial_partner_id, company_currency_id, cs_tier_id (related stored),
    sale_order_id, invoice_id, parent_id/child_ids/child_count, related_ticket_ids,
    360 computed non-stored (partner_due_amount=credit, sale_count, sale_total, last_order, ticket_count, warranty_count).
    `create` override → `_apply_cs_tier` (nâng priority nếu đang thấp + gắn thẻ SLA, không hạ mức tay).
  - Model mới `vct.cs.tier` (name/priority/sla_tag) + `res.partner.cs_tier_id`. Seed VIP/Thường.
  - Form ticket: trang "Toàn cảnh khách hàng" + 2 smart button (ticket con / ticket của KH) + badge hạng; search group-by hạng.
  - `resource.calendar` "Giờ làm VN" (T2–T6 8–17) + 4 ngày lễ dương 2026 (Tết âm = thêm tay). **CHƯA tự gán** cho công ty/team.
  - `post_init_hook`: `CREATE EXTENSION unaccent` (tìm không dấu tự có cho ilike).
  - Test: 6/6 pass. Live: module installed, 2 tiers, calendar+4 leaves, 6 field, unaccent=1.
  - Migration: module mới → cài đặt CHÍNH là migration (không có schema cũ để dời).

- 2026-07-22: **Phase 2 `vct_helpdesk_zalo` xong + live.** deps: vct_helpdesk.
  - `vct.zalo.account` (oa_id, app_id, access_token/refresh_token/secret_key [password=True], token_expiry, default_team_id).
    `_send_message` (Zalo Open API v3.0 /message/cs), `_refresh_token` (oauth v4) + cron 12h, `_verify_signature`
    (sha256(appId+data+timestamp+secret)), `_handle_inbound`. HTTP tách ở `_http_post` để mock.
  - `vct.zalo.conversation` (account/zalo_user_id/partner/ticket/state) — unique(account,user). `_get_or_create`,
    `_ensure_ticket` (mở lại ticket chưa fold hoặc tạo mới).
  - **Hội thoại = chatter ticket** (không dựng kho riêng): inbound → message_post(context zalo_inbound) vào ticket;
    override `helpdesk.ticket.message_post` → reply comment (subtype mt_comment) tự gửi ra Zalo, bỏ qua note nội bộ + tránh dội.
  - Controller `POST /vct_zalo/webhook` (auth public, csrf off, luôn trả 200).
  - Test: 7/7 pass (mock, không gọi Zalo thật). Live: module installed, 2 model, cron, route trả 200 'ok'.
  - **Cần chủ dự án khi dùng thật:** Helpdesk → Cấu hình → Tài khoản Zalo OA → nhập oa_id/app_id/access_token/secret_key;
    trỏ webhook Zalo về `<odoo>/vct_zalo/webhook`.

- 2026-07-22: **Phase 3 `vct_helpdesk_ai` xong + live.** deps: vct_helpdesk_zalo, vct_llm_assistant, knowledge.
  - **Quyết định an toàn:** KHÔNG đưa tool ERP cho model hướng khách. `vct.cs.ai.config._answer` pre-fetch đúng
    dữ liệu partner (`_partner_context`: đơn/giao/công nợ=credit/bảo hành, scope `child_of` commercial_partner)
    + RAG `_retrieve_kb` (ilike name/body trên knowledge.article, unaccent tự áp, scope kb_root_article_id) →
    nhồi vào system prompt → `mail.bot._run_agent(use_tools=False)`. Model không có tool → không lộ KH khác.
  - Guardrails trong prompt: chỉ dựa ngữ cảnh, không bịa, sentinel `<ESCALATE>` → chuyển người; lỗi LLM cũng escalate.
  - Hook Zalo: override `vct.zalo.account._handle_inbound` — conv 'bot' → AI trả lời (gửi Zalo + ghi 🤖 vào chatter
    zalo_inbound=True tránh gửi lặp) hoặc escalate → conv 'human' + note nội bộ. `vct.zalo.conversation._get_or_create`
    override: conv mới → 'bot' khi autoreply bật. Mọi lượt ghi `vct.cs.ai.log` (QA).
  - `vct.cs.ai.config` (autoreply/kb_root/max_kb/policy_text) — **autoreply mặc định TẮT** (bật thủ công khi sẵn sàng).
  - Test: 8/8 pass gồm **test bảo mật** (_partner_context không lộ KH khác) + guardrails. Live: module installed, 2 model, autoreply=false.
  - DEFER (Phase sau): write-action có xác nhận (đổi trả/đặt lịch KTV), kênh livechat/email, embeddings, confidence số.

- 2026-07-22: **Phase 4 (Copilot + AutoQA) xong + live** (trong `vct_helpdesk_ai`, dùng `-u`).
  - Copilot `vct.cs.copilot` (TransientModel wizard): 3 nút header ticket — Gợi ý trả lời (context ticket+hội thoại+KB),
    Tóm tắt, Viết lại (tone lịch sự/ngắn gọn/trang trọng). Kết quả agent xem/sửa; "Chèn làm trả lời" → message_post
    comment (tự ra Zalo nếu là ticket Zalo). Người luôn trong vòng lặp.
  - AutoQA `vct.cs.qa.score`: `_generate_for(ticket)` → LLM trả JSON {diem,nguy_co,nhan_xet} (parse chịu lỗi),
    gắn cờ at_risk. Nút "Chấm QA" trên ticket + cron `_cron_autoqa` (ticket đã đóng chưa chấm) — **cron TẮT sẵn**.
    Menu QA lọc sẵn nguy-cơ + chưa-soát.
  - `_conversation_text` (helpdesk.ticket) gom comment theo thời gian cho AI đọc.
  - Test: 15/15 (8 P3 + 7 P4). Live: 2 model, cron autoqa=false, access OK.
  - Lưu ý: linter từng xoá import side-effect trong models/__init__.py → đã thêm `# noqa: F401`.

- 2026-07-22: **4 hạng mục mở rộng xong + live** (chủ dự án chọn cả 4).
  - `vct_helpdesk_actions` — từ ticket: nút "Điều KTV" (FSM task), "Hoàn tiền/Đổi trả" (credit note), tái dùng nút
    tạo phiếu sửa chữa native của helpdesk_repair. Mở form điền sẵn → người lưu = xác nhận. Back-link project.task.helpdesk_ticket_id. 4/4 test.
  - `vct_helpdesk_privacy` — che số thẻ(13-19)/CCCD(9,12)/SĐT trong message_post + description; retention = **archive** (không xoá cứng),
    cron OFF. Mask enabled OFF mặc định. 7/7 test.
  - `vct_helpdesk_messenger` — kênh FB Messenger 2 chiều (mirror Zalo): webhook GET verify + POST (X-Hub-Signature-256),
    Send API v20.0, hội thoại=chatter ticket. 6/6 test.
  - `vct_helpdesk_report` — pivot+graph CS×ERP trên helpdesk.ticket (chiều hạng KH/đội/SLA-fail/CSAT), menu dưới Reporting;
    dùng report-builder gốc Odoo (kéo-thả, xuất Excel). 2/2 test.
  - **Sự cố Antigravity race** (xem [[odoo-dev-loop]]): server Antigravity cold-boot deadlock với migration trên ALTER project_project
    → SIGKILL migration kẹt + chờ pg_stat_activity quiescent + retry apply trong cửa sổ sạch. Đã khắc phục.

## 🎯 Bốn differentiator đã xong — quyết định tiếp
Cả 4 việc chủ dự án chọn (360° ERP · Zalo · AI khách · Copilot+AutoQA) **đã live, 36 test pass**. Còn lại là các
"module tương lai" đã defer từ Phase 0, **chờ chủ dự án chọn có làm không:**
- **Voice/CTI** — tổng đài SIP, click-to-call, screen-pop, ghi âm (cần vendor VN: Stringee/Omicall/3CX).
- **WFM** — dự báo tải, xếp ca, tuân thủ ca.
- **Report builder** — kéo-thả metric/dimension, nối dữ liệu CS×ERP, lịch gửi email.
- **REST API công khai** + OAuth + OpenAPI (đã có JSON-RPC sẵn).
- **Bảo mật nâng cao** — data-masking CCCD/thẻ/SĐT (NĐ 13/2023) + retention/xoá dữ liệu.
Ngoài ra có thể mở rộng: kênh **Facebook Messenger** (adapter tương tự Zalo), **AI write-action** (đổi trả/đặt lịch KTV có xác nhận), **embeddings** cho RAG.

## Điều cần biết cho Phase 1 (đã kiểm thực tế)
- helpdesk default priority không chắc '0' → test hạng kiểm bằng thẻ, không bằng giá trị priority tuyệt đối.
- công nợ = `res.partner.credit` (account). Không có `total_due` ở bản này.
- `helpdesk.ticket` KHÔNG có commercial_partner_id sẵn → tự thêm (related stored) để domain/tổng hợp dùng.
- Anchor form: `helpdesk.helpdesk_ticket_view_form`, button_box `//div[@name='button_box']`, có `//notebook`.

## Ghi chú vận hành (tránh vấp lại)
- Test module: DB tạm, cổng riêng — `--http-port=8998 --gevent-port=8997 --stop-after-init --test-tags /<mod>`
  (server live giữ 8069). `PGPASSWORD="$(docker exec vct-postgres printenv POSTGRES_PASSWORD)"`.
- Áp live: dừng server → `-i/-u <mod> --stop-after-init` → nohup relaunch → curl 200. Xem `scratchpad/apply_live.sh`.
- Odoo 19: `safe_eval(expr, context, *, mode)` **không có `nocopy`**; `_read_group` m2o trả recordset key (không phải id);
  trường `name` là jsonb (cast `::text` khi query psql).
