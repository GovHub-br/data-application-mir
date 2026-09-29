-- Paridade temporaria (spec §11): posicao nova x gold antigo, convenio a
-- convenio e medida a medida. Apagar na etapa 5, junto com o gold antigo.
-- O gold antigo tem linhas repetidas (resumo_convenios: 834 linhas para 643
-- convenios; a repeticao so muda a UG responsavel): fica uma linha por
-- convenio, a que tem UG. As duas tabelas antigas tem as mesmas colunas em
-- ordens diferentes, por isso a lista explicita.
{% set colunas = [
    "nr_convenio", "modalidade_instrumento", "situacao_atual", "origem",
    "valor_firmado_atualizado", "valor_firmado_inicial", "valor_repasse_previsto",
    "saldo_disponivel", "valor_contrapartida_previsto", "valor_total_repassado",
    "quantidade_desembolsos", "data_ultimo_desembolso", "valor_empenhado",
    "quantidade_empenhos", "valor_total_pago", "quantidade_pagamentos",
    "data_ultimo_pagamento", "valor_total_tributos", "quantidade_pagamentos_tributo",
    "valor_contrapartida_depositado", "valor_desbloqueado", "valor_bloqueado",
    "quantidade_licitacoes", "valor_total_contratado", "quantidade_metas",
    "quantidade_aditivos", "quantidade_prorrogacoes", "quantidade_mudancas_situacao",
    "inadimplente", "rescindido", "anulado", "prazo_vigente", "prazo_meta_expirado",
] %}
with
    antigo as (
        select 'resumo_convenios' as tabela, {{ colunas | join(", ") }}
        from
            (
                select distinct on (nr_convenio) *
                from {{ ref("resumo_convenios") }}
                order by nr_convenio, ug_responsavel_codigo nulls last
            ) as r

        union all

        select 'resumo_termos_fomento' as tabela, {{ colunas | join(", ") }}
        from
            (
                select distinct on (nr_convenio) *
                from {{ ref("resumo_termos_fomento") }}
                order by nr_convenio, ug_responsavel_codigo nulls last
            ) as t
    ),

    situacoes as (
        select sk_convenio, count(*) as qtd_mudancas_situacao
        from {{ ref("fato_evento_convenio") }}
        where tipo_evento = 'Mudança de situação'
        group by sk_convenio
    ),

    novo as (
        select
            d.nr_convenio,
            d.modalidade,
            d.situacao,
            d.origem_recurso,
            d.inadimplente,
            d.rescindido,
            d.anulado,
            d.vigente,
            d.meta_expirada,
            coalesce(s.qtd_mudancas_situacao, 0) as qtd_mudancas_situacao,
            p.*
        from {{ ref("fato_convenio_posicao") }} as p
        inner join {{ ref("dim_convenio") }} as d on d.sk_convenio = p.sk_convenio
        left join situacoes as s on s.sk_convenio = p.sk_convenio
    ),

    -- Cada tabela antiga e comparada so com os convenios que ela cobre; o
    -- resumo de termos de fomento cobre so a modalidade TERMO DE FOMENTO
    pares as (
        select a.tabela, a.nr_convenio as nr_antigo, n.nr_convenio as nr_novo, a, n
        from antigo as a
        full join
            (
                select n.*, t.tabela
                from novo as n
                cross join
                    (values ('resumo_convenios'), ('resumo_termos_fomento')) as t(tabela)
                where t.tabela = 'resumo_convenios' or n.modalidade = 'TERMO DE FOMENTO'
            ) as n
            on n.nr_convenio = a.nr_convenio
            and n.tabela = a.tabela
    )

select
    coalesce(p.tabela, (p.n).tabela) as tabela,
    coalesce(p.nr_antigo, p.nr_novo) as nr_convenio,
    c.medida,
    c.valor_antigo,
    c.valor_novo
