# Written for VCT Platform. Not part of Odoo S.A.
# Import cho side-effect (đăng ký model Odoo) — đừng để linter xoá.
from . import shipping_carrier  # noqa: F401
from . import shipment  # noqa: F401
from . import sale_order  # noqa: F401
