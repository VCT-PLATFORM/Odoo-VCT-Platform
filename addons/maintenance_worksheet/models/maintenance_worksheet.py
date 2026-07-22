# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class MaintenanceWorksheet(models.Model):
    _name = 'maintenance.worksheet'
    _description = 'Maintenance Worksheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char("Tên bảng công tác", compute='_compute_name', store=True)
    request_id = fields.Many2one('maintenance.request', string="Phiếu bảo dưỡng", required=True, ondelete='cascade', index=True)
    template_id = fields.Many2one('maintenance.worksheet.template', string="Mẫu bảng công tác", required=True, ondelete='restrict')
    line_ids = fields.One2many('maintenance.worksheet.line', 'worksheet_id', string="Nội dung thực hiện", copy=True)
    signature = fields.Binary("Chữ ký kỹ thuật viên")
    signed_by = fields.Char("Họ tên người ký")
    date_signed = fields.Datetime("Ngày ký")
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Hoàn thành')
    ], string="Trạng thái", default='draft', required=True, tracking=True)

    @api.depends('request_id.name', 'template_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.request_id and rec.template_id:
                rec.name = f"{rec.template_id.name} - {rec.request_id.name}"
            else:
                rec.name = "Bảng công tác bảo dưỡng"

    @api.model_create_multi
    def create(self, vals_list):
        records = super(MaintenanceWorksheet, self).create(vals_list)
        for record in records:
            if not record.line_ids:
                # Pre-fill worksheet lines from template
                lines_vals = []
                for t_line in record.template_id.line_ids:
                    lines_vals.append({
                        'worksheet_id': record.id,
                        'template_line_id': t_line.id,
                    })
                if lines_vals:
                    self.env['maintenance.worksheet.line'].create(lines_vals)
        return records

    def action_done(self):
        for rec in self:
            # Check required fields
            for line in rec.line_ids:
                if line.is_required:
                    if line.type == 'checkbox' and not line.value_checkbox:
                        raise ValidationError(_("Công tác bắt buộc chưa hoàn thành: %s") % line.name)
                    elif line.type == 'text' and not line.value_text:
                        raise ValidationError(_("Vui lòng nhập câu trả lời cho: %s") % line.name)
                    elif line.type == 'number' and line.value_number is False:
                        raise ValidationError(_("Vui lòng nhập giá trị số cho: %s") % line.name)
                    elif line.type == 'selection' and not line.value_option_id:
                        raise ValidationError(_("Vui lòng chọn một tùy chọn cho: %s") % line.name)
            rec.state = 'done'

    def action_draft(self):
        self.state = 'draft'


class MaintenanceWorksheetLine(models.Model):
    _name = 'maintenance.worksheet.line'
    _description = 'Maintenance Worksheet Line'
    _order = 'sequence, id'

    worksheet_id = fields.Many2one('maintenance.worksheet', string="Bảng công tác", required=True, ondelete='cascade', index=True)
    template_line_id = fields.Many2one('worksheet.template.line', string="Câu hỏi gốc", required=True, ondelete='restrict')
    sequence = fields.Integer("Thứ tự", related='template_line_id.sequence', store=True)
    name = fields.Char("Công tác/Câu hỏi", related='template_line_id.name', readonly=True, store=True)
    type = fields.Selection(related='template_line_id.type', readonly=True)
    is_required = fields.Boolean(related='template_line_id.is_required', readonly=True)

    value_checkbox = fields.Boolean("Đã hoàn thành")
    value_text = fields.Text("Câu trả lời")
    value_number = fields.Float("Giá trị đo được")
    value_option_id = fields.Many2one('worksheet.template.line.option', string="Lựa chọn")
