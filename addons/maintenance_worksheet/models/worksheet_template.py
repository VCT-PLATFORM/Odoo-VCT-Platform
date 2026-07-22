# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class MaintenanceWorksheetTemplate(models.Model):
    _name = 'maintenance.worksheet.template'
    _description = 'Maintenance Worksheet Template'
    _order = 'name'

    name = fields.Char("Tên mẫu", required=True, translate=True)
    description = fields.Text("Mô tả")
    line_ids = fields.One2many('worksheet.template.line', 'template_id', string="Công tác/Câu hỏi", copy=True)
    active = fields.Boolean("Đang hoạt động", default=True)


class WorksheetTemplateLine(models.Model):
    _name = 'worksheet.template.line'
    _description = 'Worksheet Template Line'
    _order = 'sequence, id'

    template_id = fields.Many2one('maintenance.worksheet.template', string="Mẫu bảng công tác", required=True, ondelete='cascade')
    sequence = fields.Integer("Thứ tự", default=10)
    name = fields.Char("Công tác/Câu hỏi", required=True, translate=True)
    type = fields.Selection([
        ('checkbox', 'Hộp kiểm (Checkbox)'),
        ('text', 'Văn bản (Text)'),
        ('number', 'Số (Number)'),
        ('selection', 'Lựa chọn (Selection)')
    ], string="Loại câu hỏi", default='checkbox', required=True)
    option_ids = fields.One2many('worksheet.template.line.option', 'line_id', string="Các lựa chọn", copy=True)
    is_required = fields.Boolean("Bắt buộc điền", default=False)


class WorksheetTemplateLineOption(models.Model):
    _name = 'worksheet.template.line.option'
    _description = 'Worksheet Template Line Option'
    _order = 'sequence, id'

    line_id = fields.Many2one('worksheet.template.line', string="Dòng câu hỏi", required=True, ondelete='cascade')
    sequence = fields.Integer("Thứ tự", default=10)
    name = fields.Char("Tên lựa chọn", required=True, translate=True)
