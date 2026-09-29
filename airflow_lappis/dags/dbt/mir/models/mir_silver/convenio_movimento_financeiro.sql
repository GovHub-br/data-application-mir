{{ config(materialized="table") }}

-- Movimentos financeiros dos convenios do MIR, uma linha por movimento. Une as
-- tabelas do SICONV que tem a mesma forma (convenio, data, valor) para que o BI
-- compare entradas e saidas numa fato so. A chave de cada tipo e a chave
-- natural da origem; contrapartida e tributo nao tem chave na origem e usam
-- data e valor (unicos nos dados atuais, garantidos pelo teste unique);
-- desbloqueio usa a linha inteira, sem as repeticoes da origem. O recorte do
-- MIR e aplicado em cada ramo, antes da uniao, para nao ler o SICONV inteiro.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    -- O SICONV publica o CPF mascarado (***12345***): o documento de pessoa
    -- fisica fica como veio, e a chave do fornecedor PF leva o nome, porque os
    -- 5 digitos visiveis nao identificam a pessoa sozinhos. CPF sem mascara e
    -- mascarado no mesmo formato. Documento sem formato de CPF ou CNPJ fica
    -- sem tipo e sem chave (fornecedor Nao identificado no gold).
    pagamentos as (
        select
            p.*,
            case
                when p.fornecedor_documento ~ '^\d{14}$'
                then 'PJ'
                when p.fornecedor_documento ~ '^\*{3}\d{5}\*{3}$'
                then 'PF'
            end as fornecedor_tipo
        from
            (
                select
                    nr_convenio,
                    nr_mov_fin,
                    data_pag,
                    vl_pago,
                    nr_dl,
                    case
                        when identif_fornecedor ~ '\*'
                        then upper(trim(identif_fornecedor))
                        when
                            regexp_replace(identif_fornecedor, '\D', '', 'g') ~ '^\d{11}$'
                        then
                            '***' || substr(
                                regexp_replace(identif_fornecedor, '\D', '', 'g'), 4, 5
                            )
                            || '***'
                        else nullif(regexp_replace(identif_fornecedor, '\D', '', 'g'), '')
                    end as fornecedor_documento,
                    nullif(trim(nome_fornecedor), '') as fornecedor_nome
                from {{ ref("pagamento") }}
                where nr_convenio in (select nr_convenio from mir)
            ) as p
    ),

    movimentos as (
        select
            nr_convenio,
            'Desembolso federal' as tipo_movimento,
            id_desembolso::text as chave_origem,
            data_desembolso as data_movimento,
            vl_desembolsado as valor,
            null::numeric as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            nr_siafi as documento_referencia
        from {{ ref("desembolso") }}
        where nr_convenio in (select nr_convenio from mir)

        union all

        select
            nr_convenio,
            'Contrapartida depositada' as tipo_movimento,
            concat_ws(
                '|', dt_ingresso_contrapartida, vl_ingresso_contrapartida
            ) as chave_origem,
            dt_ingresso_contrapartida as data_movimento,
            vl_ingresso_contrapartida as valor,
            null::numeric as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            null::text as documento_referencia
        from {{ ref("ingresso_contrapartida") }}
        where nr_convenio in (select nr_convenio from mir)

        union all

        select
            nr_convenio,
            'Desbloqueio' as tipo_movimento,
            concat_ws(
                '|',
                nr_ob,
                data_cadastro,
                data_envio,
                tipo_recurso_desbloqueio,
                vl_total_desbloqueio,
                vl_desbloqueado,
                vl_bloqueado
            ) as chave_origem,
            data_cadastro as data_movimento,
            vl_desbloqueado as valor,
            vl_bloqueado as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            nr_ob as documento_referencia
        -- O desbloqueio nao tem chave na origem e traz linhas identicas
        -- repetidas: remove as repeticoes e usa a linha inteira como chave
        from
            (
                select distinct *
                from {{ ref("desbloqueio") }}
                where nr_convenio in (select nr_convenio from mir)
            ) as d

        union all

        select
            nr_convenio,
            'Pagamento a fornecedor' as tipo_movimento,
            nr_mov_fin::text as chave_origem,
            data_pag as data_movimento,
            vl_pago as valor,
            null::numeric as valor_bloqueado,
            fornecedor_documento,
            fornecedor_nome,
            fornecedor_tipo,
            case
                when fornecedor_tipo = 'PJ'
                then fornecedor_documento
                when fornecedor_tipo = 'PF'
                then fornecedor_documento || '|' || coalesce(fornecedor_nome, '')
            end as fornecedor_chave,
            nr_dl as documento_referencia
        from pagamentos

        union all

        select
            nr_convenio,
            'Pagamento de tributo' as tipo_movimento,
            concat_ws('|', data_tributo, vl_pag_tributos) as chave_origem,
            data_tributo as data_movimento,
            vl_pag_tributos as valor,
            null::numeric as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            null::text as documento_referencia
        from {{ ref("pagamento_tributo") }}
        where nr_convenio in (select nr_convenio from mir)
    )

select
    md5(concat_ws('|', m.tipo_movimento, m.nr_convenio, m.chave_origem)) as id_movimento,
    m.nr_convenio,
    m.tipo_movimento,
    m.data_movimento,
    m.valor,
    m.valor_bloqueado,
    m.fornecedor_documento,
    m.fornecedor_nome,
    m.fornecedor_tipo,
    m.fornecedor_chave,
    m.documento_referencia
from movimentos as m
