"""The `report_feedback` tool: fixed schema, two consumer-facing knobs.

See the package docstring (`mcp_feedback/__init__.py`) for the full
rationale. This module is deliberately small: the function signature of
`register_feedback_tool` IS the enforcement mechanism for "exactly two
knobs" — there is no third parameter to add without changing this file.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Annotated

import pydantic
from fastmcp import (
    Context,  # noqa: TC002 — FastMCP's own get_type_hints() resolves the `ctx: Context` annotation at decoration time; it must stay a real runtime name, not TYPE_CHECKING-only.
)
from mcp.types import ToolAnnotations

from mcp_feedback._transport import post_feedback_logs

if TYPE_CHECKING:
    from fastmcp import FastMCP

_SCOPE_NAME = "mcp.feedback.agent"

_BASE_DESCRIPTION = (
    "Report your own subjective read on a result that didn't actually answer what you needed — "
    "even if the call otherwise succeeded.\n\n"
    "No category to pick — just say what was wrong (`note`) and, if you have one, what you wanted "
    "instead (`wanted`). `subject` is your own words for what this feedback concerns.\n\n"
    "Off unless the operator has configured a feedback endpoint; `sent=False` on the result most "
    "often means it isn't configured."
)


class FeedbackReportResult(pydantic.BaseModel):
    """`report_feedback`'s return value.

    `sent` reflects whether a send was ATTEMPTED (feedback reporting is
    configured) — never whether it was actually delivered, which is
    invisible by design (best-effort, swallowed on failure). `sent=False`
    most often means the operator hasn't configured an endpoint/key.
    """

    sent: bool


def _build_description(extra_instructions: str | None) -> str:
    if not extra_instructions:
        return _BASE_DESCRIPTION
    return f"{_BASE_DESCRIPTION}\n\n{extra_instructions}"


def register_feedback_tool(
    mcp: FastMCP,
    *,
    endpoint: str,
    api_key: str,
    extra_instructions: str | None = None,
) -> None:
    """Mount `report_feedback` on `mcp`.

    `endpoint`/`api_key` are resolved plain config values — this package
    owns no environment variable names or settings schema of its own.
    `extra_instructions` is appended to a fixed base description, never
    replacing it, for one line of consumer-specific guidance (e.g.
    "subject = the URL you fetched").
    """
    description = _build_description(extra_instructions)

    async def report_feedback(
        *,
        subject: Annotated[
            str,
            pydantic.Field(min_length=1, description="What this feedback concerns, in your own words."),
        ],
        note: Annotated[
            str,
            pydantic.Field(min_length=1, description="What was wrong — free text, your own words."),
        ],
        wanted: Annotated[
            str | None,
            pydantic.Field(description="What you would have preferred instead, if you have something specific in mind. Optional."),
        ] = None,
        ctx: Context,
    ) -> FeedbackReportResult:
        resource_attrs: list[dict[str, object]] = [
            {"key": "service.name", "value": {"stringValue": "mcp-feedback"}},
        ]
        attributes: list[dict[str, object]] = [
            {"key": "subject", "value": {"stringValue": subject}},
            {"key": "note", "value": {"stringValue": note}},
            {"key": "session_id", "value": {"stringValue": ctx.session_id}},
        ]
        if wanted:
            attributes.append({"key": "wanted", "value": {"stringValue": wanted}})
        log_records: list[dict[str, object]] = [
            {
                "timeUnixNano": str(time.time_ns()),
                "severityText": "INFO",
                "body": {"stringValue": note},
                "attributes": attributes,
            }
        ]
        sent = await post_feedback_logs(
            endpoint=endpoint,
            api_key=api_key,
            scope_name=_SCOPE_NAME,
            resource_attrs=resource_attrs,
            log_records=log_records,
        )
        return FeedbackReportResult(sent=sent)

    mcp.tool(
        name="report_feedback",
        description=description,
        annotations=ToolAnnotations(
            title="Report Feedback",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        tags={"write"},
    )(report_feedback)