from pares as p
cross join
    lateral(
        values
            (
                'presenca',
                (p.nr_antigo is not null)::text,
                (p.nr_novo is not null)::text,
                p.nr_antigo is null or p.nr_novo is null
            ),
            (
                'modalidade',
                (p.a).modalidade_instrumento,
                (p.n).modalidade,
                (p.a).modalidade_instrumento is distinct from (p.n).modalidade
            ),
            (
                'situacao',
                (p.a).situacao_atual,
                (p.n).situacao,
                (p.a).situacao_atual is distinct from (p.n).situacao
            ),
            (
                'origem',
                (p.a).origem,
                (p.n).origem_recurso,
                case
                    when (p.a).origem like 'Emenda%' then 'Emenda' else 'Recurso próprio'
                end
                is distinct from (p.n).origem_recurso
            ),
            (
                'valor_firmado_atualizado',
                (p.a).valor_firmado_atualizado::text,
                (p.n).valor_firmado_atualizado::text,
                coalesce((p.a).valor_firmado_atualizado, 0)
                <> coalesce((p.n).valor_firmado_atualizado, 0)
            ),
            (
                'valor_firmado_inicial',
                (p.a).valor_firmado_inicial::text,
                (p.n).valor_firmado_inicial::text,
                coalesce((p.a).valor_firmado_inicial, 0)
                <> coalesce((p.n).valor_firmado_inicial, 0)
            ),
            (
                'valor_repasse_previsto',
                (p.a).valor_repasse_previsto::text,
                (p.n).valor_repasse_previsto::text,
                coalesce((p.a).valor_repasse_previsto, 0)
                <> coalesce((p.n).valor_repasse_previsto, 0)
            ),
            (
                'saldo_em_conta',
                (p.a).saldo_disponivel::text,
                (p.n).valor_saldo_conta::text,
                coalesce((p.a).saldo_disponivel, 0)
                <> coalesce((p.n).valor_saldo_conta, 0)
            ),
            (
                'contrapartida_prevista',
                (p.a).valor_contrapartida_previsto::text,
                (p.n).valor_contrapartida_prevista::text,
                coalesce((p.a).valor_contrapartida_previsto, 0)
                <> coalesce((p.n).valor_contrapartida_prevista, 0)
            ),
            (
                'desembolsado',
                (p.a).valor_total_repassado::text,
                (p.n).valor_desembolsado::text,
                coalesce((p.a).valor_total_repassado, 0)
                <> coalesce((p.n).valor_desembolsado, 0)
            ),
            (
                'qtd_desembolsos',
                (p.a).quantidade_desembolsos::text,
                (p.n).qtd_desembolsos::text,
                coalesce((p.a).quantidade_desembolsos, 0)
                <> coalesce((p.n).qtd_desembolsos, 0)
            ),
            (
                'data_ultimo_desembolso',
                (p.a).data_ultimo_desembolso::text,
                (p.n).data_ultimo_desembolso::text,
                (p.a).data_ultimo_desembolso is distinct from (p.n).data_ultimo_desembolso
            ),
            (
                'empenhado_siconv',
                (p.a).valor_empenhado::text,
                (p.n).valor_empenhado_siconv::text,
                coalesce((p.a).valor_empenhado, 0)
                <> coalesce((p.n).valor_empenhado_siconv, 0)
            ),
            (
                'qtd_empenhos_siconv',
                (p.a).quantidade_empenhos::text,
                (p.n).qtd_empenhos_siconv::text,
                coalesce((p.a).quantidade_empenhos, 0)
                <> coalesce((p.n).qtd_empenhos_siconv, 0)
            ),
            (
                'pago_fornecedores',
                (p.a).valor_total_pago::text,
                (p.n).valor_pago_fornecedores::text,
                coalesce((p.a).valor_total_pago, 0)
                <> coalesce((p.n).valor_pago_fornecedores, 0)
            ),
            (
                'qtd_pagamentos',
                (p.a).quantidade_pagamentos::text,
                (p.n).qtd_pagamentos::text,
                coalesce((p.a).quantidade_pagamentos, 0)
                <> coalesce((p.n).qtd_pagamentos, 0)
            ),
            (
                'data_ultimo_pagamento',
                (p.a).data_ultimo_pagamento::text,
                (p.n).data_ultimo_pagamento::text,
                (p.a).data_ultimo_pagamento is distinct from (p.n).data_ultimo_pagamento
            ),
            (
                'tributos',
                (p.a).valor_total_tributos::text,
                (p.n).valor_tributos::text,
                coalesce((p.a).valor_total_tributos, 0)
                <> coalesce((p.n).valor_tributos, 0)
            ),
            (
                'qtd_pagamentos_tributo',
                (p.a).quantidade_pagamentos_tributo::text,
                (p.n).qtd_pagamentos_tributo::text,
                coalesce((p.a).quantidade_pagamentos_tributo, 0)
                <> coalesce((p.n).qtd_pagamentos_tributo, 0)
            ),
            (
                'contrapartida_depositada',
                (p.a).valor_contrapartida_depositado::text,
                (p.n).valor_contrapartida_depositada::text,
                coalesce((p.a).valor_contrapartida_depositado, 0)
                <> coalesce((p.n).valor_contrapartida_depositada, 0)
            ),
            (
                'desbloqueado',
                (p.a).valor_desbloqueado::text,
                (p.n).valor_desbloqueado::text,
                coalesce((p.a).valor_desbloqueado, 0)
                <> coalesce((p.n).valor_desbloqueado, 0)
            ),
            (
                'bloqueado',
                (p.a).valor_bloqueado::text,
                (p.n).valor_bloqueado::text,
                coalesce((p.a).valor_bloqueado, 0) <> coalesce((p.n).valor_bloqueado, 0)
            ),
            (
                'qtd_licitacoes',
                (p.a).quantidade_licitacoes::text,
                (p.n).qtd_licitacoes::text,
                coalesce((p.a).quantidade_licitacoes, 0)
                <> coalesce((p.n).qtd_licitacoes, 0)
            ),
            (
                'valor_licitado',
                (p.a).valor_total_contratado::text,
                (p.n).valor_licitado::text,
                coalesce((p.a).valor_total_contratado, 0)
                <> coalesce((p.n).valor_licitado, 0)
            ),
            (
                'qtd_metas',
                (p.a).quantidade_metas::text,
                (p.n).qtd_metas::text,
                coalesce((p.a).quantidade_metas, 0) <> coalesce((p.n).qtd_metas, 0)
            ),
            (
                'qtd_aditivos',
                (p.a).quantidade_aditivos::text,
                (p.n).qtd_aditivos::text,
                coalesce((p.a).quantidade_aditivos, 0) <> coalesce((p.n).qtd_aditivos, 0)
            ),
            (
                'qtd_prorrogacoes',
                (p.a).quantidade_prorrogacoes::text,
                (p.n).qtd_prorrogacoes::text,
                coalesce((p.a).quantidade_prorrogacoes, 0)
                <> coalesce((p.n).qtd_prorrogacoes, 0)
            ),
            (
                'qtd_mudancas_situacao',
                (p.a).quantidade_mudancas_situacao::text,
                (p.n).qtd_mudancas_situacao::text,
                coalesce((p.a).quantidade_mudancas_situacao, 0)
                <> coalesce((p.n).qtd_mudancas_situacao, 0)
            ),
            (
                'inadimplente',
                (p.a).inadimplente::text,
                (p.n).inadimplente::text,
                coalesce((p.a).inadimplente, false) <> coalesce((p.n).inadimplente, false)
            ),
            (
                'rescindido',
                (p.a).rescindido::text,
                (p.n).rescindido::text,
                coalesce((p.a).rescindido, false) <> coalesce((p.n).rescindido, false)
            ),
            (
                'anulado',
                (p.a).anulado::text,
                (p.n).anulado::text,
                coalesce((p.a).anulado, false) <> coalesce((p.n).anulado, false)
            ),
            (
                'vigente',
                (p.a).prazo_vigente::text,
                (p.n).vigente::text,
                coalesce((p.a).prazo_vigente, false) <> coalesce((p.n).vigente, false)
            ),
            (
                'meta_expirada',
                (p.a).prazo_meta_expirado::text,
                (p.n).meta_expirada::text,
                coalesce((p.a).prazo_meta_expirado, false)
                <> coalesce((p.n).meta_expirada, false)
            )
    ) as c(medida, valor_antigo, valor_novo, difere)
where c.difere
