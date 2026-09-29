{{ config(materialized="table") }}

-- Movimentos financeiros dos convenios do MIR, uma linha por movimento. Une as
-- tabelas do SICONV que tem a mesma forma (convenio, data, valor) para que o BI
-- compare entradas e saidas numa fato so. A chave de cada tipo e a chave
-- natural da origem (unica nos dados do MIR, garantida pelo teste unique).
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    movimentos as (
        select
            nr_convenio,
            'Desembolso federal' as tipo_movimento,
            id_desembolso::text as chave_origem,
            data_desembolso as data_movimento,
            vl_desembolsado as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            nr_siafi as documento_referencia
        from {{ ref("desembolso") }}

        union all

        select
            nr_convenio,
            'Contrapartida depositada' as tipo_movimento,
            concat_ws(
                '|', dt_ingresso_contrapartida, vl_ingresso_contrapartida
            ) as chave_origem,
            dt_ingresso_contrapartida as data_movimento,
            vl_ingresso_contrapartida as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as documento_referencia
        from {{ ref("ingresso_contrapartida") }}

        union all

        select
            nr_convenio,
            'Desbloqueio' as tipo_movimento,
            nr_ob as chave_origem,
            data_cadastro as data_movimento,
            vl_desbloqueado as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            nr_ob as documento_referencia
        from {{ ref("desbloqueio") }}

        union all

        select
            nr_convenio,
            'Pagamento a fornecedor' as tipo_movimento,
            nr_mov_fin::text as chave_origem,
            data_pag as data_movimento,
            vl_pago as valor,
            regexp_replace(identif_fornecedor, '\D', '', 'g') as fornecedor_documento,
            nome_fornecedor as fornecedor_nome,
            nr_dl as documento_referencia
        from {{ ref("pagamento") }}

        union all

        select
            nr_convenio,
            'Pagamento de tributo' as tipo_movimento,
            concat_ws('|', data_tributo, vl_pag_tributos) as chave_origem,
            data_tributo as data_movimento,
            vl_pag_tributos as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as documento_referencia
        from {{ ref("pagamento_tributo") }}
    )

select
    md5(concat_ws('|', m.tipo_movimento, m.nr_convenio, m.chave_origem)) as id_movimento,
    m.nr_convenio,
    m.tipo_movimento,
    m.data_movimento,
    m.valor,
    m.fornecedor_documento,
    m.fornecedor_nome,
    m.documento_referencia
from movimentos as m
inner join mir on mir.nr_convenio = m.nr_convenio
