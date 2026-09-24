from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Startup, UserProfile


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
        self.profile = UserProfile.objects.create(user=self.user, user_type='public')
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
        self.assertEqual(response.url, reverse('staff:startup_create'))

        profile = UserProfile.objects.get(user__username='newuser')
        self.assertEqual(profile.user_type, 'public')
        self.assertIsNone(profile.startup)

    def test_register_cannot_grant_admin_rights(self):
        self.client.logout()
        self.client.post(reverse('staff:register'), {
            'username': 'sneaky',
            'email': 's@example.com',
            'password': 'verysecret123',
            'user_type': 'admin',
        })
        profile = UserProfile.objects.get(user__username='sneaky')
        self.assertEqual(profile.user_type, 'public')

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
        UserProfile.objects.create(user=staff_user, user_type='staff')

        response = self.client.post(reverse('staff:user_login'), {
            'username': 'staffuser',
            'password': 'secret1234',
            'user_type': 'staff',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:staff_list'))

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
        self.assertEqual(startup.status, 'pending')
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
        UserProfile.objects.create(user=john, user_type='public')
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
        UserProfile.objects.create(user=stranger, user_type='public')
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
        self.profile = UserProfile.objects.create(user=self.user, user_type='public')

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
