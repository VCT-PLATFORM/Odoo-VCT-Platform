# Written for VCT Platform. Not part of Odoo S.A.
import logging

_logger = logging.getLogger(__name__)

# Model được gắn nút "Hỏi AI" trong menu Hành động (nếu model tồn tại).
_ASK_MODELS = [
    'account.move', 'sale.order', 'crm.lead', 'project.task',
    'res.partner', 'purchase.order', 'helpdesk.ticket',
]

_ASK_CODE = """rec = records[:1]
action = {
    'type': 'ir.actions.act_window',
    'name': 'Hỏi AI',
    'res_model': 'ai.ask.wizard',
    'view_mode': 'form',
    'target': 'new',
    'context': {'active_model': rec._name, 'active_id': rec.id},
}"""


def post_init_hook(env):
    """Gắn hành động 'Hỏi AI' vào menu Hành động của các model chính (giống Odoo AI
    đưa AI vào ngữ cảnh từng app)."""
    Server = env['ir.actions.server'].sudo()
    Model = env['ir.model'].sudo()
    for model_name in _ASK_MODELS:
        model = Model.search([('model', '=', model_name)], limit=1)
        if not model:
            continue
        if Server.search_count([('binding_model_id', '=', model.id), ('name', '=', '🤖 Hỏi AI')]):
            continue
        Server.create({
            'name': '🤖 Hỏi AI',
            'model_id': model.id,
            'binding_model_id': model.id,
            'binding_type': 'action',
            'state': 'code',
            'code': _ASK_CODE,
        })
    _logger.info('vct_ai_agent: đã gắn "Hỏi AI" vào các model chính')
