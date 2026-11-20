# Diagnostics

Expected failures keep their legacy `error` string and add a `diagnostic`
object with a stable code, a fix, and this page. HTTP 422 responses put the
same object in `detail`.

| code | meaning | fix |
|---|---|---|
| `SUP_INPUT_EMPTY` | required workflow/chat text was blank | send non-blank text |
| `SUP_INPUT_TOO_LARGE` | input exceeded 8,000 chars | shorten it; never truncated |
| `SUP_NO_SKILLS` | extractor returned no skills | name concrete skills in the input |
| `SUP_TOOL_UNKNOWN` | tool/skill is not advertised | use an advertised tool |
| `SUP_DELEGATION_FAILED` | skills-agent or engine call failed | start it, then retry |

## SUP_INPUT_EMPTY

A required field was blank. `screen_candidate` needs both `jd_text` and
`resume_text`; `talent_brief` needs `topic`; `/chat` needs `message`.

## SUP_INPUT_TOO_LARGE

Input crossed `MAX_WORKFLOW_CHARS` (8,000). Shorten it upstream. The server
refuses rather than truncating, because truncation silently drops skills.

## SUP_NO_SKILLS

The extractor completed but found nothing. Send text that names real skills
(tools, languages, platforms) rather than a generic role description.

## SUP_TOOL_UNKNOWN

The model or caller asked for a tool that is not in the advertised set. Use
`ask_skills_agent`, `search_agent_registry`, or `list_mcp_servers`; the
skills-agent itself handles `infer_skills`, `normalize_skill`,
`search_taxonomy`, and `lifecycle_report`.

## SUP_DELEGATION_FAILED

The delegated call raised. Check that the skills-agent and the backing engine
are running, then retry. The response includes a `request_id` for log lookup.
