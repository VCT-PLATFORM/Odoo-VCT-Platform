# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class SignTemplate(models.Model):
    """Mẫu tài liệu để ký: một PDF gốc + các vùng ký (chữ ký/họ tên/ngày) đặt trên trang."""
    _name = 'sign.template'
    _description = 'Mẫu ký điện tử'
    _order = 'name'

    name = fields.Char('Tên mẫu', required=True)
    active = fields.Boolean(default=True)
    pdf = fields.Binary('Tệp PDF gốc', required=True)
    pdf_filename = fields.Char('Tên tệp')
    item_ids = fields.One2many('sign.item', 'template_id', string='Vùng ký')
    request_count = fields.Integer(compute='_compute_request_count')

    def _compute_request_count(self):
        counts = dict(self.env['sign.request']._read_group(
            [('template_id', 'in', self.ids)], groupby=['template_id'], aggregates=['__count']))
        for tmpl in self:
            tmpl.request_count = counts.get(tmpl, 0)

    def action_new_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sign.request',
            'view_mode': 'form', 'context': {'default_template_id': self.id},
        }

    def action_view_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.name,
            'res_model': 'sign.request', 'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }
