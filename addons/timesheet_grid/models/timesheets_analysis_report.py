# Written for VCT Platform. Not part of Odoo S.A.

from odoo import api, fields, models


class TimesheetsAnalysisReport(models.Model):
    # sale_timesheet's report search view primary-inherits the timesheet line
    # search, so it copies the `to_validate` filter this module adds there. That
    # filter references `validated`, so the report model must expose it too — the
    # report is a SQL view over account_analytic_line, where we already add the
    # column. Without this, installing timesheet_grid breaks the report view.
    _inherit = 'timesheets.analysis.report'

    validated = fields.Boolean(string='Đã duyệt', readonly=True)

    @api.model
    def _select(self):
        return super()._select() + ",\n                A.validated AS validated"
