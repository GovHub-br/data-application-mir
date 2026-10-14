-- Falha se a ponte tiver mais de uma linha por ano_ppa x nivel x item x agenda.
-- Linha repetida na ponte duplicaria os valores no BI ao filtrar por agenda.
select
    ano_ppa,
    nivel,
    programa,
    objetivo,
    objetivo_especifico,
    entrega,
    indicador,
    meta_do_objetivo_especifico,
    meta_da_entrega,
    regiao,
    publico,
    medida_institucional_normativa,
    enunciado,
    codigo_agenda,
    count(*) as linhas
from {{ ref('ponte_agenda_mir') }}
group by
    ano_ppa,
    nivel,
    programa,
    objetivo,
    objetivo_especifico,
    entrega,
    indicador,
    meta_do_objetivo_especifico,
    meta_da_entrega,
    regiao,
    publico,
    medida_institucional_normativa,
    enunciado,
    codigo_agenda
having count(*) > 1
