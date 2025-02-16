{% macro create_f_parse_financial_value() %}

    create or replace function {{ target.schema }}.parse_number(in_text text)
    returns numeric
    as
        $$
	select
		case when in_text like '(%' then regexp_replace(replace(coalesce(in_text, '0'), '.', ''), '(\()?(\d+),(\d+)(\))?', '-\2.\3')::numeric(15,2)
			else replace(replace(coalesce(in_text, '0'), '.', ''), ',', '.')::numeric(15,2) end as result
$$
    language sql
    ;

{% endmacro %}
