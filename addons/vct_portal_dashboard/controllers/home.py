# Written for VCT Platform. Not part of Odoo S.A.

from odoo.http import request
from odoo.addons.web.controllers.home import Home


class Home(Home):
    """Land on the portal app launcher (/my) after login instead of /odoo.

    Only the "fully logged in, no explicit redirect" branch is changed. A partial
    session (2FA/MFA pending) has no session.uid yet and must keep returning the
    MFA url, and an explicit ?redirect= deep link must still win — otherwise
    two-factor auth and shared links break.
    """

    def _login_redirect(self, uid, redirect=None):
        if not redirect and request.session.uid:
            return '/my'
        return super()._login_redirect(uid, redirect=redirect)
