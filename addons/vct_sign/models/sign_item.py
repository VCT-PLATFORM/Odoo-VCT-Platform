# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class SignItem(models.Model):
    """Một vùng ký trên mẫu. Vị trí theo tỉ lệ 0–1 tính từ góc trên-trái của trang
    (không cần trình đặt trực quan cho MVP; nhập số)."""
    _name = 'sign.item'
    _description = 'Vùng ký'
    _order = 'page, id'

    template_id = fields.Many2one('sign.template', required=True, ondelete='cascade', index=True)
    item_type = fields.Selection([
        ('signature', 'Chữ ký'), ('name', 'Họ tên'), ('date', 'Ngày ký'),
    ], string='Loại', default='signature', required=True)
    page = fields.Integer('Trang', default=1, required=True)
    pos_x = fields.Float('X (0–1)', default=0.1, help='Tỉ lệ từ mép trái.')
    pos_y = fields.Float('Y (0–1)', default=0.85, help='Tỉ lệ từ mép trên.')
    width = fields.Float('Rộng (0–1)', default=0.25)
    height = fields.Float('Cao (0–1)', default=0.05)
    label = fields.Char('Nhãn')

    _page_positive = models.Constraint('CHECK(page > 0)', 'Số trang phải lớn hơn 0.')
