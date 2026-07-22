# Written for VCT Platform. Not part of Odoo S.A.

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWebsiteHelpdesk(TransactionCase):

    def test_ticket_is_exposed_to_the_form_builder(self):
        model = self.env['ir.model']._get('helpdesk.ticket')
        self.assertTrue(model.website_form_access)
        self.assertEqual(model.website_form_key, 'create_ticket')

    def test_only_safe_fields_are_writable_from_the_web(self):
        """A visitor must not be able to file into an arbitrary team or stage,
        nor assign the ticket to somebody."""
        writable = set(self.env['ir.model']._get('helpdesk.ticket')._get_form_writable_fields())
        self.assertEqual(
            writable & {'name', 'description', 'partner_name', 'partner_email'},
            {'name', 'description', 'partner_name', 'partner_email'},
            "the fields a customer legitimately fills must be writable")
        for forbidden in ('team_id', 'stage_id', 'user_id', 'priority', 'sla_deadline'):
            self.assertNotIn(
                forbidden, writable, f"{forbidden} must not be settable from a public form")

    def test_input_filter_matches_a_known_customer_by_email(self):
        partner = self.env['res.partner'].create(
            {'name': 'Khách quen', 'email': 'known@example.com'})
        values = self.env['helpdesk.ticket'].website_form_input_filter(
            None, {'partner_email': 'known@example.com', 'name': 'Hỏng hàng'})
        self.assertEqual(values['partner_id'], partner.id)

    def test_input_filter_keeps_unknown_senders_as_plain_email(self):
        values = self.env['helpdesk.ticket'].website_form_input_filter(
            None, {'partner_email': 'stranger@example.com', 'name': 'Hỏng hàng'})
        self.assertNotIn('partner_id', values)
        self.assertEqual(values['partner_email'], 'stranger@example.com')

    def test_input_filter_supplies_a_subject_when_missing(self):
        values = self.env['helpdesk.ticket'].website_form_input_filter(None, {})
        self.assertTrue(values['name'], "name is required on the model")

    def test_a_ticket_filed_from_the_web_lands_in_a_team_and_first_stage(self):
        values = self.env['helpdesk.ticket'].website_form_input_filter(
            None, {'name': 'Từ web', 'partner_email': 'x@example.com'})
        ticket = self.env['helpdesk.ticket'].create(values)
        self.assertTrue(ticket.team_id, "the server picks the team, not the visitor")
        self.assertTrue(ticket.stage_id)
        self.assertFalse(ticket.stage_id.fold, "a new ticket must not start closed")
