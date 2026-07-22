# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    worksheet_template_id = fields.Many2one('maintenance.worksheet.template', string="Mẫu bảng công tác")
    worksheet_ids = fields.One2many('maintenance.worksheet', 'request_id', string="Bảng công tác")
    worksheet_count = fields.Integer("Số lượng bảng công tác", compute='_compute_worksheet_count')

    @api.depends('worksheet_ids')
    def _compute_worksheet_count(self):
        for rec in self:
            rec.worksheet_count = len(rec.worksheet_ids)

    def action_open_worksheet(self):
        self.ensure_one()
        if not self.worksheet_template_id:
            raise UserError(_("Vui lòng chọn mẫu bảng công tác trước."))
        
        # Check if there is an existing worksheet
        worksheet = self.worksheet_ids[:1]
        if not worksheet:
            # Create a new one
            worksheet = self.env['maintenance.worksheet'].create({
                'request_id': self.id,
                'template_id': self.worksheet_template_id.id,
            })
            
        return {
            'name': _('Bảng công tác bảo dưỡng'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.worksheet',
            'view_mode': 'form',
            'res_id': worksheet.id,
            'target': 'current',
        }
