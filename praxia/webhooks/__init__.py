"""Outgoing webhooks — fire HTTP POSTs on Praxia events.

Use cases:
    - Notify a Slack channel when a flow completes
    - Push skill output to a Microsoft Teams Incoming Webhook
    - Trigger a downstream workflow in Zapier / n8n / make.com
    - Call a custom internal endpoint when consolidate finishes

Subscriptions are per-event and persisted to disk:

    .praxia/webhooks/subscriptions.json

Each subscription is:

    Subscription(
        id="uuid",
        url="https://hooks.slack.com/services/...",
        event="flow.completed",        # or "*" for all
        active=True,
        secret="hmac-shared-secret",   # optional; signs each delivery
        created_at=...,
        labels={"team": "growth"},
    )

When an event fires, every active subscription whose `event` matches receives
the JSON payload. Failures are recorded to a delivery log; retries are
left to the operator (we keep this layer tiny — use a real queue for
high-stakes wiring).

Standard events:
    flow.run.start | flow.run.complete | flow.run.error
    skill.run.start | skill.run.complete
    memory.consolidate.complete
    memory.freeze
    user.create | user.delete
    policy.deny
    skill.promote
    experiment.results

Custom events: any caller can `dispatch("my.event", payload)`.
"""
from praxia.webhooks.framework import (
    Subscription,
    WebhookManager,
    WebhookDelivery,
    sign_payload,
    verify_payload,
)

__all__ = [
    "Subscription",
    "WebhookManager",
    "WebhookDelivery",
    "sign_payload",
    "verify_payload",
]
