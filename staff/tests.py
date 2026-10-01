from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Investor, Mentor, Startup, UserProfile


def startup_payload(name='AgriTech Solutions', founders=1):
    """Build a valid POST payload for the startup creation form."""
    data = {
        'name': name,
        'startup_type': 'public',
        'description': 'Helping smallholder farmers get to market.',
        'industry': 'Agriculture',
        'website': 'https://example.com',
        'founded_date': '2024-01-15',
        'year_incubated': '2024',
        'contract_status': 'draft',
        # Opportunities
        'opportunities-TOTAL_FORMS': '1',
        'opportunities-INITIAL_FORMS': '0',
        'opportunities-MIN_NUM_FORMS': '0',
        'opportunities-MAX_NUM_FORMS': '1000',
        'opportunities-0-title': 'Seed funding',
        'opportunities-0-description': '',
        'opportunities-0-opportunity_type': 'funding',
        'opportunities-0-status': 'open',
        'opportunities-0-deadline': '',
        # Fundings
        'fundings-TOTAL_FORMS': '1',
        'fundings-INITIAL_FORMS': '0',
        'fundings-MIN_NUM_FORMS': '0',
        'fundings-MAX_NUM_FORMS': '1000',
        'fundings-0-source': '',
        'fundings-0-amount': '',
        'fundings-0-currency': 'USD',
        'fundings-0-funding_type': 'seed',
        'fundings-0-date_received': '',
        'fundings-0-status': 'committed',
        'fundings-0-notes': '',
        # KPIs
        'kpis-TOTAL_FORMS': '1',
        'kpis-INITIAL_FORMS': '0',
        'kpis-MIN_NUM_FORMS': '0',
        'kpis-MAX_NUM_FORMS': '1000',
        'kpis-0-metric_name': '',
        'kpis-0-metric_value': '',
        'kpis-0-target_value': '',
        'kpis-0-period': 'monthly',
        'kpis-0-unit': '',
        # Pitch decks
        'pitches-TOTAL_FORMS': '1',
        'pitches-INITIAL_FORMS': '0',
        'pitches-MIN_NUM_FORMS': '0',
        'pitches-MAX_NUM_FORMS': '1000',
        'pitches-0-title': '',
        'pitches-0-description': '',
        'pitches-0-presentation_date': '',
        # Services
        'services-TOTAL_FORMS': '1',
        'services-INITIAL_FORMS': '0',
        'services-MIN_NUM_FORMS': '0',
        'services-MAX_NUM_FORMS': '1000',
        'services-0-name': '',
        'services-0-description': '',
        'services-0-category': 'other',
    }

    # Founders — at least one is required
    data.update({
        'founders-TOTAL_FORMS': str(founders),
        'founders-INITIAL_FORMS': '0',
        'founders-MIN_NUM_FORMS': '0',
        'founders-MAX_NUM_FORMS': '1000',
    })
    for i in range(founders):
        data.update({
            f'founders-{i}-name': f'Founder {i + 1}',
            f'founders-{i}-email': f'founder{i + 1}@example.com',
            f'founders-{i}-phone': '',
            f'founders-{i}-role': 'founder',
            f'founders-{i}-bio': '',
            f'founders-{i}-linkedin': '',
            f'founders-{i}-twitter': '',
        })
    return data


class StartupCreationTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='jane', password='secret1234', email='jane@example.com'
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user, defaults={'user_type': 'public'})
        self.profile.user_type = 'public'
        self.profile.save(update_fields=['user_type'])
        self.client.force_login(self.user)

    def test_anonymous_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('staff:startup_create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('staff:user_login'), response.url)

    def test_register_creates_account_and_opens_creation_form(self):
        self.client.logout()
        response = self.client.post(reverse('staff:register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'verysecret123',
            'user_type': 'public',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:user_login'))

        profile = UserProfile.objects.get(user__username='newuser')
        self.assertEqual(profile.user_type, 'public')
        self.assertIsNone(profile.startup)

    def test_register_cannot_grant_admin_rights(self):
        self.client.logout()
        response = self.client.post(reverse('staff:register'), {
            'username': 'sneaky',
            'email': 's@example.com',
            'password': 'verysecret123',
            'user_type': 'admin',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='sneaky').exists())
        self.assertFalse(UserProfile.objects.filter(user__username='sneaky').exists())

    def test_self_registration_redirects_to_login_and_does_not_auto_login(self):
        self.client.logout()
        response = self.client.post(reverse('staff:register'), {
            'username': 'startupuser',
            'email': 'startup@example.com',
            'password': 'verysecret123',
            'user_type': 'public',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:user_login'))
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_staff_login_redirects_to_staff_page(self):
        staff_user = get_user_model().objects.create_user(
            username='staffuser',
            password='secret1234',
            email='staff@example.com',
            is_staff=True,
        )
        staff_profile, _ = UserProfile.objects.get_or_create(user=staff_user, defaults={'user_type': 'staff'})
        staff_profile.user_type = 'staff'
        staff_profile.save(update_fields=['user_type'])

        response = self.client.post(reverse('staff:user_login'), {
            'username': 'staffuser',
            'password': 'secret1234',
            'user_type': 'staff',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:staff_home'))

    def test_register_rejects_duplicate_username(self):
        self.client.logout()
        response = self.client.post(reverse('staff:register'), {
            'username': 'jane',
            'email': 'jane@example.com',
            'password': 'whatever1234',
            'user_type': 'public',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            UserProfile.objects.filter(user__username='jane').count(), 1
        )

    def test_logged_in_user_creates_their_own_startup(self):
        response = self.client.post(reverse('staff:startup_create'), startup_payload())
        self.assertEqual(response.status_code, 302)

        startup = Startup.objects.get(name='AgriTech Solutions')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.startup, startup)
        self.assertEqual(startup.status, 'active')
        self.assertEqual(startup.contract_status, 'draft')
        self.assertEqual(startup.founders.count(), 1)
        self.assertEqual(response.url, reverse('staff:startup_profile', kwargs={'slug': startup.slug}))

        # The owner lands on their own profile
        page = self.client.get(response.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'AgriTech Solutions')

    def test_form_errors_are_shown_when_founder_is_missing(self):
        payload = startup_payload()
        payload['founders-0-name'] = ''
        payload['founders-0-email'] = ''
        response = self.client.post(reverse('staff:startup_create'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'error-list')
        self.assertFalse(Startup.objects.exists())

    def test_user_only_gets_one_startup(self):
        self.client.post(reverse('staff:startup_create'), startup_payload('First Startup'))
        second = self.client.post(reverse('staff:startup_create'), startup_payload('Second Startup'))
        self.assertEqual(second.status_code, 302)
        self.assertEqual(second.url, reverse('staff:startup_profile', kwargs={'slug': 'first-startup'}))
        self.assertEqual(Startup.objects.count(), 1)

    def test_duplicate_names_get_unique_slugs(self):
        self.client.post(reverse('staff:startup_create'), startup_payload('Same Name'))
        john = get_user_model().objects.create_user(username='john', password='secret1234')
        john_profile, _ = UserProfile.objects.get_or_create(user=john, defaults={'user_type': 'public'})
        john_profile.user_type = 'public'
        john_profile.save(update_fields=['user_type'])
        self.client.force_login(john)

        self.client.post(reverse('staff:startup_create'), startup_payload('Same Name'))
        slugs = list(Startup.objects.values_list('slug', flat=True))
        self.assertEqual(len(slugs), 2)
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertIn('same-name', slugs)
        self.assertIn('same-name-2', slugs)

    def test_owner_can_edit_but_strangers_cannot(self):
        self.client.post(reverse('staff:startup_create'), startup_payload())
        startup = Startup.objects.get(name='AgriTech Solutions')

        # Owner may edit
        payload = startup_payload('AgriTech Solutions')
        payload['founders-INITIAL_FORMS'] = '1'
        payload['founders-0-id'] = str(startup.founders.first().pk)
        payload['description'] = 'Updated by the owner.'
        owner_post = self.client.post(
            reverse('staff:startup_profile', kwargs={'slug': startup.slug}), payload
        )
        self.assertEqual(owner_post.status_code, 302)
        startup.refresh_from_db()
        self.assertEqual(startup.description, 'Updated by the owner.')

        # A stranger may view but not edit
        stranger = get_user_model().objects.create_user(
            username='stranger', password='secret1234'
        )
        stranger_profile, _ = UserProfile.objects.get_or_create(user=stranger, defaults={'user_type': 'public'})
        stranger_profile.user_type = 'public'
        stranger_profile.save(update_fields=['user_type'])
        self.client.force_login(stranger)

        view = self.client.get(reverse('staff:startup_profile', kwargs={'slug': startup.slug}))
        self.assertEqual(view.status_code, 200)
        self.assertNotContains(view, 'name="description"', status_code=200)

        payload['description'] = 'Hijacked by a stranger.'
        edit = self.client.post(reverse('staff:startup_profile', kwargs={'slug': startup.slug}), payload)
        self.assertEqual(edit.status_code, 302)
        startup.refresh_from_db()
        self.assertEqual(startup.description, 'Updated by the owner.')

class PageRenderingTests(TestCase):
    """Guard the templates involved in the sign-up -> add startup journey."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='render', password='secret1234'
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user, defaults={'user_type': 'public'})
        self.profile.user_type = 'public'
        self.profile.save(update_fields=['user_type'])

    def test_landing_page_is_public(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Get Started')
        # Signed-out visitors get sign-in buttons in the sidebar
        self.assertContains(response, 'Create account')

    def test_register_and_login_pages_render(self):
        self.assertEqual(self.client.get(reverse('staff:register')).status_code, 200)
        self.assertEqual(self.client.get(reverse('staff:user_login')).status_code, 200)

    def test_dashboard_offers_to_add_a_startup(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('staff:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('staff:startup_create'))
        self.assertContains(response, 'Add My Startup')
        self.assertContains(response, 'Add Startup')  # sidebar link

    def test_create_form_renders_all_sections(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('staff:startup_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Your Startup')
        self.assertContains(response, 'Add My Startup')      # submit button
        self.assertContains(response, 'Add another founder')  # dynamic rows
        self.assertContains(response, 'name="founders-TOTAL_FORMS"')
        self.assertContains(response, 'name="contract_status"')
        self.assertContains(response, 'name="year_incubated"')
        self.assertNotContains(response, 'name="status"')
        # The first founder is pre-filled with the account owner
        self.assertContains(response, self.user.username)

    def test_startups_list_renders_with_add_button(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('staff:startups'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('staff:startup_create'))

    def test_sidebar_shows_the_signed_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('staff:dashboard'))
        self.assertContains(response, self.user.username)
        self.assertContains(response, reverse('staff:user_logout'))

    def test_anonymous_visitor_cannot_open_a_profile(self):
        startup = Startup.objects.create(name='Open Startup')
        self.client.logout()
        response = self.client.get(reverse('staff:startup_profile', kwargs={'slug': startup.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('staff:user_login'), response.url)


class StaffLandingPageTests(TestCase):

    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username='staffland', password='secret1234', email='staffland@example.com', is_staff=True,
        )
        self.staff_profile, _ = UserProfile.objects.get_or_create(user=self.staff_user)
        self.staff_profile.user_type = 'staff'
        self.staff_profile.save(update_fields=['user_type'])
        self.member = get_user_model().objects.create_user(
            username='plainmember', password='secret1234', email='plain@example.com',
        )
        self.member_profile, _ = UserProfile.objects.get_or_create(user=self.member)
        self.member_profile.user_type = 'public'
        self.member_profile.save(update_fields=['user_type'])

    def test_staff_home_renders_for_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('staff:staff_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff Home')
        self.assertContains(response, 'Pending applications')

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse('staff:staff_home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('staff:user_login'), response.url)

    def test_ordinary_member_cannot_open_staff_home(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('staff:staff_home'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:dashboard'))

    def test_sidebar_offers_staff_home_to_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('staff:dashboard'))
        self.assertContains(response, reverse('staff:staff_home'))


class StaffStartupControlTests(TestCase):

    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username='staffctl', password='secret1234', email='staffctl@example.com', is_staff=True,
        )
        self.staff_profile, _ = UserProfile.objects.get_or_create(user=self.staff_user)
        self.staff_profile.user_type = 'staff'
        self.staff_profile.save(update_fields=['user_type'])
        self.pending = Startup.objects.create(name='Pending Startup', status='pending', directory_visible=False)
        self.client.force_login(self.staff_user)

    def test_staff_can_open_account_management(self):
        response = self.client.get(reverse('staff:account_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Startup accounts')

    def test_staff_account_management_hides_staff_section(self):
        response = self.client.get(reverse('staff:account_management'))
        self.assertNotContains(response, 'Staff accounts')
        self.assertNotContains(response, reverse('staff:account_add', kwargs={'kind': 'staff'}))

    def test_staff_can_approve_a_startup(self):
        response = self.client.post(
            reverse('staff:startup_decision', kwargs={'pk': self.pending.pk, 'decision': 'approve'}),
        )
        self.assertEqual(response.status_code, 302)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'active')
        self.assertTrue(self.pending.directory_visible)

    def test_staff_can_delete_a_startup(self):
        response = self.client.post(
            reverse('staff:account_delete', kwargs={'kind': 'startup', 'pk': self.pending.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Startup.objects.filter(pk=self.pending.pk).exists())

    def test_staff_cannot_create_staff_accounts(self):
        response = self.client.get(reverse('staff:account_add', kwargs={'kind': 'staff'}))
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_create_mentor_accounts(self):
        response = self.client.get(reverse('staff:account_add', kwargs={'kind': 'mentor'}))
        self.assertEqual(response.status_code, 403)

    def test_admin_still_manages_staff_accounts(self):
        admin_user = get_user_model().objects.create_superuser(
            username='qaadmin', password='secret1234', email='qaadmin@example.com',
        )
        admin_profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        admin_profile.user_type = 'admin'
        admin_profile.save(update_fields=['user_type'])
        self.client.force_login(admin_user)
        response = self.client.get(reverse('staff:account_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff accounts')
        self.assertContains(response, reverse('staff:account_add', kwargs={'kind': 'staff'}))
        self.assertContains(response, reverse('staff:account_add', kwargs={'kind': 'mentor'}))

    def test_ordinary_member_is_denied_account_management(self):
        member = get_user_model().objects.create_user(username='nomember', password='secret1234')
        profile, _ = UserProfile.objects.get_or_create(user=member)
        profile.user_type = 'public'
        profile.save(update_fields=['user_type'])
        self.client.force_login(member)
        response = self.client.get(reverse('staff:account_management'))
        self.assertEqual(response.status_code, 403)


class PublicReportCsvTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        Startup.objects.create(name='Visible Startup', status='active', directory_visible=True, industry='Fintech')
        Startup.objects.create(name='Hidden Startup', status='pending', directory_visible=False)
        Startup.objects.create(name='Inactive Startup', status='inactive', directory_visible=True)
        Mentor.objects.create(name='Active Mentor', is_active=True, role='Product')
        Mentor.objects.create(name='Retired Mentor', is_active=False)
        Investor.objects.create(name='Active Investor', status='active', organization='Acme')
        Investor.objects.create(name='Paused Investor', status='paused')

    def _get(self, kind):
        return self.client.get(reverse('public_report', kwargs={'kind': kind}))

    def test_anonymous_startup_report_downloads(self):
        response = self._get('startups')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="startup_directory.csv"')
        body = response.content.decode('utf-8-sig')
        self.assertTrue(body.startswith('"Name","Type","Industry"'), body[:80])
        self.assertIn('"Visible Startup"', body)
        self.assertNotIn('Hidden Startup', body)
        self.assertNotIn('Inactive Startup', body)

    def test_every_csv_row_is_a_single_quoted_line(self):
        response = self._get('mentors')
        body = response.content.decode('utf-8-sig')
        lines = body.splitlines()
        self.assertEqual(len(lines), Mentor.objects.filter(is_active=True).count() + 1)
        for line in lines:
            self.assertTrue(line.startswith('"') and line.endswith('"'), line[:60])
            self.assertNotIn('\\n', line)

    def test_anonymous_mentor_report_downloads(self):
        response = self._get('mentors')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Active Mentor', body)
        self.assertNotIn('Retired Mentor', body)

    def test_anonymous_investor_report_downloads(self):
        response = self._get('investors')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Active Investor', body)
        self.assertNotIn('Paused Investor', body)

    def test_anonymous_pdf_report_downloads(self):
        response = self.client.get(reverse('public_report_pdf', kwargs={'kind': 'startups'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="startup_directory.pdf"')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 1000)

    def test_pdf_report_rejects_unknown_kind_and_post(self):
        self.assertEqual(
            self.client.get(reverse('public_report_pdf', kwargs={'kind': 'passwords'})).status_code, 404,
        )
        self.assertEqual(
            self.client.post(reverse('public_report_pdf', kwargs={'kind': 'mentors'})).status_code, 405,
        )

    def test_unknown_report_kind_is_not_found(self):
        response = self._get('passwords')
        self.assertEqual(response.status_code, 404)

    def test_report_endpoint_rejects_post(self):
        response = self.client.post(reverse('public_report', kwargs={'kind': 'startups'}))
        self.assertEqual(response.status_code, 405)


class StaffManagementTests(TestCase):

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='superq', password='secret1234', email='superq@example.com',
        )
        admin_profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        admin_profile.user_type = 'admin'
        admin_profile.save(update_fields=['user_type'])
        self.staff_user = get_user_model().objects.create_user(
            username='actstaff', password='secret1234', email='actstaff@example.com', is_staff=True,
        )
        staff_profile, _ = UserProfile.objects.get_or_create(user=self.staff_user)
        staff_profile.user_type = 'staff'
        staff_profile.save(update_fields=['user_type'])

    def test_admin_opens_staff_management(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('staff:staff_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff management')
        self.assertContains(response, 'Activity monitoring')
        self.assertContains(response, 'actstaff')

    def test_staff_member_is_denied_staff_management(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('staff:staff_management'))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse('staff:staff_management'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('staff:user_login'), response.url)

    def test_admin_can_disable_and_reenable_staff(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('staff:staff_toggle', kwargs={'pk': self.staff_user.pk}))
        self.assertEqual(response.status_code, 302)
        self.staff_user.refresh_from_db()
        self.assertFalse(self.staff_user.is_active)
        response = self.client.post(reverse('staff:staff_toggle', kwargs={'pk': self.staff_user.pk}))
        self.assertEqual(response.status_code, 302)
        self.staff_user.refresh_from_db()
        self.assertTrue(self.staff_user.is_active)

    def test_staff_member_cannot_toggle_accounts(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse('staff:staff_toggle', kwargs={'pk': self.admin.pk}))
        self.assertEqual(response.status_code, 403)

    def test_sidebar_offers_staff_management_to_admin_only(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('staff:dashboard'))
        self.assertContains(response, reverse('staff:staff_management'))
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('staff:dashboard'))
        self.assertNotContains(response, reverse('staff:staff_management'))


class StatisticsPageTests(TestCase):

    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username='statstaff', password='secret1234', email='statstaff@example.com', is_staff=True,
        )
        staff_profile, _ = UserProfile.objects.get_or_create(user=self.staff_user)
        staff_profile.user_type = 'staff'
        staff_profile.save(update_fields=['user_type'])
        self.member = get_user_model().objects.create_user(
            username='statmember', password='secret1234', email='statmember@example.com',
        )
        member_profile, _ = UserProfile.objects.get_or_create(user=self.member)
        member_profile.user_type = 'public'
        member_profile.save(update_fields=['user_type'])

    def test_statistics_page_renders_for_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('staff:statistics'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Programme statistics')
        self.assertContains(response, 'chart-industry')
        self.assertContains(response, 'chart-status')
        self.assertContains(response, 'chart-monthly')
        self.assertContains(response, 'chart-partnerships')
        self.assertContains(response, 'stats-payload')

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse('staff:statistics'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('staff:user_login'), response.url)

    def test_ordinary_member_is_denied(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('staff:statistics'))
        self.assertEqual(response.status_code, 403)

    def test_post_request_is_rejected(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse('staff:statistics'))
        self.assertEqual(response.status_code, 405)

    def test_data_endpoint_returns_counts(self):
        Startup.objects.create(name='Stats Startup One', industry='Agriculture')
        Startup.objects.create(name='Stats Startup Two', industry='agriculture')
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('staff:statistics_data'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ('generated_at', 'signature', 'cards', 'industry', 'status', 'monthly', 'partnerships',
                    'entity_rows', 'monthly_rows', 'industry_rows'):
            self.assertIn(key, payload)
        startup_row = next(row for row in payload['entity_rows'] if row['entity'] == 'Startups')
        self.assertEqual(startup_row['total'], 2)
        self.assertEqual(payload['monthly']['startups'][-1], 2)
        self.assertEqual(payload['monthly_rows'][0]['startups'], 2)
        self.assertEqual(len(payload['monthly']['labels']), 12)

    def test_blank_industry_merges_into_unspecified(self):
        Startup.objects.create(name='No Industry Startup')
        self.client.force_login(self.staff_user)
        payload = self.client.get(reverse('staff:statistics_data')).json()
        labels = [row['industry'] for row in payload['industry_rows']]
        self.assertIn('Unspecified', labels)

    def test_new_records_change_signature_and_counts(self):
        self.client.force_login(self.staff_user)
        url = reverse('staff:statistics_data')
        before = self.client.get(url).json()
        Startup.objects.create(name='Late Arrival', industry='Fintech')
        after = self.client.get(url).json()
        self.assertNotEqual(before['signature'], after['signature'])
        startup_before = next(r for r in before['entity_rows'] if r['entity'] == 'Startups')['total']
        startup_after = next(r for r in after['entity_rows'] if r['entity'] == 'Startups')['total']
        self.assertEqual(startup_after, startup_before + 1)

    def test_sidebar_offers_statistics_to_staff_only(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('staff:dashboard'))
        self.assertContains(response, reverse('staff:statistics'))
        self.client.force_login(self.member)
        response = self.client.get(reverse('staff:dashboard'))
        self.assertNotContains(response, reverse('staff:statistics'))


class ModelStringTests(TestCase):
    """`str()` on models must terminate — admin delete confirmation reprs them."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='strcheck', password='secret1234', email='strcheck@example.com',
        )

    def test_userprofile_str_does_not_recurse(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.user_type = 'public'
        profile.save(update_fields=['user_type'])
        text = str(profile)
        self.assertIn('strcheck', text)
        self.assertEqual(text, 'strcheck (Public Startup)')
        self.assertNotIn('bound method', text)
        self.assertTrue(repr(profile).startswith('<UserProfile:'))

    def test_registration_rate_str_does_not_recurse(self):
        from .models import RegistrationRate
        rate = RegistrationRate(date_range='today', total_registrations=7)
        self.assertEqual(str(rate), 'Today: 7 registrations')

    def test_startup_admin_delete_confirmation_renders(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        from .admin import StartupAdmin
        from .models import Startup
        admin_user = get_user_model().objects.create_superuser(
            username='delconf', password='secret1234', email='delconf@example.com',
        )
        startup = Startup.objects.create(name='Deletion Probe')
        request = RequestFactory().post(
            '/admin/staff/startup/',
            {'action': 'delete_selected', '_selected_action': str(startup.pk), 'index': '0'},
        )
        request.user = admin_user
        request._dont_enforce_csrf_checks = True
        response = StartupAdmin(Startup, site).changelist_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Deletion Probe', response.rendered_content if hasattr(response, 'rendered_content') else response.content.decode())


class SectorFilterTests(TestCase):
    """Sector keywords must not match inside another word (edtech vs MedTech)."""

    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username='sectorstaff', password='secret1234', email='sectorstaff@example.com', is_staff=True,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.staff_user)
        profile.user_type = 'staff'
        profile.save(update_fields=['user_type'])
        self.client.force_login(self.staff_user)
        Startup.objects.create(name='EdTech One', industry='EdTech', status='active')
        Startup.objects.create(name='EdTech Two', industry='EdTech', status='active')
        Startup.objects.create(name='MedTech One', industry='Health & MedTech', status='active')
        Startup.objects.create(name='AgriTech One', industry='Agritech', status='active')
        Startup.objects.create(name='Fin One', industry='Fintech & E-commerce', status='active')

    def _count(self, sector):
        response = self.client.get(reverse('staff:startups'), {'industry': f'sector:{sector}'})
        return response.context['startup_list'].paginator.count

    def test_education_sector_does_not_capture_medtech(self):
        self.assertEqual(self._count('education'), 2)

    def test_health_sector_still_matches_health_industries(self):
        self.assertEqual(self._count('health'), 1)

    def test_prefix_keywords_still_match(self):
        self.assertEqual(self._count('agriculture'), 1)
        self.assertEqual(self._count('finance'), 1)

    def test_sector_words_match_inside_labeled_industry(self):
        Startup.objects.create(name='Solar One', industry='Renewable Energy', status='active')
        self.assertEqual(self._count('energy'), 1)


class YcDirectoryPageTests(TestCase):
    """The YC-style startups directory keeps its functional contract."""

    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username='ycstaff', password='secret1234', email='ycstaff@example.com', is_staff=True,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.staff_user)
        profile.user_type = 'staff'
        profile.save(update_fields=['user_type'])
        self.client.force_login(self.staff_user)
        self.s1 = Startup.objects.create(name='Solar One', industry='Renewable Energy', status='active')
        self.s2 = Startup.objects.create(name='PayFlow Limited', industry='Fintech & E-commerce', status='active')
        Startup.objects.create(name='Hidden Venture', industry='Fintech & E-commerce', status='inactive')

    def test_page_renders_yc_shell(self):
        response = self.client.get(reverse('staff:startups'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="yc-page"')
        self.assertContains(response, 'style/startups-yc.css')
        self.assertContains(response, 'id="ycRail"')
        self.assertContains(response, 'class="yc-grid"')

    def test_showcase_context_lists_featured_startups(self):
        response = self.client.get(reverse('staff:startups'))
        showcase = response.context['showcase']
        self.assertEqual(len(showcase), 2)
        for startup in showcase:
            self.assertContains(
                response, reverse('staff:startup_profile', kwargs={'slug': startup.slug})
            )

    def test_filter_form_contract_preserved(self):
        response = self.client.get(reverse('staff:startups'), {'q': 'Pay', 'status': 'active'})
        self.assertContains(response, 'id="startupFilters"')
        self.assertContains(response, 'id="startupSearch"')
        self.assertContains(response, 'name="q" value="Pay"')
        self.assertContains(response, 'name="industry"')
        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'name="type"')

    def test_report_and_add_links_present(self):
        response = self.client.get(reverse('staff:startups'))
        self.assertContains(response, reverse('staff:startup_create'))
        self.assertContains(response, reverse('public_report', kwargs={'kind': 'startups'}))
        self.assertContains(response, reverse('public_report_pdf', kwargs={'kind': 'startups'}))

    def test_admin_sees_manage_link(self):
        # Admins are superusers: the sync_user_profile_role signal keeps
        # non-superusers on 'staff', and every login re-runs that signal.
        admin = get_user_model().objects.create_superuser(
            username='ycadmin', password='secret1234', email='ycadmin@example.com',
        )
        self.client.force_login(admin)
        response = self.client.get(reverse('staff:startups'))
        self.assertContains(response, reverse('admin:staff_startup_changelist'))

    def test_grid_links_every_visible_startup(self):
        response = self.client.get(reverse('staff:startups'))
        self.assertContains(response, reverse('staff:startup_profile', kwargs={'slug': self.s1.slug}))
        self.assertContains(response, reverse('staff:startup_profile', kwargs={'slug': self.s2.slug}))
        # Inactive startups stay hidden from non-admin visitors
        self.assertNotContains(response, 'Hidden Venture')

    def test_empty_state_renders_without_showcase(self):
        Startup.objects.all().delete()
        response = self.client.get(reverse('staff:startups'))
        self.assertContains(response, 'No startups yet')
        self.assertContains(response, 'yc-empty')
        self.assertEqual(response.context['showcase'], [])
        self.assertNotContains(response, 'id="ycRail"')
