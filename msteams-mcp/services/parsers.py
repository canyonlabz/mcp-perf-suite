"""
Pure parsing functions for Teams API responses.

Handles HTML stripping, link extraction, and structured parsing of
Substrate search results, people suggestions, and channel suggestions.
No I/O or auth dependencies — all functions are stateless.

Ported from the TypeScript parsers-search.ts, parsers-people.ts,
and parsers-channels.ts modules in the msteams-mcp reference project.
"""

import base64
import re
import uuid
from html import unescape
from typing import Any

MIN_CONTENT_LENGTH = 5

# ---------------------------------------------------------------------------
# HTML utilities
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities, collapsing whitespace."""
    cleaned = _TAG_RE.sub(" ", text)
    cleaned = unescape(cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def extract_links(html: str) -> list[dict[str, str]]:
    """Extract href/text pairs from <a> tags before HTML is stripped."""
    links: list[dict[str, str]] = []
    for match in _HREF_RE.finditer(html):
        href = match.group(1).strip()
        text = strip_html(match.group(2)).strip()
        if href:
            links.append({"url": href, "text": text or href})
    return links


# ---------------------------------------------------------------------------
# Search result parsing (Substrate v2/query)
# ---------------------------------------------------------------------------


def _extract_conversation_id(source: dict[str, Any]) -> str | None:
    """
    Extract conversationId with the same priority as the TS reference:
    ClientThreadId > Extensions.SkypeGroupId > ClientConversationId (strip ;messageid=).
    """
    client_thread_id = source.get("ClientThreadId")
    if isinstance(client_thread_id, str) and client_thread_id:
        return client_thread_id

    extensions = source.get("Extensions")
    if isinstance(extensions, dict):
        group_id = extensions.get("SkypeSpaces_ConversationPost_Extension_SkypeGroupId")
        if isinstance(group_id, str) and group_id:
            return group_id

    client_conv_id = source.get("ClientConversationId")
    if isinstance(client_conv_id, str) and client_conv_id:
        return client_conv_id.split(";")[0]

    return None


def _extract_message_timestamp(source: dict[str, Any], fallback_ts: str | None) -> str | None:
    """Extract a numeric message timestamp for deep links and thread identification."""
    for key in ("ComposeTime", "OriginalArrivalTime"):
        val = source.get(key)
        if isinstance(val, str) and val.isdigit():
            return val

    if fallback_ts:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(fallback_ts.replace("Z", "+00:00"))
            return str(int(dt.timestamp() * 1000))
        except Exception:
            pass

    return None


def parse_v2_result(item: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single v2 query result item into a search result dict."""
    content = item.get("HitHighlightedSummary") or item.get("Summary") or ""
    if len(content) < MIN_CONTENT_LENGTH:
        return None

    result_id = (
        item.get("Id")
        or item.get("ReferenceId")
        or f"v2-{uuid.uuid4()}"
    )

    links = extract_links(content)
    clean_content = strip_html(content)

    source: dict[str, Any] = item.get("Source") or {}

    conversation_id = _extract_conversation_id(source)

    timestamp = (
        source.get("DateTimeReceived")
        or source.get("DateTimeSent")
        or source.get("DateTimeCreated")
        or source.get("ReceivedTime")
        or source.get("CreatedDateTime")
    )

    message_timestamp = _extract_message_timestamp(source, timestamp)

    parent_message_id: str | None = None
    client_conv_id = source.get("ClientConversationId")
    if isinstance(client_conv_id, str) and ";messageid=" in client_conv_id:
        match = re.search(r";messageid=(\d+)", client_conv_id)
        if match:
            parent_message_id = match.group(1)

    result: dict[str, Any] = {
        "id": result_id,
        "type": "message",
        "content": clean_content,
        "sender": source.get("From") or source.get("Sender"),
        "timestamp": timestamp,
        "channelName": source.get("ChannelName") or source.get("Topic"),
        "teamName": source.get("TeamName") or source.get("GroupName"),
        "conversationId": conversation_id,
        "messageId": message_timestamp or item.get("ReferenceId"),
    }

    if links:
        result["links"] = links
    if parent_message_id:
        result["parentMessageId"] = parent_message_id

    return result


def parse_search_results(
    entity_sets: list[Any] | None,
) -> dict[str, Any]:
    """
    Parse Substrate v2/query EntitySets response into search results.

    Returns {"results": [...], "total": int | None}.
    """
    results: list[dict[str, Any]] = []
    total: int | None = None

    if not isinstance(entity_sets, list):
        return {"results": results, "total": total}

    for entity_set in entity_sets:
        if not isinstance(entity_set, dict):
            continue
        result_sets = entity_set.get("ResultSets")
        if not isinstance(result_sets, list):
            continue

        for result_set in result_sets:
            if not isinstance(result_set, dict):
                continue

            rs_total = (
                result_set.get("Total")
                or result_set.get("TotalCount")
                or result_set.get("TotalEstimate")
            )
            if isinstance(rs_total, (int, float)):
                total = int(rs_total)

            items = result_set.get("Results")
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                parsed = parse_v2_result(item)
                if parsed:
                    results.append(parsed)

    return {"results": results, "total": total}


