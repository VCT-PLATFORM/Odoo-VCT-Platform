# Written for VCT Platform. Not part of Odoo S.A.

{
    'name': 'Kế toán: Đối soát',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Đối soát thủ công các bút toán và theo dõi công nợ chưa đối soát',
    'description': """
Bổ sung lối vào giao diện cho phần đối soát mà account đã cài đặt sẵn:
chọn các dòng bút toán trong danh sách rồi Đối soát / Huỷ đối soát,
kèm màn hình "Công nợ chưa đối soát" nhóm theo tài khoản.

Không bao gồm tự động tải sao kê ngân hàng: đó là dịch vụ trả phí của Odoo.
""",
    'depends': ['account'],
    'data': [
        'views/account_reconciliation_views.xml',
    ],
    'author': 'VCT Platform',
    'license': 'LGPL-3',
}
