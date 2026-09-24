"""Optional AI summaries for aggregate programme report data."""
import json
import logging
import os
import hashlib
from decimal import Decimal
from urllib.request import Request, urlopen

from django.utils.html import strip_tags
from django.core.cache import cache

logger = logging.getLogger(__name__)

def _fallback_summary(data):
    current = sum(row['total'] for row in data['startups_by_status'])
    funding = ', '.join(f'{currency} {amount:,.2f}' for currency, amount in sorted(data['funding_totals'].items()))
    if not funding:
        funding = 'no funding recorded in the selected period'
    outcome_changes = data['participant_outcome_changes']
    revenue_change = ', '.join(
        f'{currency} {amount:,.2f}' for currency, amount in sorted(outcome_changes['revenue_by_currency'].items())
    ) or 'no comparable revenue change available'
    return (
        f"From {data['start_date']} to {data['end_date']}, {data['new_startups']} startups were added "
        f"(versus {data['previous_startups']} in the preceding equal-length period), and {current} startups "
        f"are currently recorded. The system recorded {data['mentor_sessions']} mentor sessions "
        f"({data['mentor_hours']:,.1f} hours), {data['new_mentors']} new mentors, and "
        f"{data['new_investors']} new investors. Funding recorded: {funding}. "
        f"There were {data['new_partnerships']} new partnership requests, with "
        f"{data['active_partnership_pipeline']} requests in the active pipeline and "
        f"{data['completed_partnerships']} completed during the period. "
        f"{data['scheduled_mentor_sessions']} mentor sessions are currently arranged for the selected dates. "
        f"{data['cancelled_mentor_sessions']} sessions were cancelled or marked no-show in the period. "
        f"There are {data['participant_journeys_current']} participant journeys currently tracked, "
        f"with {len(data['participant_journey_changes'])} stage or status changes and "
        f"{data['participant_support_total']} additional support records in the selected period. "
        f"{data['participant_followups_completed']} follow-up actions were completed and "
        f"{data['participant_followups_due']} remain open and due in that period. "
        f"Outcome comparisons are available for {data['participant_outcome_comparisons']} participants "
        f"with snapshots both before and during the period: net job change was "
        f"{outcome_changes['full_time_jobs']} full-time and {outcome_changes['part_time_jobs']} part-time, "
        f"and monthly revenue change was {revenue_change}. "
        f"Tracked unique daily entity visits: {data['page_visit_total']}."
    )


def summarize_report(data):
    """Use a configured OpenAI-compatible endpoint; safely fall back to local counts."""
    fallback = _fallback_summary(data)
    api_key = os.environ.get('DTBI_AI_API_KEY', '').strip()
    if not api_key:
        return {'text': fallback, 'source': 'Rule based summary', 'ai_enabled': False}

    base_url = os.environ.get('DTBI_AI_BASE_URL', 'https://api.openai.com/v1').strip().rstrip('/')
    if base_url.endswith('/chat/completions'):
        endpoint = base_url
    elif base_url.endswith('/v1'):
        endpoint = base_url + '/chat/completions'
    else:
        endpoint = base_url + '/v1/chat/completions'
    model = os.environ.get('DTBI_AI_MODEL', 'gpt-4o-mini').strip()
    metrics = {
        'period': f"{data['start_date']} to {data['end_date']}",
        'new_startups': data['new_startups'],
        'previous_equal_period_startups': data['previous_startups'],
        'current_startups_by_status': {str(row['status']): row['total'] for row in data['startups_by_status']},
        'new_mentors': data['new_mentors'],
        'new_investors': data['new_investors'],
        'mentor_sessions': data['mentor_sessions'],
        'mentor_hours': float(data['mentor_hours']),
        'funding_by_currency': {currency: float(amount) if isinstance(amount, Decimal) else amount
                                for currency, amount in data['funding_totals'].items()},
        'kpi_observations': data['kpi_observations'],
        'unique_daily_entity_visits': data['page_visit_total'],
        'new_partnership_requests': data['new_partnerships'],
        'active_partnership_pipeline': data['active_partnership_pipeline'],
        'completed_partnerships_in_period': data['completed_partnerships'],
        'current_partnership_status_counts': {row['status']: row['total'] for row in data['partnership_statuses']},
        'scheduled_mentor_sessions_in_period': data['scheduled_mentor_sessions'],
        'session_cancellations_or_no_shows_in_period': data['cancelled_mentor_sessions'],
        'participant_journeys_currently_tracked': data['participant_journeys_current'],
        'participant_stage_or_status_changes_in_period': len(data['participant_journey_changes']),
        'additional_support_records_in_period': data['participant_support_total'],
        'open_followups_due_in_period': data['participant_followups_due'],
        'followups_completed_in_period': data['participant_followups_completed'],
        'participants_with_comparable_outcome_snapshots': data['participant_outcome_comparisons'],
        'change_in_full_time_jobs_for_comparable_participants': data['participant_outcome_changes']['full_time_jobs'],
        'change_in_part_time_jobs_for_comparable_participants': data['participant_outcome_changes']['part_time_jobs'],
        'change_in_customers_or_users_for_comparable_participants': data['participant_outcome_changes']['customers_or_users'],
        'monthly_revenue_change_by_currency_for_comparable_participants': {
            currency: float(amount) for currency, amount in data['participant_outcome_changes']['revenue_by_currency'].items()
        },
    }
    cache_key = 'report-ai-summary:' + hashlib.sha256(
        json.dumps({'metrics': metrics, 'model': model, 'endpoint': endpoint}, sort_keys=True).encode('utf-8')
    ).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached
    prompt = (
        'Write a concise executive summary (80 to 120 words) for programme managers. '
        'Describe measured changes and notable patterns only. Do not infer causes, make forecasts, '
        'or recommend policy from these aggregate metrics. State when a metric is zero or unavailable. '
        'Keep funding currencies separate. Return plain text only. Metrics: ' + json.dumps(metrics)
    )
    payload = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You summarize aggregate startup programme metrics accurately and cautiously.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
        'max_tokens': 220,
    }).encode('utf-8')
    try:
        request = Request(endpoint, data=payload, headers={
            'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json',
        }, method='POST')
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read(256_000).decode('utf-8'))
        text = result['choices'][0]['message']['content']
        text = strip_tags(str(text)).strip()
        if not text:
            raise ValueError('The AI provider returned an empty summary.')
        summary = {'text': text[:4000], 'source': 'AI generated summary', 'ai_enabled': True}
        cache.set(cache_key, summary, 6 * 60 * 60)
        return summary
    except Exception:
        logger.warning('AI report summary unavailable; using the local summary.', exc_info=True)
        summary = {'text': fallback, 'source': 'Rule based summary (AI service unavailable)', 'ai_enabled': False}
        cache.set(cache_key, summary, 5 * 60)
        return summary
