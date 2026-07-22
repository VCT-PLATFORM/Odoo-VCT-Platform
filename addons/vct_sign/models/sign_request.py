# Written for VCT Platform. Not part of Odoo S.A.
import base64
import hashlib
import logging
from collections import defaultdict
from io import BytesIO

from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SignRequest(models.Model):
    """Một yêu cầu ký từ mẫu. Khi ký: đóng chữ ký/họ tên/ngày lên đúng vị trí trên
    PDF, lưu bản đã ký + hash SHA-256 để lưu vết."""
    _name = 'sign.request'
    _description = 'Yêu cầu ký'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char('Tiêu đề', required=True, default='Yêu cầu ký', tracking=True)
    template_id = fields.Many2one('sign.template', string='Mẫu', required=True, ondelete='restrict')
    request_owner_id = fields.Many2one('res.users', 'Người gửi', default=lambda self: self.env.user)
    signer_partner_id = fields.Many2one('res.partner', string='Người ký')
    signer_email = fields.Char('Email người ký')
    signer_name = fields.Char('Chữ ký (gõ họ tên)', help='Người ký gõ họ tên làm chữ ký.')
    state = fields.Selection([
        ('draft', 'Nháp'), ('sent', 'Đã gửi'), ('signed', 'Đã ký'), ('cancel', 'Đã huỷ'),
    ], default='draft', tracking=True, string='Trạng thái')
    signed_pdf = fields.Binary('PDF đã ký', readonly=True, attachment=True)
    signed_filename = fields.Char()
    signed_on = fields.Datetime('Ký lúc', readonly=True)
    document_hash = fields.Char('Hash (SHA-256)', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def action_send(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'sent'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})

    def action_sign(self):
        for req in self:
            if req.state not in ('sent', 'draft'):
                continue
            if not req.signer_name:
                raise UserError(_('Cần nhập chữ ký (họ tên) trước khi ký.'))
            if not req.template_id.pdf:
                raise UserError(_('Mẫu chưa có tệp PDF.'))
            when = fields.Datetime.now()
            pdf_bytes = req._generate_signed_pdf(req.signer_name, when)
            req.write({
                'state': 'signed',
                'signed_pdf': base64.b64encode(pdf_bytes),
                'signed_filename': (req.name or 'signed') + '.pdf',
                'signed_on': when,
                'document_hash': hashlib.sha256(pdf_bytes).hexdigest(),
            })
            req.message_post(body=_('Đã ký bởi %(who)s lúc %(when)s. Hash: %(h)s',
                                    who=req.signer_name, when=when, h=req.document_hash[:16] + '…'))

    def _generate_signed_pdf(self, signer_name, when):
        """Đóng giá trị các vùng ký lên PDF gốc. reportlab tạo lớp phủ, pypdf ghép."""
        self.ensure_one()
        try:
            original = base64.b64decode(self.template_id.pdf)
            reader = PdfReader(BytesIO(original))
            writer = PdfWriter()
            items_by_page = defaultdict(list)
            for item in self.template_id.item_ids:
                items_by_page[item.page].append(item)
            date_str = fields.Datetime.context_timestamp(self, when).strftime('%d/%m/%Y')
            for index, page in enumerate(reader.pages, start=1):
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
                for item in items_by_page.get(index, []):
                    overlay = self._make_overlay(item, signer_name, date_str, width, height)
                    page.merge_page(overlay)
                writer.add_page(page)
            out = BytesIO()
            writer.write(out)
            return out.getvalue()
        except UserError:
            raise
        except Exception as e:
            _logger.exception('Ký PDF lỗi')
            raise UserError(_('Không tạo được PDF đã ký: %s', e))

    def _make_overlay(self, item, signer_name, date_str, width, height):
        buf = BytesIO()
        pdf = canvas.Canvas(buf, pagesize=(width, height))
        text = date_str if item.item_type == 'date' else (signer_name or '')
        font = 'Helvetica-Oblique' if item.item_type == 'signature' else 'Helvetica'
        size = max(9, min(18, int((item.height or 0.05) * height)))
        pdf.setFont(font, size)
        x = (item.pos_x or 0) * width
        # pos_y tính từ mép trên; PDF gốc toạ độ từ đáy → lật + hạ 1 dòng
        y = height - (item.pos_y or 0) * height - size
        pdf.drawString(x, y, text)
        pdf.save()
        buf.seek(0)
        return PdfReader(buf).pages[0]
