import sys
import random
from datetime import datetime, timedelta
import odoo
import odoo.tools.config
import odoo.sql_db
import odoo.modules.registry
from odoo import fields

def generate_demo():
    odoo.tools.config.parse_config(['--addons-path=addons,odoo/addons', '-d', 'vct-erp-odoo', '--db_user=vct_admin', '--db_host=127.0.0.1', '--db_port=5432'])
    db = odoo.sql_db.db_connect('vct-erp-odoo')
    registry = odoo.modules.registry.Registry.new('vct-erp-odoo')
    
    with db.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        
        # 1. Ensure Suppliers / Partners exist
        print("1. Creating Suppliers & Partners...")
        suppliers_data = [
            {'name': 'Công ty Cổ phần Công nghệ & Thiết bị Hà Nội', 'supplier_rank': 1, 'email': 'contact@hanoitech.vn', 'phone': '024-3852-1111', 'city': 'Hà Nội'},
            {'name': 'Tập đoàn Điện tử & Viễn thông VCT', 'supplier_rank': 1, 'email': 'sales@vct-telecom.vn', 'phone': '028-7300-8888', 'city': 'Hồ Chí Minh'},
            {'name': 'Công ty TNHH Phần mềm & Giải pháp Số', 'supplier_rank': 1, 'email': 'info@digitalsolutions.vn', 'phone': '0236-3999-555', 'city': 'Đà Nẵng'},
            {'name': 'Công ty Cổ phần Thương mại & Sản xuất Minh Phát', 'supplier_rank': 1, 'email': 'minhphat@trade.com.vn', 'phone': '024-3766-2222', 'city': 'Hà Nội'},
        ]
        suppliers = env['res.partner']
        for sdata in suppliers_data:
            existing = env['res.partner'].search([('name', '=', sdata['name'])], limit=1)
            if not existing:
                existing = env['res.partner'].create(sdata)
            suppliers |= existing

        customers = env['res.partner'].search([('customer_rank', '>', 0)], limit=10)
        if not customers:
            customers = env['res.partner'].search([], limit=10)
            
        products = env['product.product'].search([], limit=15)
        company = env.company

        # 2. Purchase Orders
        print("2. Generating Purchase Orders...")
        if 'purchase.order' in env:
            po_count = env['purchase.order'].search_count([])
            if po_count < 5:
                for i in range(6):
                    supplier = suppliers[i % len(suppliers)]
                    date_order = fields.Datetime.now() - timedelta(days=random.randint(1, 45))
                    try:
                        po = env['purchase.order'].create({
                            'partner_id': supplier.id,
                            'date_order': date_order,
                            'company_id': company.id,
                            'order_line': [
                                (0, 0, {
                                    'product_id': prod.id,
                                    'name': prod.name,
                                    'product_qty': random.randint(5, 50),
                                    'product_uom_id': prod.uom_id.id,
                                    'price_unit': prod.standard_price or random.randint(100000, 5000000),
                                    'date_planned': date_order + timedelta(days=7),
                                }) for prod in products[i:i+3]
                            ]
                        })
                        if i % 2 == 0:
                            try:
                                po.button_confirm()
                            except Exception as e:
                                print(f"PO confirm notice: {e}")
                    except Exception as e:
                        print(f"PO create notice: {e}")

        # 3. Stock Pickings & Stock Quants
        print("3. Generating Stock & Warehouse Data...")
        warehouse = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        if warehouse and 'stock.picking' in env:
            picking_type_in = warehouse.in_type_id
            picking_type_out = warehouse.out_type_id
            
            # Create incoming picking
            if picking_type_in:
                try:
                    pick_in = env['stock.picking'].create({
                        'picking_type_id': picking_type_in.id,
                        'partner_id': suppliers[0].id,
                        'location_id': picking_type_in.default_location_src_id.id,
                        'location_dest_id': picking_type_in.default_location_dest_id.id,
                        'move_ids': [
                            (0, 0, {
                                'name': prod.name,
                                'product_id': prod.id,
                                'product_uom_qty': random.randint(10, 30),
                                'product_uom_id': prod.uom_id.id,
                                'location_id': picking_type_in.default_location_src_id.id,
                                'location_dest_id': picking_type_in.default_location_dest_id.id,
                            }) for prod in products[:3]
                        ]
                    })
                    pick_in.action_confirm()
                except Exception as e:
                    print(f"Picking IN notice: {e}")

            # Create outgoing picking
            if picking_type_out and customers:
                try:
                    pick_out = env['stock.picking'].create({
                        'picking_type_id': picking_type_out.id,
                        'partner_id': customers[0].id,
                        'location_id': picking_type_out.default_location_src_id.id,
                        'location_dest_id': picking_type_out.default_location_dest_id.id,
                        'move_ids': [
                            (0, 0, {
                                'name': prod.name,
                                'product_id': prod.id,
                                'product_uom_qty': random.randint(2, 10),
                                'product_uom_id': prod.uom_id.id,
                                'location_id': picking_type_out.default_location_src_id.id,
                                'location_dest_id': picking_type_out.default_location_dest_id.id,
                            }) for prod in products[3:6]
                        ]
                    })
                    pick_out.action_confirm()
                except Exception as e:
                    print(f"Picking OUT notice: {e}")

        # 4. Helpdesk Tickets
        print("4. Generating Helpdesk Tickets...")
        if 'helpdesk.ticket' in env:
            teams = env['helpdesk.team'].search([])
            if not teams:
                teams = env['helpdesk.team'].create({'name': 'Hỗ trợ Kỹ thuật & AI'})
            team = teams[0]
            
            stages = env['helpdesk.stage'].search([('team_ids', 'in', team.id)])
            if not stages:
                stages = env['helpdesk.stage'].search([])
            
            tickets_data = [
                {'name': 'Hỗ trợ tích hợp AI Chatbot vào Zalo OA', 'description': 'Khách hàng yêu cầu hỗ trợ kết nối tài khoản Zalo OA với hệ thống VCT Helpdesk AI.'},
                {'name': 'Lỗi không in được hóa đơn POS qua máy in mạng', 'description': 'Máy in POS tại quầy 2 không nhận lệnh in từ trình duyệt Chrome.'},
                {'name': 'Tư vấn cấu hình máy chủ Cloud cho Odoo Enterprise', 'description': 'Cần tư vấn thông số RAM/CPU tối ưu cho 50 người dùng đồng thời.'},
                {'name': 'Hướng dẫn tạo báo cáo doanh thu theo bộ phận', 'description': 'Bộ phận kế toán cần hướng dẫn thiết lập tài khoản quản trị (Analytic Account).'},
                {'name': 'Yêu cầu mở rộng dung lượng bộ nhớ filestore', 'description': 'Hệ thống sắp hết dung lượng đĩa cứng lưu trữ tài liệu đính kèm.'},
                {'name': 'Sự cố không nhận được email thông báo đơn hàng mới', 'description': 'Mail gateway bị từ chối do cấu hình SPF/DKIM chưa cập nhật.'},
                {'name': 'Hỗ trợ phân quyền người dùng cho nhân viên kinh doanh mới', 'description': 'Cấp quyền truy cập Phân hệ CRM & Bán hàng cho 3 nhân viên mới.'},
            ]
            
            for idx, tdata in enumerate(tickets_data):
                stage_id = stages[idx % len(stages)].id if stages else False
                try:
                    env['helpdesk.ticket'].create({
                        'name': tdata['name'],
                        'description': tdata['description'],
                        'team_id': team.id,
                        'stage_id': stage_id,
                        'partner_id': customers[idx % len(customers)].id if customers else False,
                        'priority': str(random.randint(0, 3)),
                    })
                except Exception as e:
                    print(f"Ticket notice: {e}")

        # 5. Manufacturing Orders (MRP)
        print("5. Generating Manufacturing Orders...")
        if 'mrp.production' in env:
            mrp_count = env['mrp.production'].search_count([])
            if mrp_count < 3 and products:
                finished_prod = products[0]
                bom = env['mrp.bom'].search([('product_tmpl_id', '=', finished_prod.product_tmpl_id.id)], limit=1)
                if not bom:
                    bom = env['mrp.bom'].create({
                        'product_tmpl_id': finished_prod.product_tmpl_id.id,
                        'product_qty': 1,
                        'type': 'normal',
                        'bom_line_ids': [
                            (0, 0, {'product_id': p.id, 'product_qty': 2}) for p in products[1:4]
                        ]
                    })
                
                for _ in range(4):
                    try:
                        env['mrp.production'].create({
                            'product_id': finished_prod.id,
                            'product_qty': random.randint(5, 20),
                            'bom_id': bom.id,
                            'product_uom_id': finished_prod.uom_id.id,
                            'company_id': company.id,
                        })
                    except Exception as e:
                        print(f"MRP notice: {e}")

        # 6. Additional Sales Orders
        print("6. Generating Sales Orders...")
        if 'sale.order' in env:
            so_count = env['sale.order'].search_count([])
            if so_count < 10 and customers and products:
                for i in range(5):
                    cust = customers[i % len(customers)]
                    try:
                        so = env['sale.order'].create({
                            'partner_id': cust.id,
                            'company_id': company.id,
                            'order_line': [
                                (0, 0, {
                                    'product_id': prod.id,
                                    'name': prod.name,
                                    'product_uom_qty': random.randint(1, 5),
                                    'price_unit': prod.list_price or random.randint(500000, 10000000),
                                }) for prod in products[i:i+3]
                            ]
                        })
                        if i % 2 == 0:
                            so.action_confirm()
                    except Exception as e:
                        print(f"SO notice: {e}")

        cr.commit()
        print(">>> SUCCESS: All demo data generated and committed to DB!")

if __name__ == '__main__':
    generate_demo()
