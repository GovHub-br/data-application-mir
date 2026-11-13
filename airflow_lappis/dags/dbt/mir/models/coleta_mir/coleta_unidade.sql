{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, Bloco 2 do formulário de TEDs: código Siorg e CNPJ da unidade
  descentralizadora responsável. coleta_ted traz a sigla e o nome da unidade que
  acompanha o TED, mas o portal TED não traz estes dois campos. Eles vêm do seed
  coleta_unidade_mir, cuja descrição dá a fonte de cada um.

  O consumidor liga coleta_ted.sg_unidade_acompanhamento a coleta_unidade.sg_unidade. Uma
  sigla nova no portal fica sem linha aqui; test_coleta_unidade_sigla_do_ted avisa.

  coleta_convenio já traz a sigla da unidade concedente, achada pela UG (cd_ug); liga
  da mesma forma, por sg_unidade.
#}
select
    sg_unidade::text as sg_unidade,
    no_unidade::text as no_unidade,
    cd_siorg::text as cd_siorg,
    nr_cnpj::text as nr_cnpj,
    cd_ug::text as cd_ug
from {{ ref("coleta_unidade_mir") }}
