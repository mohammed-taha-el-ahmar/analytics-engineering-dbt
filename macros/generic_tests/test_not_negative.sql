{% test not_negative(model, column_name) %}

    {#
        Custom business-logic test.

        Generic dbt tests (unique, not_null, relationships, accepted_values)
        check referential integrity and value membership, but they don't
        encode domain rules like "this is a monetary amount and must never
        be negative". This generic test fills that gap and can be reused on
        any numeric column across the project.

        Returns any rows where the column is negative — a passing test
        returns zero rows.
    #}

    select *
    from {{ model }}
    where {{ column_name }} < 0

{% endtest %}
