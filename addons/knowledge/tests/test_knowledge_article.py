# Written for VCT Platform. Not part of Odoo S.A.

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestKnowledgeArticle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = new_test_user(cls.env, 'kn_author', groups='knowledge.group_knowledge_user')
        cls.other = new_test_user(cls.env, 'kn_other', groups='knowledge.group_knowledge_user')
        cls.manager = new_test_user(cls.env, 'kn_manager', groups='knowledge.group_knowledge_manager')

    def _article(self, user=None, **values):
        return self.env['knowledge.article'].with_user(user or self.author).create({
            'name': 'Bài viết', **values,
        })

    # --- hierarchy

    def test_complete_name_shows_the_path(self):
        root = self._article(name='Sổ tay')
        child = self._article(name='Nghỉ phép', parent_id=root.id)
        leaf = self._article(name='Nghỉ ốm', parent_id=child.id)
        self.assertEqual(leaf.complete_name, 'Sổ tay / Nghỉ phép / Nghỉ ốm')

    def test_root_article_is_the_top_of_the_branch(self):
        root = self._article(name='Sổ tay')
        child = self._article(name='Con', parent_id=root.id)
        leaf = self._article(name='Cháu', parent_id=child.id)
        self.assertEqual(leaf.root_article_id, root)
        self.assertEqual(root.root_article_id, root, "a root is its own root")

    def test_an_article_cannot_be_its_own_ancestor(self):
        root = self._article(name='A')
        child = self._article(name='B', parent_id=root.id)
        # the parent_store machinery catches the loop before our constraint does,
        # and it raises a plain UserError
        with self.assertRaises(UserError):
            root.parent_id = child

    def test_deleting_a_root_takes_its_branch(self):
        root = self._article(name='A')
        child = self._article(name='B', parent_id=root.id)
        root.unlink()
        self.assertFalse(child.exists(), "children are cascaded with their parent")

    def test_child_count_counts_direct_children_only(self):
        root = self._article(name='A')
        child = self._article(name='B', parent_id=root.id)
        self._article(name='C', parent_id=child.id)
        self.assertEqual(root.child_count, 1, "grandchildren are not direct children")

    # --- permissions

    def test_a_child_always_inherits_the_branch_permission(self):
        root = self._article(name='Riêng', internal_permission='none')
        child = self.env['knowledge.article'].with_user(self.author).create({
            'name': 'Con', 'parent_id': root.id, 'internal_permission': 'write',
        })
        self.assertEqual(child.internal_permission, 'none',
                         "the caller cannot loosen a branch by passing another value")

    def test_permission_cannot_be_set_on_a_child(self):
        root = self._article(name='A')
        child = self._article(name='B', parent_id=root.id)
        with self.assertRaises(ValidationError):
            child.internal_permission = 'none'

    def test_changing_the_root_permission_moves_the_whole_branch(self):
        root = self._article(name='A')
        child = self._article(name='B', parent_id=root.id)
        leaf = self._article(name='C', parent_id=child.id)
        root.internal_permission = 'read'
        self.assertEqual(child.internal_permission, 'read')
        self.assertEqual(leaf.internal_permission, 'read', "deep children follow too")

    def test_a_private_branch_is_invisible_to_others(self):
        root = self._article(name='Riêng tư', internal_permission='none')
        child = self._article(name='Con riêng tư', parent_id=root.id)
        visible = self.env['knowledge.article'].with_user(self.other).search([])
        self.assertNotIn(root, visible)
        self.assertNotIn(child, visible, "the child of a private root is private too")
        self.assertIn(root, self.env['knowledge.article'].with_user(self.author).search([]))

    def test_a_read_only_branch_cannot_be_edited_by_others(self):
        root = self._article(name='Chỉ đọc', internal_permission='read')
        child = self._article(name='Con', parent_id=root.id)
        self.assertIn(child, self.env['knowledge.article'].with_user(self.other).search([]),
                      "read-only still means readable")
        with self.assertRaises(AccessError):
            child.with_user(self.other).name = 'Sửa trộm'

    def test_a_writable_branch_is_editable_by_everyone(self):
        root = self._article(name='Công khai', internal_permission='write')
        root.with_user(self.other).name = 'Ai cũng sửa được'
        self.assertEqual(root.name, 'Ai cũng sửa được')

    def test_the_author_keeps_access_to_their_own_private_branch(self):
        root = self._article(name='Của tôi', internal_permission='none')
        root.with_user(self.author).body = '<p>ghi chú</p>'
        self.assertEqual(root.body, '<p>ghi chú</p>')

    def test_a_manager_sees_private_branches(self):
        root = self._article(name='Riêng tư', internal_permission='none')
        self.assertIn(root, self.env['knowledge.article'].with_user(self.manager).search([]))

    # --- favourites

    def test_favorite_is_per_user(self):
        article = self._article(name='A')
        article.with_user(self.author).action_toggle_favorite()
        self.assertTrue(article.with_user(self.author).is_favorite)
        self.assertFalse(article.with_user(self.other).is_favorite,
                         "one user's star is not another's")

    def test_favorite_toggles_off(self):
        article = self._article(name='A')
        article.with_user(self.author).action_toggle_favorite()
        article.with_user(self.author).action_toggle_favorite()
        self.assertFalse(article.with_user(self.author).is_favorite)

    def test_searching_favorites_returns_only_mine(self):
        mine = self._article(name='Của tôi')
        theirs = self._article(name='Của người khác')
        mine.with_user(self.author).action_toggle_favorite()
        theirs.with_user(self.other).action_toggle_favorite()
        found = self.env['knowledge.article'].with_user(self.author).search(
            [('is_favorite', '=', True)])
        self.assertEqual(found, mine)

    # --- revision history

    def test_body_revisions_are_kept(self):
        """The page promises content is never lost; body is collaborative and
        unsanitised, so past revisions have to survive a bad edit."""
        article = self._article(name='A', body='<p>bản đầu</p>')
        self.assertIn('body', article._get_versioned_fields())
        article.body = '<p>bản sau</p>'
        self.assertTrue(article.html_field_history, "a revision must have been recorded")
        self.assertIn('body', article.html_field_history)

    def test_article_body_is_sanitised(self):
        """An article is written by one employee and read by every other: script
        injected here would run in all their browsers."""
        article = self._article(name='XSS', body='<p>hi</p><script>alert(1)</script>')
        self.assertNotIn('<script>', article.body or '')