# ---------------------------------------------------------------------------
# People result parsing (Substrate v1/suggestions)
# ---------------------------------------------------------------------------

def _extract_object_id(raw_id: str) -> str | None:
    """
    Convert a raw ID to a proper GUID format.
    Handles plain GUIDs, base64-encoded GUIDs, and email-suffixed IDs.
    """
    id_part = raw_id.split("@")[0] if "@" in raw_id else raw_id

    guid_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    if guid_re.match(id_part):
        return id_part

    try:
        decoded = base64.b64decode(id_part + "=" * (-len(id_part) % 4))
        if len(decoded) == 16:
            return str(uuid.UUID(bytes_le=decoded))
    except Exception:
        pass

    return None


def parse_person_suggestion(item: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single person suggestion from Substrate API response."""
    raw_id = item.get("Id")
    if not isinstance(raw_id, str) or not raw_id:
        return None

    object_id = _extract_object_id(raw_id)
    if not object_id:
        return None

    mri = item.get("MRI") or f"8:orgid:{object_id}"
    if "orgid:" in mri and "-" not in mri:
        mri = f"8:orgid:{object_id}"

    email_addresses = item.get("EmailAddresses")
    email = email_addresses[0] if isinstance(email_addresses, list) and email_addresses else None

    result: dict[str, Any] = {
        "id": object_id,
        "mri": mri,
        "displayName": item.get("DisplayName") or "",
        "email": email,
    }

    for field in ("GivenName", "Surname", "JobTitle", "Department", "CompanyName"):
        val = item.get(field)
        if val:
            py_field = field[0].lower() + field[1:]
            result[py_field] = val

    return result


def parse_people_results(groups: list[Any] | None) -> list[dict[str, Any]]:
    """Parse Groups/Suggestions structure from Substrate people search."""
    results: list[dict[str, Any]] = []
    if not isinstance(groups, list):
        return results

    for group in groups:
        if not isinstance(group, dict):
            continue
        suggestions = group.get("Suggestions")
        if not isinstance(suggestions, list):
            continue
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                continue
            parsed = parse_person_suggestion(suggestion)
            if parsed:
                results.append(parsed)

    return results


# ---------------------------------------------------------------------------
# Channel result parsing (Substrate suggestions + CSA teams list)
# ---------------------------------------------------------------------------

def parse_channel_suggestion(suggestion: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single channel suggestion from Substrate API response."""
    name = suggestion.get("Name")
    thread_id = suggestion.get("ThreadId")
    team_name = suggestion.get("TeamName")
    group_id = suggestion.get("GroupId")

    if not all((name, thread_id, team_name, group_id)):
        return None

    return {
        "channelId": thread_id,
        "channelName": name,
        "teamName": team_name,
        "teamId": group_id,
        "channelType": suggestion.get("ChannelType") or "Standard",
        "description": suggestion.get("Description"),
    }


def parse_channel_results(groups: list[Any] | None) -> list[dict[str, Any]]:
    """Parse Groups/Suggestions for ChannelSuggestion entities from Substrate."""
    results: list[dict[str, Any]] = []
    if not isinstance(groups, list):
        return results

    for group in groups:
        if not isinstance(group, dict):
            continue
        suggestions = group.get("Suggestions")
        if not isinstance(suggestions, list):
            continue
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                continue
            if suggestion.get("EntityType") != "ChannelSuggestion":
                continue
            parsed = parse_channel_suggestion(suggestion)
            if parsed:
                results.append(parsed)

    return results


def filter_channels_by_name(
    teams_data: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """
    Filter channels from CSA teams list by name (case-insensitive partial match).

    Expects teams_data in the format returned by teams_api.get_my_teams_and_channels():
    [{"id": ..., "displayName": ..., "channels": [{"id": ..., "displayName": ...}, ...]}]
    """
    lower_query = query.lower()
    results: list[dict[str, Any]] = []

    for team in teams_data:
        if not isinstance(team, dict):
            continue
        team_name = team.get("displayName", "")
        for channel in team.get("channels", []):
            if not isinstance(channel, dict):
                continue
            ch_name = channel.get("displayName", "")
            if lower_query in ch_name.lower():
                results.append({
                    "channelId": channel.get("id", ""),
                    "channelName": ch_name,
                    "teamName": team_name,
                    "teamId": team.get("id", ""),
                    "channelType": channel.get("membershipType", "Standard"),
                    "description": channel.get("description"),
                    "isMember": True,
                })

    return results
