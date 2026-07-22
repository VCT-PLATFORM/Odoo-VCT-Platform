# Written for VCT Platform. Not part of Odoo S.A.
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, route

# App launcher entries linked by backend menu, resolved by xmlid per-DB (no
# hardcoded menu ids). Core apps with a stable /odoo/<path> slug are linked
# directly in the template instead.
_APP_MENUS = {
    'crm': 'crm.crm_menu_root',
    'knowledge': 'knowledge.menu_knowledge_root',
    'helpdesk': 'helpdesk.menu_helpdesk_root',
    'ai_workflow': 'vct_ai_workflow.menu_ai_workflow_root',
}


class VctCustomerPortal(CustomerPortal):

    @route(['/my', '/my/home'], type='http', auth="user")
    def home(self, **kw):
        response = super().home(**kw)
        if not hasattr(response, 'qcontext'):
            return response

        env = request.env
        installed = set(env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))
        app_menus = {}
        for key, xmlid in _APP_MENUS.items():
            menu = env.ref(xmlid, raise_if_not_found=False)
            app_menus[key] = menu.id if menu else False

        response.qcontext.update({
            'installed_apps': installed,
            'current_user_name': env.user.name,
            'company_name': env.company.name,
            'app_menus': app_menus,
        })
        return response
