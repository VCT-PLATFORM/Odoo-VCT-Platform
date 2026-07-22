# Written for VCT Platform. Not part of Odoo S.A.
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class VctAiTaskSchedule(models.Model):
    """A recurring delegation: the AI runs the same instruction on a schedule
    (every morning, every Monday...) and each run produces a vct.ai.task."""
    _name = 'vct.ai.task.schedule'
    _description = 'Việc giao AI định kỳ'
    _order = 'next_run'

    name = fields.Char('Tên lịch', required=True)
    instruction = fields.Text('Nội dung giao việc', required=True)
    user_id = fields.Many2one(
        'res.users', 'Chạy theo quyền', required=True, default=lambda self: self.env.user)
    use_tools = fields.Boolean('Cho phép thao tác dữ liệu', default=True)
    active = fields.Boolean(default=True)
    interval_number = fields.Integer('Lặp mỗi', default=1, required=True)
    interval_type = fields.Selection([
        ('hours', 'Giờ'), ('days', 'Ngày'), ('weeks', 'Tuần'), ('months', 'Tháng'),
    ], string='Đơn vị', default='days', required=True)
    next_run = fields.Datetime(
        'Lần chạy kế tiếp', required=True, default=fields.Datetime.now)
    last_run = fields.Datetime('Lần chạy gần nhất', readonly=True)
    run_count = fields.Integer('Số lần đã chạy', readonly=True, default=0)
    last_task_id = fields.Many2one('vct.ai.task', 'Việc gần nhất', readonly=True)
    task_ids = fields.One2many('vct.ai.task', 'schedule_id', 'Các lần chạy')
    task_count = fields.Integer(compute='_compute_task_count')

    _interval_positive = models.Constraint(
        'CHECK(interval_number > 0)', 'Khoảng lặp phải lớn hơn 0.')

    def _compute_task_count(self):
        # _read_group on a m2o returns recordset keys, not ids
        counts = dict(self.env['vct.ai.task']._read_group(
            [('schedule_id', 'in', self.ids)], groupby=['schedule_id'], aggregates=['__count']))
        for sched in self:
            sched.task_count = counts.get(sched, 0)

    def _spawn_task(self):
        """Create one delegated task from this schedule and queue it."""
        self.ensure_one()
        task = self.env['vct.ai.task'].create({
            'name': _('%(sched)s — %(when)s', sched=self.name,
                      when=fields.Datetime.to_string(fields.Datetime.now())),
            'instruction': self.instruction,
            'user_id': self.user_id.id,
            'use_tools': self.use_tools,
            'schedule_id': self.id,
        })
        task.action_run()
        self.write({
            'last_run': fields.Datetime.now(),
            'last_task_id': task.id,
            'run_count': self.run_count + 1,
            'next_run': fields.Datetime.now() + relativedelta(
                **{self.interval_type: self.interval_number}),
        })
        return task

    @api.model
    def _cron_run_schedules(self):
        due = self.search([('active', '=', True), ('next_run', '<=', fields.Datetime.now())])
        for sched in due:
            try:
                with self.env.cr.savepoint():
                    sched._spawn_task()
            except Exception:
                _logger.exception('Lịch việc AI %s lỗi khi sinh việc', sched.id)

    def action_run_now(self):
        for sched in self:
            sched._spawn_task()
        return True

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Các lần chạy'),
            'res_model': 'vct.ai.task', 'view_mode': 'list,form',
            'domain': [('schedule_id', '=', self.id)],
        }
