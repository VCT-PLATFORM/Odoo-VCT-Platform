# Written for VCT Platform. Not part of Odoo S.A.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_website_helpdesk = fields.Boolean(
        string="Nhận phiếu từ website",
        help="Cho phép khách gửi phiếu hỗ trợ bằng khối Form trên trang web.")
    module_helpdesk_repair = fields.Boolean(
        string="Sửa chữa",
        help="Tạo lệnh sửa chữa thẳng từ phiếu hỗ trợ.")
