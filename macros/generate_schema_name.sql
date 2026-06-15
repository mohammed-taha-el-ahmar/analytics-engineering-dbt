{% macro generate_schema_name(custom_schema_name, node) -%}

    {#
        dbt's default behavior concatenates the target schema with any
        custom schema, e.g. `+schema: raw` becomes `dbt_alice_raw`. That's
        useful for ephemeral PR-preview schemas, but for this project we
        want a stable, predictable layout regardless of which target you
        run against: a `raw` schema, a `staging` schema, a `marts` schema,
        and a `marts_finance` schema — every time, in dev and in prod.

        This is the standard dbt-labs "use the custom schema name as-is"
        override. If a model doesn't set `+schema`, we fall back to the
        target's default schema as usual.
    #}

    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is none -%}

        {{ default_schema }}

    {%- else -%}

        {{ custom_schema_name | trim }}

    {%- endif -%}

{%- endmacro %}
