# coding: utf-8
import xmlrpclib
import xlrd
from datetime import datetime, timedelta

print("\nStart time:", datetime.today())

# Odoo connection config
dbname = "v18_product_import"
username = 'admin'
pwd = 'admin'
sock_common = xmlrpclib.ServerProxy('http://localhost:8069/xmlrpc/common')
sock = xmlrpclib.ServerProxy('http://localhost:8069/xmlrpc/object')
uid = sock_common.login(dbname, username, pwd)

# Open Excel workbook
work_book = xlrd.open_workbook("/home/jatin/workspace/HQ_Product_List.xls")

# Utilities
def excel_serial_to_date(serial):
    start_date = datetime(1899, 12, 30) + timedelta(days=serial)
    return start_date.strftime("%Y-%m-%d %H:%M:%S")

def parse_exp_date(value):
    if isinstance(value, (int, float)):
        return excel_serial_to_date(value)
    elif isinstance(value, basestring):
        try:
            return datetime.strptime(value, '%d/%m/%Y').strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return value
    return str(value)

created_product = []

# Loop over sheet
for sheet in work_book._sheet_list:
    cnt = 0
    sheet_values = sheet._cell_values
    for sheet_data in sheet_values[2:]:
        if len(sheet_data) < 12:
            continue 
        cnt += 1
        if cnt <= 17:
            continue
        if cnt == 19:
            break
        prod_ref = sheet_data[0].encode('utf-8')
        name = sheet_data[1].encode('utf-8')
        category_name = sheet_data[2].encode('utf-8')
        p_uom = sheet_data[3].encode('utf-8')
        cost = sheet_data[4]
        price = sheet_data[6]
        barcode = sheet_data[8].encode('utf-8') if isinstance(sheet_data[8], basestring) else str(sheet_data[8])
        lot_no = sheet_data[9].encode('utf-8') if isinstance(sheet_data[9], basestring) else str(sheet_data[9])
        qty = sheet_data[10]
        exp_date = parse_exp_date(sheet_data[11])

        if prod_ref:
            # Get UoM ID
            uom_id = sock.execute_kw(dbname, uid, pwd, 'uom.uom', 'search', [[('name', '=', p_uom)]])
            if uom_id:
                uom_id = uom_id[0]
            else:
                # Create category if not found
                uom_id = sock.execute_kw(dbname, uid, pwd, 'uom.uom', 'create', [{
                    'name': p_uom,
                    'category_id':1,
                    'uom_type':'smaller',
                    'active': True,
                }])            

            # Get or Create Category ID
            category_id = sock.execute_kw(dbname, uid, pwd, 'product.category', 'search', [[('name', '=', category_name)]])
            if category_id:
                category_id = category_id[0]
            else:
                # Create category if not found
                category_id = sock.execute_kw(dbname, uid, pwd, 'product.category', 'create', [{
                    'name': category_name
                }])

            # Product data
            product_data = {
                'name': name,
                'default_code': prod_ref,
                'barcode': barcode,
                'list_price': price,
                'standard_price':cost,
                # 'qty_available':qty,
                'uom_id': uom_id,
                'uom_po_id': uom_id,
                'is_storable': True,
                'tracking': 'lot',
                'type': 'consu',
                'use_expiration_date': True,
                'categ_id': category_id,
            }

            print("product_data",product_data)
            # Search for product by internal reference
            existing = sock.execute_kw(dbname, uid, pwd, 'product.product', 'search', [[('default_code', '=', prod_ref)]])
            print("existing==\n",existing)
            if existing:
                # Update
                sock.execute_kw(dbname, uid, pwd, 'product.product', 'write', [existing, product_data])
                product_id = existing[0]
                print("Updated product:", prod_ref)
            else:
                # Create
                product_id = sock.execute_kw(dbname, uid, pwd, 'product.product', 'create', [product_data])
                print("Created product:", prod_ref)

            created_product.append(product_id)

print("Total products created or updated:", len(created_product),created_product)



esugh8erhgiuh
rwtgtrgtr
erwgrwgrg
fsbgwrbgfbh
sghhhhhhhh,,,
,
,
,
,
,
,
,,

,
,
,,
,
,

