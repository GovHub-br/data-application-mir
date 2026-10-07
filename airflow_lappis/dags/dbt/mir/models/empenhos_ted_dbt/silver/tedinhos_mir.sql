{{ config(materialized="table") }}

{#
  Detecção de "tedinhos" (issue #507): uma Descentralização de Crédito do MIR
  que nunca é registrada no TransfereGov. Só pode vir do lado em que o MIR
  descentraliza (relatorio = 'enviadas') -- o lado 'recebidas' é sobre o MIR
  executando crédito de OUTRO órgão, uma categoria diferente, fora do escopo
  da issue.

  Chave de instrumento, em ordem de preferência:
    1. nc_transferencia, quando já atribuído (!= '-8') -- existe em TODOS os
       anos (2023-2026), é a chave universal.
    2. processo, extraído do texto de descricao -- só existe no relatório
       pós-2026 (o relatório "até 2025" do Tesouro Gerencial não tem esse
       campo de texto livre).
    3. a própria NC -- fallback de último caso quando nenhum dos dois
       identificadores acima existe (nc_transferencia ainda '-8' e sem
       processo, tipicamente pré-2026). Grão mais fino que o ideal, mas
       nunca funde instrumentos diferentes por falta de um identificador
       comum -- mais seguro que arriscar um agrupamento errado.

  nc_transferencia = '-8' sozinho NÃO identifica o instrumento (é "ainda não
  atribuído", não um identificador único -- várias NCs distintas podem estar
  em '-8' ao mesmo tempo). Por isso só vira chave quando tem valor real.

  O registro no TransfereGov é checado contra ted_plano_acao_consolidado
  (fonte nova do PR #75: portal do sistema TED + página de transparência do
  gov.br + dados abertos como reserva) -- cobre mais instrumentos conhecidos
  que a fonte antiga (planos_acao_ted sozinha), reduzindo falso positivo de
  tedinho. Mesmo assim, o texto da NC às vezes já cita um código antes do
  campo estruturado ser atualizado (ex.: TED normal em trânsito) -- por isso
  também extraímos codigo_mencionado_no_texto como segundo sinal.
#}

with
    nc_descentralizacao as (
        select
            nc,
            nc_ug_responsavel,
            nc_ug_responsavel_descricao,
            valor_celula,
            nc_evento_descricao,
            nc_transferencia,
            emissao_dia,
            descricao,
            -- Restrito ao prefixo 21290 (orgao SEI do MIR): sem isso, o
            -- regex tambem casava processo administrativo de OUTRO orgao
            -- (ex: da instituicao favorecida) quando citado no texto da NC,
            -- misturando processos que nao sao do MIR.
            (regexp_match(descricao, '(21290\.[0-9]{6}/[0-9]{4}-[0-9]{2})'))[1] as processo,
            coalesce(
                (regexp_match(
                    descricao, 'TED\s+([0-9]{6}|1[A-Za-z0-9]{5}|7[A-Za-z0-9]{5})'
                ))[1],
                (regexp_match(
                    descricao,
                    'DESCENTRALIZADA\s*N[^0-9A-Za-z]*([0-9]{6}|1[A-Za-z0-9]{5}|7[A-Za-z0-9]{5})'
                ))[1]
            ) as codigo_mencionado_no_texto,
            dt_ingest
        from {{ ref('nc_tesouro_mir') }}
        where relatorio = 'enviadas'
            and nc_evento_descricao ilike '%DESCENTRALIZACAO DE CREDITO%'
    ),

    -- Chave de instrumento com prefixo por tipo, para nunca colidir um
    -- nc_transferencia '123456' com um processo ou NC que por acaso tenha o
    -- mesmo texto.
    chaveada as (
        select
            *,
            case
                -- processo tem prioridade sobre nc_transferencia: e estavel
                -- ao longo do ciclo de vida do instrumento, enquanto
                -- nc_transferencia pode comecar em '-8' e so ganhar um
                -- codigo real depois de uma anulacao/reemissao (caso MIR x
                -- UFF/CERD, processo 21290.000127/2026-28) -- se
                -- nc_transferencia tivesse prioridade, as NCs de antes e
                -- depois da reemissao cairiam em instrumento_key diferentes
                -- e quebrariam o grao.
                when processo is not null then 'proc:' || processo
                when nc_transferencia is not null and nc_transferencia <> '-8'
                    then 'transf:' || nc_transferencia
                else 'nc:' || nc
            end as instrumento_key
        from nc_descentralizacao
    ),

    -- Uma descentralização pode ser anulada e reemitida com um
    -- nc_transferencia diferente. O estado que importa para classificar o
    -- instrumento é o mais recente, não o primeiro.
    transferencia_atual as (
        select instrumento_key, nc_transferencia
        from (
            select
                instrumento_key,
                nc_transferencia,
                row_number() over (
                    partition by instrumento_key
                    order by emissao_dia desc nulls last, nc desc
                ) as rn
            from chaveada
        ) ranked
        where rn = 1
    ),

    -- Um código mencionado em QUALQUER NC do instrumento (mesmo uma anterior
    -- à mais recente) já invalida o instrumento como tedinho forte.
    codigo_no_texto_por_instrumento as (
        select instrumento_key, max(codigo_mencionado_no_texto) as codigo_mencionado_no_texto
        from chaveada
        group by instrumento_key
    ),

    classificacao_por_instrumento as (
        select
            ta.instrumento_key,
            ta.nc_transferencia as nc_transferencia_atual,
            cnt.codigo_mencionado_no_texto,
            (pa.sq_instrumento is not null) as registrado_no_transferegov
        from transferencia_atual ta
        left join codigo_no_texto_por_instrumento cnt using (instrumento_key)
        left join {{ ref("ted_plano_acao_consolidado") }} pa
            on pa.sq_instrumento = ta.nc_transferencia
    )

select
    nd.nc,
    nd.instrumento_key,
    nd.processo,
    nd.nc_ug_responsavel,
    nd.nc_ug_responsavel_descricao,
    nd.valor_celula,
    nd.nc_evento_descricao,
    nd.nc_transferencia,
    nd.emissao_dia,
    nd.descricao,
    nd.dt_ingest,
    c.nc_transferencia_atual,
    c.codigo_mencionado_no_texto,
    coalesce(c.registrado_no_transferegov, false) as registrado_no_transferegov,
    (
        not coalesce(c.registrado_no_transferegov, false)
        and c.codigo_mencionado_no_texto is null
    ) as tedinho_provavel
from chaveada nd
left join classificacao_por_instrumento c using (instrumento_key)
