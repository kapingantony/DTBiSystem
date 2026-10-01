from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from staff.models import Funding, Investor, Mentor, MentorEngagement, UserProfile


LEGACY_SOURCE = 'BUNI HUB INNOVATORS APPLICATIONS.xlsx'
DEMO_SOURCE = 'DEMO ONLY - fictional sample profile'

MENTOR_SAMPLES = [
    ('Sample Mentor 01', 'Product and venture strategy', 'Customer discovery, product roadmaps, and early-stage business models', 'MVP validation; product planning; founder coaching'),
    ('Sample Mentor 02', 'Software and digital systems', 'Software architecture, cloud platforms, and secure product development', 'Technical planning; software quality; scaling digital services'),
    ('Sample Mentor 03', 'Finance and investment readiness', 'Financial planning, grant readiness, and investment preparation', 'Business finances; investor preparation; pitch development'),
    ('Sample Mentor 04', 'Market access and growth', 'Sales strategy, partnerships, marketing, and customer acquisition', 'Market research; B2B sales; partnership development'),
    ('Sample Mentor 05', 'Agriculture and climate innovation', 'Agritech, food systems, climate adaptation, and inclusive design', 'Agribusiness models; climate solutions; impact measurement'),
]

INVESTOR_SAMPLES = [
    ('Sample Investor 01', 'Illustrative Capital One', 'Climate technology and clean energy', 'Fictional example only. No real fund, person, commitment, or contact details.'),
    ('Sample Investor 02', 'Illustrative Capital Two', 'Agriculture, food systems, and agritech', 'Fictional example only. No real fund, person, commitment, or contact details.'),
    ('Sample Investor 03', 'Illustrative Capital Three', 'Health, education, and inclusive technology', 'Fictional example only. No real fund, person, commitment, or contact details.'),
    ('Sample Investor 04', 'Illustrative Capital Four', 'Fintech and financial inclusion', 'Fictional example only. No real fund, person, commitment, or contact details.'),
    ('Sample Investor 05', 'Illustrative Capital Five', 'Early stage enterprise and digital services', 'Fictional example only. No real fund, person, commitment, or contact details.'),
]


class Command(BaseCommand):
    help = 'Replace imported mentor/investor directory entries with five clearly marked demo profiles per directory.'

    @transaction.atomic
    def handle(self, *args, **options):
        mentors = Mentor.objects.filter(source=LEGACY_SOURCE)
        investors = Investor.objects.filter(source=LEGACY_SOURCE)
        demo_mentors = Mentor.objects.filter(source=DEMO_SOURCE)
        demo_investors = Investor.objects.filter(source=DEMO_SOURCE)
        all_old_mentors = mentors | demo_mentors
        all_old_investors = investors | demo_investors
        old_mentor_count = all_old_mentors.count()
        old_investor_count = all_old_investors.count()

        if MentorEngagement.objects.filter(mentor__in=all_old_mentors).exists():
            raise CommandError('A mentor being replaced has session history. Preserve those records and review the roster before replacement.')
        if Funding.objects.filter(investor__in=all_old_investors).exists():
            raise CommandError('An investor being replaced is linked to funding. Preserve those records and review the roster before replacement.')

        user_ids = list(UserProfile.objects.filter(
            user_type__in=('mentor', 'investor'),
            user__is_staff=False,
            user__is_superuser=False,
            user__mentor_record__in=all_old_mentors,
        ).values_list('user_id', flat=True))
        investor_user_ids = list(UserProfile.objects.filter(
            user_type='investor',
            user__is_staff=False,
            user__is_superuser=False,
            user__investor_record__in=all_old_investors,
        ).values_list('user_id', flat=True))
        user_ids = set(user_ids + investor_user_ids)

        User = get_user_model()
        deleted_account_count = User.objects.filter(pk__in=user_ids).count()
        all_old_mentors.delete()
        all_old_investors.delete()
        deleted_users, _ = User.objects.filter(pk__in=user_ids).delete()

        for name, role, skills, topics in MENTOR_SAMPLES:
            Mentor.objects.create(
                name=name, role=role, skills=f'{skills}. Fictional demonstration profile.',
                training_topics=topics, education_level='Sample profile',
                is_active=True, source=DEMO_SOURCE,
            )
        for name, organization, focus, description in INVESTOR_SAMPLES:
            Investor.objects.create(
                name=name, organization=organization, investment_interest=focus,
                description=description, status='active', source=DEMO_SOURCE,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Replaced {old_mentor_count} old mentor records and {old_investor_count} old investor records '
            f'with {len(MENTOR_SAMPLES)} fictional mentors and {len(INVESTOR_SAMPLES)} fictional investors. '
            f'Removed {deleted_account_count} linked imported accounts ({deleted_users} total database rows including related profiles).'
        ))
