# -*- coding: utf-8 -*-
import base64
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountBankStatementImportQif(models.TransientModel):
    _name = 'account.bank.statement.import.qif'
    _description = 'Import QIF Bank Statement'

    file_data = fields.Binary("Tệp QIF", required=True)
    file_name = fields.Char("Tên tệp")
    journal_id = fields.Many2one('account.journal', string="Sổ nhật ký", required=True,
        domain="[('type', '=', 'bank')]")

    def _parse_qif_date(self, date_str):
        clean_str = date_str.replace("'", "/").replace(" ", "/").replace("-", "/").strip()
        for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y/%m/%d', '%d/%m/%Y', '%d/%m/%y'):
            try:
                return datetime.strptime(clean_str, fmt).date()
            except ValueError:
                continue
        return fields.Date.today()

    def action_import(self):
        self.ensure_one()
        try:
            file_content = base64.b64decode(self.file_data).decode('utf-8', errors='ignore')
        except Exception as e:
            raise UserError(_("Không thể đọc tệp QIF. Vui lòng đảm bảo tệp đúng định dạng. Chi tiết: %s") % str(e))

        # Split content into transactions by '^'
        tx_chunks = [c.strip() for c in file_content.split('^') if c.strip()]
        
        parsed_txs = []
        for chunk in tx_chunks:
            lines = chunk.split('\n')
            tx_data = {
                'date': None,
                'amount': 0.0,
                'payee': '',
                'memo': '',
            }
            is_valid_tx = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                code = line[0]
                val = line[1:].strip()
                if code == 'D':
                    tx_data['date'] = self._parse_qif_date(val)
                    is_valid_tx = True
                elif code == 'T':
                    # Parse amount: remove commas and whitespace
                    clean_amount = val.replace(',', '').replace(' ', '')
                    try:
                        tx_data['amount'] = float(clean_amount)
                    except ValueError:
                        tx_data['amount'] = 0.0
                elif code == 'P':
                    tx_data['payee'] = val
                elif code == 'M':
                    tx_data['memo'] = val

            if is_valid_tx:
                if not tx_data['date']:
                    tx_data['date'] = fields.Date.today()
                parsed_txs.append(tx_data)

        if not parsed_txs:
            raise UserError(_("Không tìm thấy giao dịch hợp lệ nào trong tệp QIF này."))

        # Create Bank Statement
        statement = self.env['account.bank.statement'].create({
            'name': self.file_name or _('Nhập từ tệp QIF %s') % fields.Date.today(),
            'journal_id': self.journal_id.id,
        })

        # Create Bank Statement Lines
        line_vals_list = []
        for tx in parsed_txs:
            # Try to match partner
            partner = False
            if tx['payee']:
                partner = self.env['res.partner'].search([('name', 'ilike', tx['payee'])], limit=1)

            ref = tx['payee']
            if tx['memo']:
                ref = f"{ref} - {tx['memo']}" if ref else tx['memo']

            line_vals_list.append({
                'statement_id': statement.id,
                'journal_id': self.journal_id.id,
                'date': tx['date'],
                'payment_ref': ref or _('Giao dịch QIF'),
                'amount': tx['amount'],
                'partner_id': partner.id if partner else False,
            })

        if line_vals_list:
            self.env['account.bank.statement.line'].create(line_vals_list)

        # Return action to open the newly created statement
        return {
            'name': _('Bản ghi sao kê đã nhập'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement',
            'view_mode': 'form',
            'res_id': statement.id,
            'target': 'current',
        }
