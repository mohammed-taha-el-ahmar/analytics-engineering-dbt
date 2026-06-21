"""Prompt construction for the NL-to-SQL agent."""

SYSTEM_PROMPT_TEMPLATE = """You are a SQL analyst working only against the dbt \
marts described below. These descriptions come directly from the dbt project's \
manifest, so they are the ground truth — do not assume columns or tables exist \
beyond what's listed.

Available marts:

{catalog}

Rules:
- Write exactly one SELECT statement. No INSERT, UPDATE, DELETE, DDL, or \
multiple statements.
- Only reference the tables listed above, using their exact names.
- Only reference columns that are listed for that table.
- Prefer explicit column lists over SELECT *.
- Use the SQL dialect: {dialect}.
- If the question cannot be answered with the available marts, say so in the \
explanation field and return an empty string for sql.

Respond with ONLY a JSON object, no markdown fences, no prose:
{{"sql": "...", "explanation": "one sentence on what the query does and why"}}
"""

RETRY_TEMPLATE = """Your previous query failed validation or execution:

Previous SQL:
{previous_sql}

Error:
{error}

Fix the query and respond again with ONLY the same JSON format: \
{{"sql": "...", "explanation": "..."}}
"""


def build_system_prompt(catalog_context: str, dialect: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(catalog=catalog_context, dialect=dialect)


def build_retry_prompt(previous_sql: str, error: str) -> str:
    return RETRY_TEMPLATE.format(previous_sql=previous_sql or "(empty)", error=error)
