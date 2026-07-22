# Written for VCT Platform. Not part of Odoo S.A.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # hr_timesheet declares these two as bare Booleans stored nowhere and renders
    # them with widget="upgrade_boolean": they are an Enterprise advert, not a
    # setting. The reminders themselves exist here, so make the switches real by
    # binding them to the crons that do the work.
    reminder_user_allow = fields.Boolean(
        string="Nhắc nhân viên nhập giờ", readonly=False,
        compute='_compute_reminder_allow', inverse='_inverse_reminder_user_allow')
    reminder_allow = fields.Boolean(
        string="Nhắc người duyệt", readonly=False,
        compute='_compute_reminder_allow', inverse='_inverse_reminder_allow')

    def _reminder_cron(self, xmlid):
        return self.env.ref(f'timesheet_grid.{xmlid}', raise_if_not_found=False)

    @api.depends_context('company')
    def _compute_reminder_allow(self):
        user_cron = self._reminder_cron('ir_cron_timesheet_reminder')
        approver_cron = self._reminder_cron('ir_cron_validation_reminder')
        for settings in self:
            settings.reminder_user_allow = bool(user_cron and user_cron.sudo().active)
            settings.reminder_allow = bool(approver_cron and approver_cron.sudo().active)

    def _inverse_reminder_user_allow(self):
        for settings in self:
            cron = settings._reminder_cron('ir_cron_timesheet_reminder')
            if cron:
                cron.sudo().active = settings.reminder_user_allow

    def _inverse_reminder_allow(self):
        for settings in self:
            cron = settings._reminder_cron('ir_cron_validation_reminder')
            if cron:
                cron.sudo().active = settings.reminder_allow
