# Written for VCT Platform. Not part of Odoo S.A.

from . import models

# Models that get a contextual "Giao cho Trợ lý AI" action in their gear menu.
_DELEGATE_MODELS = [
    'account.move', 'helpdesk.ticket', 'sale.order', 'project.task',
    'res.partner', 'crm.lead', 'purchase.order',
]

# Server-action body: create a draft task with this record as context and open
# it, so the user types the actual instruction then clicks "Giao cho AI".
_DELEGATE_CODE = """
task = env['vct.ai.task'].create({
    'name': 'Giao AI: ' + (record.display_name or record._name),
    'instruction': 'Mô tả việc cần làm cho bản ghi này...',
    'res_model': record._name,
    'res_id': record.id,
    'user_id': env.uid,
})
action = {
    'type': 'ir.actions.act_window',
    'res_model': 'vct.ai.task',
    'res_id': task.id,
    'view_mode': 'form',
    'target': 'current',
}
""".strip()


def post_init_hook(env):
    ServerAction = env['ir.actions.server'].sudo()
    for model_name in _DELEGATE_MODELS:
        model = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not model:
            continue   # app not installed -> skip
        if ServerAction.search_count([
                ('name', '=', 'Giao cho Trợ lý AI'), ('model_id', '=', model.id)]):
            continue   # already seeded
        ServerAction.create({
            'name': 'Giao cho Trợ lý AI',
            'model_id': model.id,
            'binding_model_id': model.id,
            'binding_type': 'action',
            'state': 'code',
            'code': _DELEGATE_CODE,
        })
