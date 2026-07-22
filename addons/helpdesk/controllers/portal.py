# Written for VCT Platform. Not part of Odoo S.A.

from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class HelpdeskCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'ticket_count' in counters:
            values['ticket_count'] = request.env['helpdesk.ticket'].search_count([]) \
                if request.env['helpdesk.ticket'].has_access('read') else 0
        return values

    def _ticket_searchbar_sortings(self):
        return {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Subject'), 'order': 'name'},
            'stage': {'label': _('Stage'), 'order': 'stage_id'},
        }

    def _ticket_searchbar_filters(self):
        return {
            'all': {'label': _('All'), 'domain': []},
            'open': {'label': _('Open'), 'domain': [('stage_id.fold', '=', False)]},
            'closed': {'label': _('Closed'), 'domain': [('stage_id.fold', '=', True)]},
        }

    @http.route(['/my/tickets', '/my/tickets/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_tickets(self, page=1, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        searchbar_sortings = self._ticket_searchbar_sortings()
        searchbar_filters = self._ticket_searchbar_filters()
        if sortby not in searchbar_sortings:
            sortby = 'date'
        if filterby not in searchbar_filters:
            filterby = 'all'

        Ticket = request.env['helpdesk.ticket']
        domain = searchbar_filters[filterby]['domain']
        pager = portal_pager(
            url='/my/tickets',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=Ticket.search_count(domain),
            page=page,
            step=self._items_per_page,
        )
        tickets = Ticket.search(
            domain, order=searchbar_sortings[sortby]['order'],
            limit=self._items_per_page, offset=pager['offset'])
        request.session['my_tickets_history'] = tickets.ids[:100]

        values.update({
            'tickets': tickets,
            'page_name': 'ticket',
            'pager': pager,
            'default_url': '/my/tickets',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })
        return request.render('helpdesk.portal_my_tickets', values)

    @http.route(['/my/tickets/<int:ticket_id>'], type='http', auth='public', website=True)
    def portal_my_ticket(self, ticket_id, access_token=None, **kw):
        try:
            ticket_sudo = self._document_check_access('helpdesk.ticket', ticket_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = self._get_page_view_values(
            ticket_sudo, access_token, {'ticket': ticket_sudo, 'page_name': 'ticket'},
            'my_tickets_history', False, **kw)
        return request.render('helpdesk.portal_my_ticket', values)

    @http.route(['/my/tickets/<int:ticket_id>/close'], type='http', auth='public',
                methods=['POST'], website=True)
    def portal_ticket_close(self, ticket_id, access_token=None, **kw):
        try:
            ticket_sudo = self._document_check_access('helpdesk.ticket', ticket_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        closed_stage = ticket_sudo.team_id.closed_stage_id
        if ticket_sudo.team_id.allow_portal_close and closed_stage:
            ticket_sudo.stage_id = closed_stage
        # only carry the token back, never mint one for a logged-in customer
        url = f'/my/tickets/{ticket_id}'
        return request.redirect(f'{url}?access_token={access_token}' if access_token else url)
