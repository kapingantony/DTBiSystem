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
    return (
        f"From {data['start_date']} to {data['end_date']}, {data['new_startups']} startups were added "
        f"(versus {data['previous_startups']} in the preceding equal-length period), and {current} startups "
        f"are currently recorded. The system recorded {data['mentor_sessions']} mentor sessions "
        f"({data['mentor_hours']:,.1f} hours), {data['new_mentors']} new mentors, and "
        f"{data['new_investors']} new investors. Funding recorded: {funding}. "
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
