{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, Bloco 2 do formulário de TEDs: código Siorg, UG e CNPJ da
  unidade descentralizadora responsável. coleta_ted traz a sigla e o nome da unidade que
  acompanha o TED, mas o portal TED não traz estes três campos. Eles vêm do seed
  coleta_unidade_mir, cuja descrição dá a fonte de cada um.

  cd_ug é 810008 nas quatro linhas: é a UG que emite as NCs de todos os TEDs do MIR,
  qualquer que seja a secretaria. As UGs próprias das secretarias (ugs_mir) são da
  estrutura organizacional e não descentralizam.

  O consumidor liga coleta_ted.sg_unidade_acompanhamento a coleta_unidade.sg_unidade. Uma
  sigla nova no portal fica sem linha aqui; test_coleta_unidade_sigla_do_ted avisa.
#}
select
    sg_unidade::text as sg_unidade,
    no_unidade::text as no_unidade,
    cd_siorg::text as cd_siorg,
    cd_ug::text as cd_ug,
    nr_cnpj::text as nr_cnpj
from {{ ref("coleta_unidade_mir") }}
