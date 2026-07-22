# Written for VCT Platform. Not part of Odoo S.A.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class KnowledgeArticle(models.Model):
    _name = 'knowledge.article'
    _description = 'Bài viết'
    # html.field.history.mixin keeps past revisions of `body`: the field is
    # collaborative and sanitize=False, so a bad paste would otherwise be
    # unrecoverable. project.task uses the same mixin the same way.
    _inherit = ['mail.thread', 'html.field.history.mixin']
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(string='Tiêu đề', required=True, index='trigram', tracking=True)
    complete_name = fields.Char(
        string='Đường dẫn', compute='_compute_complete_name', recursive=True, store=True)
    icon = fields.Char(
        string='Biểu tượng', default='📄',
        help="Một emoji hiển thị cạnh tiêu đề.")
    # sanitize=True is not optional here: articles are written by one employee
    # and rendered to every other, so unsanitised HTML is stored XSS. The history
    # mixin refuses to version an unsanitised field for exactly this reason.
    body = fields.Html(string='Nội dung', sanitize=True)
    parent_id = fields.Many2one(
        'knowledge.article', string='Bài viết cha', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('knowledge.article', 'parent_id', string='Bài viết con')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    internal_permission = fields.Selection([
        ('write', 'Mọi nhân viên sửa được'),
        ('read', 'Mọi nhân viên chỉ đọc'),
        ('none', 'Riêng tư'),
    ], string='Quyền', required=True, default='write', tracking=True,
        help="Đặt trên bài viết gốc và áp dụng cho toàn bộ nhánh bên dưới.")
    root_article_id = fields.Many2one(
        'knowledge.article', string='Bài viết gốc', compute='_compute_root_article_id',
        recursive=True, store=True,
        help="Bài viết đầu nhánh; quyền của nó quyết định cả nhánh.")
    inherited_permission = fields.Selection(
        related='root_article_id.internal_permission', string='Quyền áp dụng')
    favorite_user_ids = fields.Many2many(
        'res.users', 'knowledge_article_favorite_rel', 'article_id', 'user_id',
        string='Người đánh dấu', copy=False)
    is_favorite = fields.Boolean(
        string='Yêu thích', compute='_compute_is_favorite', inverse='_inverse_is_favorite',
        search='_search_is_favorite')
    child_count = fields.Integer(string='Số bài viết con', compute='_compute_child_count')

    def _get_versioned_fields(self):
        return [KnowledgeArticle.body.name]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for article in self:
            article.complete_name = f'{article.parent_id.complete_name} / {article.name}' \
                if article.parent_id else article.name

    @api.depends('parent_id', 'parent_id.root_article_id')
    def _compute_root_article_id(self):
        for article in self:
            article.root_article_id = article.parent_id.root_article_id or article.parent_id or article

    def _compute_child_count(self):
        counts = dict(self.env['knowledge.article']._read_group(
            [('parent_id', 'in', self.ids)], ['parent_id'], ['__count']))
        for article in self:
            article.child_count = counts.get(article, 0)

    @api.depends_context('uid')
    def _compute_is_favorite(self):
        for article in self:
            article.is_favorite = self.env.user in article.favorite_user_ids

    def _inverse_is_favorite(self):
        for article in self:
            article.sudo().favorite_user_ids = [
                (4 if article.is_favorite else 3, self.env.uid)]

    def _search_is_favorite(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('favorite_user_ids', 'in', self.env.uid)]

    @api.constrains('parent_id')
    def _check_recursion(self):
        if self._has_cycle():
            raise ValidationError(_("Bài viết không thể là con của chính nó."))

    @api.constrains('internal_permission', 'parent_id')
    def _check_permission_on_root_only(self):
        for article in self:
            if article.parent_id and article.internal_permission != article.root_article_id.internal_permission:
                raise ValidationError(_(
                    "Quyền chỉ đặt được trên bài viết gốc (%s); các bài viết con luôn theo nhánh.",
                    article.root_article_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # a child always follows its branch, whatever the caller passed
            if vals.get('parent_id'):
                root = self.browse(vals['parent_id']).root_article_id
                vals['internal_permission'] = root.internal_permission
        return super().create(vals_list)

    def write(self, vals):
        if 'internal_permission' in vals:
            if any(article.parent_id for article in self):
                raise ValidationError(_("Quyền chỉ đổi được trên bài viết gốc."))
            # the roots must land first: a child checked against a root that has
            # not moved yet looks like it is breaking out of its branch
            result = super().write(vals)
            branch = self.search([('id', 'child_of', self.ids), ('id', 'not in', self.ids)])
            if branch:
                super(KnowledgeArticle, branch).write(
                    {'internal_permission': vals['internal_permission']})
            return result
        return super().write(vals)

    def action_toggle_favorite(self):
        for article in self:
            article.is_favorite = not article.is_favorite

    def action_create_child(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bài viết con'),
            'res_model': 'knowledge.article',
            'view_mode': 'form',
            'context': {'default_parent_id': self.id},
        }

    def action_view_children(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bài viết con'),
            'res_model': 'knowledge.article',
            'view_mode': 'list,form',
            'domain': [('id', 'child_of', self.id), ('id', '!=', self.id)],
            'context': {'default_parent_id': self.id},
        }
