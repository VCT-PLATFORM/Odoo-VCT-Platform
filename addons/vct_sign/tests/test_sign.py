# Written for VCT Platform. Not part of Odoo S.A.
import base64
from io import BytesIO

from reportlab.pdfgen import canvas

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _make_pdf():
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawString(100, 700, 'Hop dong test')
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestSign(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env['sign.template'].create({
            'name': 'HĐ test', 'pdf': base64.b64encode(_make_pdf()), 'pdf_filename': 't.pdf',
            'item_ids': [
                (0, 0, {'item_type': 'signature', 'page': 1, 'pos_x': 0.1, 'pos_y': 0.8}),
                (0, 0, {'item_type': 'name', 'page': 1, 'pos_x': 0.1, 'pos_y': 0.7}),
                (0, 0, {'item_type': 'date', 'page': 1, 'pos_x': 0.6, 'pos_y': 0.8}),
            ]})

    def _req(self):
        return self.env['sign.request'].create({'name': 'Ký HĐ', 'template_id': self.template.id})

    def test_sign_full_flow_valid_pdf(self):
        req = self._req()
        req.action_send()
        self.assertEqual(req.state, 'sent')
        req.signer_name = 'Nguyễn Văn A'
        req.action_sign()
        self.assertEqual(req.state, 'signed')
        self.assertTrue(req.signed_pdf and req.signed_on)
        self.assertEqual(len(req.document_hash), 64, 'hash SHA-256 64 ký tự hex')
        raw = base64.b64decode(req.signed_pdf)
        self.assertTrue(raw.startswith(b'%PDF'), 'kết quả phải là PDF hợp lệ')

    def test_sign_requires_signature(self):
        req = self._req()
        req.action_send()
        with self.assertRaises(UserError):
            req.action_sign()

    def test_generate_stamps_without_error(self):
        req = self._req()
        pdf = req._generate_signed_pdf('Trần Thị B', fields.Datetime.now())
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 200)
