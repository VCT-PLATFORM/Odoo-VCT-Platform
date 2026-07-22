# Written for VCT Platform. Not part of Odoo S.A.

from . import models

# Manual-run AI workflow templates: (model, action name, prompt). Seeded only
# for models that exist, bound to the record's Action menu, and safe — they run
# only when a user clicks them, generate text, and write nothing.
_TEMPLATES = [
    ('account.move', 'AI: Tóm tắt & nhận định hoá đơn',
     "Tóm tắt hoá đơn {{ name }} của {{ partner_id.name }}: nội dung chính, "
     "tổng tiền, tình trạng thanh toán và điểm cần lưu ý. Trả lời ngắn gọn tiếng Việt."),
    ('sale.order', 'AI: Soạn email theo dõi báo giá',
     "Soạn một email tiếng Việt lịch sự theo dõi báo giá {{ name }} gửi "
     "{{ partner_id.name }}, nhắc nhẹ và mời phản hồi. Chỉ trả về nội dung email."),
    ('helpdesk.ticket', 'AI: Tóm tắt phiếu & gợi ý xử lý',
     "Tóm tắt phiếu hỗ trợ {{ name }} và đề xuất 2-3 bước xử lý tiếp theo. "
     "Trả lời ngắn gọn tiếng Việt."),
    ('hr.leave', 'AI: Tóm tắt đơn nghỉ phép',
     "Tóm tắt đơn nghỉ phép này (người xin, loại, số ngày, lý do) và nêu điểm "
     "người duyệt cần lưu ý. Trả lời ngắn gọn tiếng Việt."),
]


def post_init_hook(env):
    ServerAction = env['ir.actions.server'].sudo()
    for model_name, name, prompt in _TEMPLATES:
        model = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not model:
            continue   # app not installed -> skip its template
        if ServerAction.search_count([('name', '=', name), ('is_ai_workflow', '=', True)]):
            continue   # already seeded
        ServerAction.create({
            'name': name,
            'model_id': model.id,
            'state': 'ai_agent',
            'is_ai_workflow': True,
            'ai_prompt': prompt,
            'ai_use_tools': False,
            'binding_model_id': model.id,   # show in the record's Action menu
            'binding_type': 'action',
        })
