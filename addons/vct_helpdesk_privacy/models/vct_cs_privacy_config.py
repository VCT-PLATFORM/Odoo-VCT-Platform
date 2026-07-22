# Written for VCT Platform. Not part of Odoo S.A.
import logging
import re

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Heuristic — che số nhạy cảm. ponytail: điều chỉnh mẫu theo dữ liệu thật nếu vướng
# dương tính giả (mã đơn 9/12 chữ số...). Thẻ (13-19) an toàn nhất → bật mặc định.
_CARD = re.compile(r'\b(?:\d[ -]?){13,19}\b')
_ID = re.compile(r'\b\d{12}\b|\b\d{9}\b')          # CCCD 12, CMND 9
_PHONE = re.compile(r'\b(?:\+84|0)\d{9,10}\b')


def _keep_last4(match):
    digits = re.sub(r'\D', '', match.group(0))
    if len(digits) <= 4:
        return match.group(0)
    return '*' * (len(digits) - 4) + digits[-4:]


class VctCsPrivacyConfig(models.Model):
    """Che dữ liệu nhạy cảm (số thẻ/CCCD/SĐT) trong ticket + chính sách lưu trữ,
    hỗ trợ tuân thủ NĐ 13/2023. TẮT sẵn — bật khi đã kiểm mẫu khớp dữ liệu thật."""
    _name = 'vct.cs.privacy.config'
    _description = 'Cấu hình bảo mật CSKH'

    name = fields.Char('Tên', required=True, default='Cấu hình bảo mật CSKH')
    active = fields.Boolean(default=True)
    mask_enabled = fields.Boolean('Bật che dữ liệu', default=False)
    mask_cards = fields.Boolean('Che số thẻ (13–19 số)', default=True)
    mask_id = fields.Boolean('Che CCCD/CMND (9/12 số)', default=False,
                             help='Có thể che nhầm mã đơn cùng độ dài — kiểm trước khi bật.')
    mask_phone = fields.Boolean('Che số điện thoại', default=False,
                                help='Agent thường cần SĐT để gọi lại — cân nhắc.')
    retention_months = fields.Integer(
        'Lưu trữ ticket đóng sau (tháng)', default=0,
        help='0 = tắt. >0: cron sẽ LƯU TRỮ (archive, không xoá cứng) ticket đã đóng cũ hơn mốc này.')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model
    def _get_active(self):
        return self.search([('active', '=', True)], limit=1)

    def _mask_text(self, text):
        """Che số nhạy cảm theo cấu hình đang bật. Trả nguyên văn nếu tắt."""
        if not text:
            return text
        cfg = self._get_active()
        if not cfg or not cfg.mask_enabled:
            return text
        if cfg.mask_cards:
            text = _CARD.sub(_keep_last4, text)
        if cfg.mask_phone:
            text = _PHONE.sub(_keep_last4, text)
        if cfg.mask_id:
            text = _ID.sub(_keep_last4, text)
        return text

    @api.model
    def _cron_apply_retention(self):
        """LƯU TRỮ (archive) ticket đã đóng quá hạn. KHÔNG xoá cứng — xoá vĩnh viễn
        phải là hành động thủ công có chủ đích của người phụ trách dữ liệu."""
        cfg = self._get_active()
        if not cfg or cfg.retention_months <= 0:
            return
        cutoff = fields.Datetime.now() - relativedelta(months=cfg.retention_months)
        tickets = self.env['helpdesk.ticket'].search([
            ('stage_id.fold', '=', True), ('write_date', '<', cutoff), ('active', '=', True),
        ], limit=500)
        if tickets:
            tickets.write({'active': False})
            _logger.info('Bảo mật CSKH: lưu trữ %s ticket đóng quá %s tháng',
                         len(tickets), cfg.retention_months)
