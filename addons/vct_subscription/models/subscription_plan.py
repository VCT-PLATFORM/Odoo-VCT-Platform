# Written for VCT Platform. Not part of Odoo S.A.
from odoo import fields, models


class SubscriptionPlan(models.Model):
    """Gói định kỳ: chu kỳ tính tiền (tuần/tháng/năm × số lượng)."""
    _name = 'vct.subscription.plan'
    _description = 'Gói thuê bao'
    _order = 'name'

    name = fields.Char('Tên gói', required=True, translate=True)
    active = fields.Boolean(default=True)
    period_value = fields.Integer('Chu kỳ mỗi', default=1, required=True)
    period_unit = fields.Selection([
        ('week', 'Tuần'), ('month', 'Tháng'), ('year', 'Năm'),
    ], string='Đơn vị', default='month', required=True)

    _period_positive = models.Constraint('CHECK(period_value > 0)', 'Chu kỳ phải lớn hơn 0.')

    def _period_in_months(self):
        """Số tháng tương đương (để quy đổi MRR)."""
        self.ensure_one()
        n = self.period_value or 1
        if self.period_unit == 'year':
            return n * 12.0
        if self.period_unit == 'week':
            return n / 4.333
        return float(n)
