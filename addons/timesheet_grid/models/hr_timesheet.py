# Written for VCT Platform. Not part of Odoo S.A.

from odoo import _, api, fields, models
from odoo.exceptions import UserError

APPROVER = 'hr_timesheet.group_hr_timesheet_approver'


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    validated = fields.Boolean(
        string='Đã duyệt', default=False, readonly=True, copy=False,
        help="Dòng đã duyệt thì khoá lại: chỉ người duyệt mới sửa hay bỏ duyệt được.")
    validated_by_id = fields.Many2one(
        'res.users', string='Người duyệt', readonly=True, copy=False)
    validated_date = fields.Datetime(string='Ngày duyệt', readonly=True, copy=False)

    def _is_timesheet(self):
        """Only project timesheets take part in the approval flow; plain analytic
        lines (accounting cost entries) are none of its business."""
        return self.filtered(lambda line: line.project_id)

    def action_validate(self):
        if not self.env.user.has_group(APPROVER):
            raise UserError(_("Bạn không có quyền duyệt chấm công."))
        lines = self._is_timesheet()
        if not lines:
            raise UserError(_("Chỉ duyệt được dòng chấm công của dự án."))
        lines.write({
            'validated': True,
            'validated_by_id': self.env.uid,
            'validated_date': fields.Datetime.now(),
        })
        return True

    def action_invalidate(self):
        if not self.env.user.has_group(APPROVER):
            raise UserError(_("Bạn không có quyền bỏ duyệt chấm công."))
        self.write({'validated': False, 'validated_by_id': False, 'validated_date': False})
        return True

    def _check_can_write_validated(self, vals=None):
        """A validated line is settled: the employee must not be able to move
        their hours after the fact, and an approver has to unlock it first."""
        # the approval fields themselves are how the lock is opened and closed
        approval_fields = {'validated', 'validated_by_id', 'validated_date'}
        if vals is not None and set(vals) <= approval_fields:
            return
        locked = self.filtered('validated')
        if locked and not self.env.user.has_group(APPROVER):
            raise UserError(_(
                "Dòng chấm công đã duyệt thì không sửa được nữa. "
                "Hãy nhờ người duyệt bỏ duyệt trước."))

    def write(self, vals):
        self._check_can_write_validated(vals)
        return super().write(vals)

    def unlink(self):
        self._check_can_write_validated()
        return super().unlink()
