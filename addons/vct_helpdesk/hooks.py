# Written for VCT Platform. Not part of Odoo S.A.
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Bật extension `unaccent` để tìm kiếm không dấu tiếng Việt.

    Odoo tự dùng unaccent cho ilike khi extension tồn tại — không cần sửa gì thêm.
    vct_admin là superuser nên CREATE EXTENSION chạy được.
    """
    try:
        env.cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
        _logger.info("vct_helpdesk: đã bật extension unaccent (tìm kiếm không dấu)")
    except Exception:
        # ponytail: nếu không đủ quyền, chỉ mất tìm-không-dấu, không chặn cài đặt
        _logger.warning("vct_helpdesk: không tạo được extension unaccent (bỏ qua)")
