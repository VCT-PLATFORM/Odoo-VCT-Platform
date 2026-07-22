# Written for VCT Platform. Not part of Odoo S.A.

from datetime import timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


# post_install: at_install runs mid-load, before modules that come later in the
# graph (account) put their required columns' fields in the registry, which
# makes creating a partner blow up on a NOT NULL column nobody has defaulted yet.
@tagged('post_install', '-at_install')
class TestHelpdesk(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_a = new_test_user(cls.env, 'helpdesk_a', groups='helpdesk.group_helpdesk_user')
        cls.user_b = new_test_user(cls.env, 'helpdesk_b', groups='helpdesk.group_helpdesk_user')
        cls.team = cls.env['helpdesk.team'].create({
            'name': 'Test Team',
            'assign_method': 'balanced',
            'member_ids': [(6, 0, (cls.user_a | cls.user_b).ids)],
            # SLA deadlines then count plain elapsed time, which keeps them predictable.
            'resource_calendar_id': False,
        })
        cls.stage_new = cls.env.ref('helpdesk.stage_new')
        cls.stage_progress = cls.env.ref('helpdesk.stage_in_progress')
        cls.stage_solved = cls.env.ref('helpdesk.stage_solved')

    def _create_ticket(self, **values):
        return self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket',
            'team_id': self.team.id,
            **values,
        })

    def _create_sla(self, **values):
        return self.env['helpdesk.sla'].create({
            'name': 'Test SLA',
            'team_id': self.team.id,
            'stage_id': self.stage_progress.id,
            'time': 4.0,
            **values,
        })

    # ---------------------------------------------------
    # Tickets
    # ---------------------------------------------------

    def test_default_stage(self):
        ticket = self._create_ticket()
        self.assertEqual(ticket.stage_id, self.stage_new)

    def test_balanced_assignment(self):
        tickets = self.env['helpdesk.ticket'].create([
            {'name': 'T%s' % i, 'team_id': self.team.id} for i in range(4)
        ])
        self.assertTrue(all(t.user_id for t in tickets))
        self.assertTrue(all(t.assign_date for t in tickets))
        # balanced: workload spread evenly between the two members
        self.assertEqual(len(tickets.filtered(lambda t: t.user_id == self.user_a)), 2)
        self.assertEqual(len(tickets.filtered(lambda t: t.user_id == self.user_b)), 2)

    def test_close_and_reopen(self):
        ticket = self._create_ticket()
        self.assertFalse(ticket.close_date)
        ticket.stage_id = self.stage_solved
        self.assertTrue(ticket.close_date)
        ticket.stage_id = self.stage_new
        self.assertFalse(ticket.close_date)

    def test_ticket_from_email(self):
        ticket = self.env['helpdesk.ticket'].message_new({
            'subject': 'Broken product',
            'email_from': 'Customer <customer@example.com>',
            'message_id': '<test@example.com>',
        }, custom_values={'team_id': self.team.id})
        self.assertEqual(ticket.name, 'Broken product')
        self.assertEqual(ticket.partner_email, 'customer@example.com',
                         "the raw 'Name <email>' from address must not leak into the field")
        self.assertEqual(ticket.partner_name, 'Customer')
        self.assertEqual(ticket.team_id, self.team)

    def test_ticket_from_email_matches_partner(self):
        partner = self.env['res.partner'].create({'name': 'Known', 'email': 'known@example.com'})
        ticket = self.env['helpdesk.ticket'].message_new({
            'subject': 'Help',
            'email_from': '"Known" <known@example.com>',
            'message_id': '<test2@example.com>',
        }, custom_values={'team_id': self.team.id})
        self.assertEqual(ticket.partner_id, partner)
        self.assertEqual(ticket.partner_email, 'known@example.com')

    # ---------------------------------------------------
    # SLA
    # ---------------------------------------------------

    def test_sla_deadline_without_calendar(self):
        sla = self._create_sla()
        ticket = self._create_ticket()
        status = ticket.sla_status_ids
        self.assertEqual(status.sla_id, sla)
        self.assertEqual(status.deadline, ticket.create_date + timedelta(hours=4))
        self.assertEqual(status.status, 'ongoing')
        self.assertEqual(ticket.sla_deadline, status.deadline)
        self.assertFalse(ticket.sla_fail)

    def test_sla_deadline_with_calendar(self):
        self.team.resource_calendar_id = self.env.company.resource_calendar_id
        self._create_sla()
        ticket = self._create_ticket()
        # Working hours skip nights and weekends, so the deadline can only be
        # pushed further away than plain elapsed time.
        self.assertGreaterEqual(
            ticket.sla_status_ids.deadline, ticket.create_date + timedelta(hours=4))

    def test_sla_reached_on_target_stage(self):
        self._create_sla()
        ticket = self._create_ticket()
        ticket.stage_id = self.stage_progress
        self.assertEqual(ticket.sla_status_ids.status, 'reached')
        self.assertFalse(ticket.sla_deadline, "no policy left to reach")
        self.assertFalse(ticket.sla_fail)

    def test_sla_reached_on_later_stage(self):
        self._create_sla()
        ticket = self._create_ticket()
        ticket.stage_id = self.stage_solved
        self.assertEqual(ticket.sla_status_ids.status, 'reached')

    # The deadline is counted from create_date, which the ORM refuses to set
    # outside of registry loading, so these two drive the clock instead of the
    # ticket's age: stamp the reach, or move "now" past the deadline.

    def test_sla_failed_when_reached_late(self):
        self._create_sla()
        ticket = self._create_ticket()
        status = ticket.sla_status_ids
        status.reached_datetime = status.deadline + timedelta(minutes=1)
        self.assertEqual(status.status, 'failed', "reached one minute after the deadline")
        self.assertTrue(ticket.sla_fail)

    def test_sla_reached_just_in_time_is_not_a_miss(self):
        self._create_sla()
        ticket = self._create_ticket()
        status = ticket.sla_status_ids
        status.reached_datetime = status.deadline
        self.assertEqual(status.status, 'reached', "landing exactly on the deadline still counts")
        self.assertFalse(ticket.sla_fail)

    def test_an_untouched_breached_ticket_is_still_flagged(self):
        """sla_fail is stored, so nothing recomputes it as time passes: without
        the cron a ticket that blows its deadline and is never touched again
        reports itself as green forever."""
        self._create_sla()
        ticket = self._create_ticket()
        self.assertFalse(ticket.sla_fail)
        later = ticket.sla_status_ids.deadline + timedelta(hours=1)
        with freeze_time(later):
            flagged = self.env['helpdesk.ticket']._cron_flag_sla_failures()
            self.assertIn(ticket, flagged)
            self.assertTrue(ticket.sla_fail, "nobody touched it, but it did breach")

    def test_sla_overdue_before_being_reached(self):
        self._create_sla()
        ticket = self._create_ticket()
        status = ticket.sla_status_ids
        self.assertEqual(status.status, 'ongoing')
        with freeze_time(status.deadline + timedelta(hours=1)):
            status.invalidate_recordset(['status'])
            self.assertEqual(status.status, 'failed', "past its deadline and still not reached")

    def test_sla_reach_is_sticky(self):
        self._create_sla()
        ticket = self._create_ticket()
        ticket.stage_id = self.stage_progress
        reached_at = ticket.sla_status_ids.reached_datetime
        ticket.stage_id = self.stage_new
        self.assertEqual(ticket.sla_status_ids.reached_datetime, reached_at,
                         "moving a ticket back must not clear a reached policy")

    def test_sla_follows_priority(self):
        self._create_sla(priority='2')
        ticket = self._create_ticket()
        self.assertFalse(ticket.sla_status_ids, "policy only covers high priority tickets")
        ticket.priority = '3'
        self.assertTrue(ticket.sla_status_ids, "raising the priority applies the policy")
        ticket.priority = '0'
        self.assertFalse(ticket.sla_status_ids, "lowering it back drops the unreached policy")

    def test_sla_follows_tags(self):
        tag = self.env['helpdesk.tag'].create({'name': 'Test Tag'})
        self._create_sla(tag_ids=[(6, 0, tag.ids)])
        ticket = self._create_ticket()
        self.assertFalse(ticket.sla_status_ids)
        ticket.tag_ids = tag
        self.assertTrue(ticket.sla_status_ids)

    def test_sla_reached_policy_is_kept(self):
        self._create_sla(priority='2')
        ticket = self._create_ticket(priority='3')
        ticket.stage_id = self.stage_progress
        self.assertEqual(ticket.sla_status_ids.status, 'reached')
        ticket.priority = '0'
        self.assertTrue(ticket.sla_status_ids,
                        "a reached policy is kept even once the ticket stops being covered")

    # ---------------------------------------------------
    # Portal & rating
    # ---------------------------------------------------

    def test_closed_stage_is_first_folded(self):
        self.assertEqual(self.team.closed_stage_id, self.stage_solved)

    def test_portal_user_sees_own_tickets_only(self):
        portal_user = new_test_user(self.env, 'helpdesk_portal', groups='base.group_portal')
        mine = self._create_ticket(partner_id=portal_user.partner_id.id)
        someone_else = self._create_ticket(
            partner_id=self.env['res.partner'].create({'name': 'Other'}).id)
        visible = self.env['helpdesk.ticket'].with_user(portal_user).search([])
        self.assertIn(mine, visible)
        self.assertNotIn(someone_else, visible)

    def test_rating_request_sent_on_stage(self):
        self.stage_solved.rating_template_id = self.env.ref('helpdesk.rating_ticket_request_email_template')
        partner = self.env['res.partner'].create({'name': 'Customer', 'email': 'c@example.com'})
        ticket = self._create_ticket(partner_id=partner.id)
        self.assertFalse(ticket.rating_ids)
        ticket.stage_id = self.stage_solved
        self.assertEqual(ticket.rating_ids.partner_id, partner,
                         "reaching the stage opens a rating for the customer")
