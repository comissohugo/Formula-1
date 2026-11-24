# F1 DATA CENTER --- Changelog

Registro cronológico das decisões, entregas e alterações do projeto.

## 2026-11-08 --- Início da documentação central

### Decisões confirmadas pelo usuário

-   Formato escolhido: dashboard interativo.
-   Nível de detalhamento: completo.
-   Temporadas iniciais: 2021, 2022, 2023, 2024 e 2025.
-   Temporada 2026: adicionar somente após o encerramento.
-   Detalhamento por GP: classificação e corrida completas.
-   O usuário quer poder compartilhar este documento Markdown com outra
    IA para continuar o projeto.

### Escopo confirmado

-   Classificação: posições, pilotos, equipes e tempos Q1/Q2/Q3 quando
    disponíveis.
-   Corrida: classificação completa, grid, voltas, pontos, status, tempo
    e volta mais rápida quando disponível.
-   Rankings e comparações de pilotos e equipes.
-   Sprint em seção separada, sem misturar com GP principal.

### Protótipo preparado

Foi criado o pacote `f1_data_center_2021_2025.zip`, contendo: -
`app.py` - `requirements.txt` - `README.md`

Tecnologias do protótipo: Python, Streamlit, Pandas, Requests e Plotly.
Fonte planejada: Jolpica F1 API.

### Estado técnico no fechamento desta entrada

-   O pacote do protótipo foi gerado.
-   O usuário informou que já tem Python instalado.
-   A instalação das dependências e a execução local ainda não foram
    concluídas.
-   A importação efetiva dos dados 2021--2025 ainda não foi executada
    nem validada.
-   O código inicial precisa ser testado, especialmente a paginação dos
    endpoints e a conferência dos dados históricos.
-   Não afirmar que os 114 GPs já foram importados.

### Próxima ação

Ajudar o usuário no Windows a extrair o ZIP, instalar dependências com:

``` bash
python -m pip install -r requirements.txt
```

e iniciar o painel com:

``` bash
streamlit run app.py
```

Depois, corrigir eventuais erros e implementar importação persistente e
validação da base.

------------------------------------------------------------------------

## 2026-11-08 --- Base 2021-2025 importada e validada; dashboard reescrito

### Decisão

-   Construir o projeto do zero em
    `C:\Users\Usuario\Documents\f1-data-center`, mantendo o protótipo
    original apenas como referência em `docs/app_prototipo_original.py`.
-   Priorizar integridade histórica: importar e validar os 114 GPs antes
    de evoluir o visual.

### Arquivos criados

-   `app.py`, `requirements.txt`, `README.md`, `.gitignore`
-   `f1dc/config.py`, `api.py`, `transform.py`, `db.py`, `ingest.py`,
    `validate.py`, `data.py`
-   `tests/test_transform.py`, `test_db.py`, `test_data.py`,
    `test_ingest.py`, `test_app_smoke.py`
-   `data/f1.db` (não versionado) e `data/validation_report.json`

### O que foi implementado

-   Cliente Jolpica com retry exponencial, ritmo adaptativo (HTTP 429) e
    paginação.
-   Importação **por GP** (obrigatória: a API limita `limit` a 100 linhas;
    buscar por temporada trunca GPs no meio da página).
-   SQLite com o modelo da seção 4 do documento central, mais
    `source_url`, `fetched_at` e `import_runs`.
-   Reimportação idempotente: a temporada é apagada e regravada em uma
    transação, sem duplicar registros.
-   Dashboard com abas Corridas, Campeonato, Pilotos, Equipes e
    Qualidade dos dados; exportação CSV.
-   Validação com 16 checagens, incluindo reconciliação de pontos
    (corrida + sprint x standings oficiais).
-   Desclassificação tratada nos dois formatos da fonte
    (`positionText = "D"` e `status = "Disqualified"`).

### Testes realizados

-   17 testes automatizados (`pytest`), incluindo smoke test do
    Streamlit (abertura e troca de temporada).
-   Importação real: 415 requisições, 114 GPs, status `ok`.
-   Validação: 16/16 checagens aprovadas e **zero divergência de pontos**
    para pilotos e construtores.
-   Campeões conferidos contra fonte externa: 2021 Verstappen/Mercedes,
    2022 Verstappen/Red Bull, 2023 Verstappen/Red Bull, 2024
    Verstappen/McLaren, 2025 Norris/McLaren.

### Ausências reais da fonte (documentadas, não preenchidas)

-   2021 R12 Bélgica: sem volta mais rápida (corrida encerrada sob safety
    car após 1 volta).
-   2021 R5 Mônaco: Schumacher sem linha na classificação (largou do pit
    lane).
-   2025 R9 Espanha: Stroll classificado, ausente no resultado (DNS não
    retornado pela fonte).
-   2025 R21 São Paulo: Bortoleto no resultado, ausente na classificação.

### Problemas conhecidos

-   A API pública aplica HTTP 429 com frequência; a importação leva
    vários minutos e o cliente reduz o ritmo automaticamente.
-   Penalidades não são inferidas; apenas os status fornecidos são
    exibidos.
-   A volta mais rápida de 2025 existe na API, mas não vale ponto (regra
    extinta); os pontos exibidos vêm dos standings oficiais.

### Próxima ação

-   Fase D: refinar visual, comparações históricas entre temporadas e
    revisar textos de limitações no painel.

------------------------------------------------------------------------

## 2026-11-08 --- Fase D: aba Histórico e comparações 2021-2025

### Decisão

-   Criar a aba **Histórico** com comparações do período completo,
    independentes do filtro de temporada da barra lateral.
-   Todas as métricas derivam dos resultados e standings já validados;
    nada é inventado ou preenchido por suposição.

### Arquivos alterados

-   `f1dc/data.py`: novas agregações do período.
-   `app.py`: nova aba e modernização de parâmetros do Streamlit.
-   `tests/test_data.py`: 6 testes novos para as agregações.
-   `docs/CHANGELOG.md` e `README.md`.

### O que foi implementado

-   **Campeões do período**: tabela e gráfico com campeão de pilotos,
    pontos, vitórias, equipe campeã e pontos da equipe.
-   **Ranking acumulado**: pontos, vitórias, pódios, poles, voltas mais
    rápidas e largadas, com seletor de métrica, top N e exportação CSV.
    Pontos somam corridas + sprints; vitórias e pódios ignoram
    desclassificados.
-   **Duelo entre pilotos**: confronto direto na classificação e nas
    corridas (apenas GPs em que ambos têm dado) e pontos por temporada.
-   **Por circuito**: uma linha por edição (vencedor, equipe, pole e
    volta mais rápida), gráfico de vitórias e exportação CSV.
-   **Equipes no período**: tabela de pontos, vitórias e pódios, mais
    gráfico de pontos por equipe e temporada.
-   Modernização: `use_container_width` substituído por `width="stretch"`
    e colunas de posição convertidas para texto, eliminando avisos de
    serialização do Arrow.

### Testes realizados

-   22 testes automatizados passando (6 novos para o período).
-   `AppTest`: 6 abas, 14 tabelas, 9 gráficos, zero exceções.
-   Navegador: aba Histórico com 5 seções, 4 tabelas e 5 gráficos, sem
    erros no console.
-   Amostras conferidas: campeões 2021-2025; Verstappen com 2.282,5
    pontos no período; Silverstone 2021 Hamilton/Hamilton/Pérez;
    H2H Verstappen x Hamilton 89x25 na classificação e 78x23 nas
    corridas.

### Problemas conhecidos

-   Um servidor Streamlit já em execução precisa ser reiniciado após
    alterações em `f1dc/*.py`, pois o processo mantém o módulo em cache.
-   O duelo usa os IDs internos dos pilotos; IDs sem GPs em comum exibem
    zeros (comportamento correto, não é erro).

### Próxima ação

-   Comparação livre entre pilotos de equipes diferentes na aba Pilotos
    (se desejado).

------------------------------------------------------------------------

## 2026-11-08 --- Exportação da base completa em ZIP

### Decisão

-   Empacotar a base inteira em um ZIP único para backup e
    compartilhamento, gerado sob demanda a partir do banco local.

### Arquivos alterados

-   `f1dc/export.py` (novo), `app.py`, `tests/test_export.py` (novo),
    `docs/CHANGELOG.md` e `README.md`.

### O que foi implementado

-   Pacote ZIP com `base_f1.db`, 9 CSVs (calendário, corridas,
    classificação, sprints, standings de pilotos e construtores, pilotos,
    equipes e circuitos), `validacao.json` e `LEIA-ME.txt`.
-   CSVs com separador `;`, decimal `,` e UTF-8 com BOM, para abrir
    direto no Excel em português.
-   Geração em memória com cache por assinatura do banco e botão
    **Baixar base completa (ZIP)** na aba Qualidade dos dados.
-   LEIA-ME com fonte, resumo (temporadas, GPs, linhas) e observações
    metodológicas.

### Testes realizados

-   24 testes automatizados passando (2 novos em
    `tests/test_export.py`).
-   Exportação real: **396 KB**, 12 arquivos, 114 GPs, 2.278 resultados
    de corrida e 480 de sprint.
-   `AppTest`: zero exceções e 9 botões de download, incluindo o ZIP.

### Problemas conhecidos

-   O ZIP é remontado quando o banco muda (cache invalidado pela
    assinatura); em bases futuras muito maiores o tempo de geração pode
    crescer.

### Próxima ação

-   Comparação livre entre pilotos de equipes diferentes na aba Pilotos
    (se desejado).

------------------------------------------------------------------------

## 2026-11-08 --- Comparação livre entre pilotos na aba Pilotos

### Decisão

-   Permitir comparar o piloto selecionado com **qualquer outro piloto
    da temporada**, independentemente da equipe, complementando o H2H
    com companheiros de equipe.

### Arquivos alterados

-   `app.py`, `tests/test_app_smoke.py`, `docs/CHANGELOG.md` e
    `README.md`.

### O que foi implementado

-   Seletor **Comparar com** com todos os outros pilotos da temporada,
    exibindo nome e equipe.
-   Tabela comparativa com pontos, vitórias, pódios, poles, abandonos e
    H2H de classificação e corrida.
-   Gráfico de pontos acumulados dos dois pilotos e exportação CSV da
    comparação.
-   Helper `driver_comparison_frame` unifica a tabela do companheiro de
    equipe e a da comparação livre.

### Testes realizados

-   26 testes automatizados passando (2 novos de `AppTest`: troca do
    piloto comparado e piloto com mais de um companheiro de equipe).
-   Navegador: seção visível na aba Pilotos, com 3 tabelas e 2 gráficos,
    sem erros no console.
-   Amostras de 2025: Verstappen x Norris 421 x 423 (H2H de
    classificação 11x13); Hamilton x Leclerc 156 x 242 (H2H de
    classificação 5x19).

### Problemas conhecidos

-   A comparação usa a temporada selecionada na barra lateral; o duelo
    de todo o período continua na aba Histórico.
-   Ao trocar o piloto principal, o seletor **Comparar com** pode voltar
    à primeira opção (comportamento padrão do Streamlit).

### Próxima ação

-   Nenhuma pendência; revisar textos e visual conforme o uso.

------------------------------------------------------------------------

## 2026-11-09 --- Base ampliada para 2016-2020

### Decisão

-   Ampliar o período histórico de 2021-2025 para **2016-2025**, mantendo a
    importação por GP e a validação contra fontes oficiais.

### Arquivos alterados

-   `f1dc/config.py`, `f1dc/validate.py`, `app.py`, `f1dc/export.py`,
    `README.md` e `docs/PROJETO_F1.md`.

### O que foi implementado

-   Importação de 2016, 2017, 2018, 2019 e 2020: **100 GPs** e 224
    requisições, status `ok`.
-   Base passou a ter **214 GPs** (2016-2025), com 0 sprints em 2016-2020.
-   Rótulos e totais do período passaram a ser calculados a partir das
    temporadas configuradas, em vez de valores fixos.
-   Ajuste oficial documentado: Racing Point perdeu 15 pontos no campeonato
    de construtores de 2020 (dutos de freio); os pilotos não perderam pontos.

### Testes realizados

-   Validação: **16/16 checagens aprovadas**, com 13 notas de ausências
    reais da fonte (11 casos de piloto sem linha na classificação, 1 ajuste
    de construtores e 1 corrida sem volta mais rápida).
-   Campeões conferidos: Rosberg 2016; Hamilton 2017-2020.

### Problemas conhecidos

-   A API pública continua aplicando HTTP 429; a importação é feita por GP e
    com ritmo adaptativo.

### Próxima ação

-   Criar o ranking acumulado do período carregado.

------------------------------------------------------------------------

## 2026-11-09 --- Ranking acumulado de pilotos

### Decisão

-   Criar a aba **🥇 Ranking** com top 10 por vitórias, pódios, corridas,
    poles, voltas rápidas, títulos e pontos.
-   O ranking deriva de todas as temporadas carregadas, então novas
    importações (como 2000-2015) ampliam a lista automaticamente.

### Arquivos alterados

-   `f1dc/data.py`, `app.py`, `tests/test_data.py`,
    `tests/test_app_smoke.py`, `README.md` e `docs/CHANGELOG.md`.

### O que foi implementado

-   `period_driver_rankings` passou a retornar também `titles` e `teams`.
-   Seletor de métrica, tabela top 10, gráfico de barras, resumo dos líderes
    e exportação CSV.
-   Ranking usa apenas corridas principais: sprints não contam como GP nem
    como vitória; pontos somam corridas + sprints.

### Testes realizados

-   28 testes automatizados passando antes da entrada de 2026.
-   Amostras conferidas: Verstappen 71 vitórias e 4 títulos; Hamilton 62
    vitórias e 58 poles; Rosberg 9 vitórias e 1 título no período.

### Problemas conhecidos

-   Pontos não são normalizados entre eras de pontuação diferentes; a
    comparação é histórica, não uma média por temporada.

### Próxima ação

-   Adicionar 2026 em modo "em andamento".

------------------------------------------------------------------------

## 2026-11-09 --- Temporada 2026 em andamento

### Decisão

-   Importar 2026 em modo parcial: somente etapas com resultado na fonte,
    sem campeão e sem total fixo de GPs.
-   A classificação de 2026 é a **posição atual**, não a final; o líder não
    conta como título no ranking.

### Arquivos alterados

-   `f1dc/config.py`, `f1dc/ingest.py`, `f1dc/validate.py`, `f1dc/data.py`,
    `f1dc/export.py`, `app.py`, `tests/test_data.py`, `tests/test_ingest.py`,
    `tests/test_export.py`, `tests/test_app_smoke.py`, `README.md`,
    `docs/PROJETO_F1.md` e `docs/CHANGELOG.md`.

### O que foi implementado

-   `IN_PROGRESS_SEASONS = {2026}` e calendário previsto de 23 GPs.
-   Importação ignora rodadas sem resultado e grava apenas as concluídas.
-   Campos de campeão ficam vazios em 2026; a validação não exige campeão
    nem quantidade fixa de GPs.
-   Cabeçalho mostra **Líder do campeonato** e **Líder de construtores**;
    abas Campeonato, Pilotos e Ranking indicam que a temporada é atual.
-   `champions_timeline` exclui temporadas em andamento; títulos do ranking
    contam apenas temporadas encerradas.
-   LEIA-ME do ZIP identifica temporadas encerradas e em andamento.

### Testes realizados

-   Importação real de 2026: **20 de 23 GPs**, 440 resultados, 435 linhas de
    classificação, 132 linhas de sprint, 54 requisições, status `ok`.
-   Validação: **16/16 checagens aprovadas**, com 16 notas; líder atual
    Andrea Kimi Antonelli / Mercedes, sem campeão definido.
-   **32 testes automatizados passando** (novos testes de importação
    parcial, ranking sem título, LEIA-ME e smoke test de 2026).

### Problemas conhecidos

-   A fonte tem ausências pontuais de classificação em 2026 (R1 Verstappen e
    R14 Bearman); elas são documentadas, não preenchidas.
-   Ao encerrar a temporada, é preciso remover 2026 de
    `IN_PROGRESS_SEASONS`, reimportar e validar os campeões.

### Próxima ação

-   Importar 2000-2015 aos poucos; o ranking se amplia automaticamente.

------------------------------------------------------------------------

## 2026-11-09 --- Base ampliada para 2010-2015 e títulos matemáticos

### Decisão

-   Ampliar o período histórico para **2010-2025** (encerradas) mais 2026
    em andamento.
-   Reconhecer os títulos já garantidos matematicamente em 2026: Antonelli
    (pilotos) e Mercedes (construtores). A temporada continua em andamento.

### Arquivos alterados

-   `f1dc/config.py`, `f1dc/data.py`, `f1dc/validate.py`, `f1dc/export.py`,
    `app.py`, `tests/test_data.py`, `tests/test_export.py`,
    `tests/test_app_smoke.py`, `README.md`, `docs/PROJETO_F1.md` e
    `docs/CHANGELOG.md`.

### O que foi implementado

-   Importação de 2010, 2011, 2012, 2013, 2014 e 2015: **115 GPs**.
-   Campeões esperados cadastrados: Vettel/Red Bull (2010-2013),
    Hamilton/Mercedes (2014-2015).
-   `IN_PROGRESS_CALENDAR_SPRINTS` e `CLINCHED_CHAMPIONS` no config.
-   Validação nova confere a conta do título matemático: vantagem maior que
    o máximo de pontos ainda disponível (corridas restantes x 25 por piloto,
    x 43 por equipe, mais sprints restantes).
-   Ranking conta o título matemático; o Histórico mostra a temporada em
    andamento com o status "Matemático (em andamento)".
-   LEIA-ME do ZIP identifica os títulos matemáticos de 2026.

### Testes realizados

-   Importação real de 2010-2015: **115 GPs**, 258 requisições, status `ok`,
    campeões Vettel/Red Bull (2010-2013) e Hamilton/Mercedes (2014-2015).
-   Validação: **17/17 checagens aprovadas**, incluindo a reconciliação de
    pontos de 2014 com a pontuação dobrada de Abu Dhabi.
-   **35 testes automatizados passando**.
-   Ranking 2010-2026: Hamilton 95 vitórias/6 títulos; Verstappen 74/4;
    Vettel 48/4; Antonelli 9/1 (título matemático de 2026).

### Problemas conhecidos

-   A fonte pode não trazer volta mais rápida em alguns GPs antigos; a
    ausência é documentada, nunca preenchida.
-   Ao encerrar 2026, remover o ano de `IN_PROGRESS_SEASONS` e de
    `CLINCHED_CHAMPIONS`, reimportar e validar os campeões oficiais.

### Próxima ação

-   Conferir a validação completa e o dashboard com 2010-2026.

------------------------------------------------------------------------

## 2026-11-10 --- Base ampliada para 2006-2009, pódios/poles e McLaren 2007

### Decisão

-   Ampliar o período histórico para **2006-2025** (encerradas) mais 2026
    em andamento.
-   Exibir **pódios** e **poles** na classificação de pilotos e de
    construtores, além de pontos e vitórias.
-   Tratar a **McLaren excluída do campeonato de construtores de 2007**
    como caso oficial, sem tentar reconciliar a soma dos resultados com o
    standings (posição nula, 0 pontos).

### Arquivos alterados

-   `f1dc/config.py`, `f1dc/data.py`, `f1dc/validate.py`, `app.py`,
    `tests/test_data.py`, `README.md`, `docs/PROJETO_F1.md` e
    `docs/CHANGELOG.md`.

### O que foi implementado

-   Importação de 2006, 2007, 2008 e 2009: **70 GPs** (18 + 17 + 18 + 17).
-   Campeões esperados: Alonso/Renault (2006), Räikkönen/Ferrari (2007),
    Hamilton/Ferrari (2008, campeão de pilotos pela McLaren e Ferrari
    campeã de construtores) e Button/Brawn (2009).
-   `EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS` documenta a McLaren em 2007; a
    validação ignora apenas essa equipe na reconciliação e informa o motivo.
-   Colunas **Pódios** e **Poles** nas classificações de pilotos e equipes;
    pódios contam apenas corridas principais classificadas e poles são o P1
    do qualifying (sprints ficam separadas).
-   Barras de rolagem laterais visíveis nas abas e tabelas largas; aviso
    quando uma equipe aparece sem posição por exclusão oficial.
-   Nota fixa no Campeonato, Histórico e Ranking: até 2009 o vencedor
    ganhava 10 pontos; a partir de 2010, 25 (Top 10). A soma de pontos não
    é normalizada entre eras; exceções como Abu Dhabi 2014 em dobro vêm da
    fonte oficial.
-   Nota no Histórico explicando que a "Equipe campeã" é o campeonato de
    construtores e pode diferir da equipe do campeão de pilotos.

### Testes realizados

-   Importação real de 2006-2009: **70 GPs**, 160 requisições, status `ok`.
-   Validação: **17/17 checagens aprovadas**, com a reconciliação de pontos
    de 2006-2009 e a exclusão da McLaren em 2007.
-   **37 testes automatizados passando** (2 novos para pódios/poles).
-   Ranking 2006-2026: Hamilton 106 vitórias/7 títulos; Verstappen 74/4;
    Vettel 53/4; Alonso 24/1; Button 15/1; Räikkönen 12/1.
-   ZIP regenerado: `f1_data_center_2006_2026.zip` (~1.395 KB).

### Problemas conhecidos

-   A fonte pode não trazer volta mais rápida em alguns GPs antigos; a
    ausência é documentada, nunca preenchida.
-   Em 2007 a McLaren aparece sem posição e com 0 pontos nos construtores
    porque foi excluída pela fonte oficial; pódios e poles de pista
    continuam sendo exibidos.
-   Ao encerrar 2026, remover o ano de `IN_PROGRESS_SEASONS` e de
    `CLINCHED_CHAMPIONS`, reimportar e validar os campeões oficiais.

### Próxima ação

-   Conferir o dashboard com 2006-2026 e, se desejado, importar 2000-2005.

------------------------------------------------------------------------

## 2026-11-10 --- 2000-2001 e fonte complementar da Wikipédia

### Decisão

-   Ampliar a base para **2000-2026** começando por **2000-2001**, para
    conferir a qualidade dos dados antigos antes de seguir.
-   A Jolpica/Ergast não traz qualifying completo antes de 2003 nem volta
    mais rápida antes de 2004. Para 2000-2001, pole e volta rápida foram
    complementadas pela **Wikipédia em português**, com URL e data.
-   Nenhum dado da fonte primária é sobrescrito: a Wikipédia só preenche
    lacunas, em tabela separada.

### O que foi implementado

-   Temporadas **2000 e 2001** importadas: 17 GPs e 373 resultados cada,
    campeões Michael Schumacher / Ferrari nas duas.
-   Configuração atualizada para 2000-2026 (GPs esperados, sprints e
    campeões) e textos do painel/documentação.
-   Novo módulo `f1dc/wikipedia.py` (CLI `python -m f1dc.wikipedia`), que
    lê a tabela "Grandes Prêmios" do wikitexto bruto e grava as premiações
    complementares.
-   Nova tabela `session_awards` (pole/volta rápida) com `source_url` e
    `fetched_at`; reimportação idempotente e conflito com a fonte primária
    barrado pela validação.
-   Agregações do painel passam a combinar as duas fontes, sempre dando
    prioridade à primária; rótulos e legendas indicam quando o dado veio da
    Wikipédia.
-   Validação: lacuna de classificação completa vira informativa; pole e
    volta rápida são exigidas para todos os GPs pela fonte combinada; nova
    checagem de conflitos e de rastreabilidade. Spa 2021 continua como
    ausência real documentada.
-   Exportação inclui `premios_complementares.csv` e o LEIA-ME explica a
    fonte complementar.

### Testes realizados

-   Validação: **19/19 checagens aprovadas**, incluindo 68 prêmios
    complementares sem conflito com a fonte primária.
-   Importação 2000-2001: 76 requisições, status `ok`.
-   **41 testes automatizados passando** (4 novos para o parser, o
    importador e a prioridade da fonte primária).
-   Ranking 2000-2026: Hamilton 106 vitórias/7 títulos; Verstappen 74/4;
    Vettel 53/4; M. Schumacher 25/2; Alonso 24/1.
-   ZIP regenerado: `f1_data_center_2000_2026.zip` (~1.458 KB).

### Problemas conhecidos

-   A classificação completa de 2000-2001 continua ausente na fonte; apenas
    a pole é conhecida. O painel informa isso no GP, sem inventar grid.
-   Fonte complementar é editável por natureza; por isso cada linha guarda
    URL e data e a validação compara com a fonte primária quando ambas
    existem.
-   Ao reimportar uma temporada antiga com `f1dc.ingest`, rode novamente o
    `f1dc.wikipedia` para repor os prêmios complementares.

### Próxima ação

-   Conferir o painel com 2000-2026 e decidir se vale importar 2002-2005
    (2002 tem qualifying incompleto; 2003 tem poles, mas não voltas
    rápidas; 2004 em diante está completo na fonte).

------------------------------------------------------------------------

## 2026-11-10 --- Base completa 2000-2026 com 2002-2005

### Decisão

-   Fechar o período histórico com a importação de **2002, 2003, 2004 e
    2005**, completando **2000-2025** (encerradas) mais **2026 em
    andamento**.
-   Manter a regra de integridade: a Wikipédia só preenche lacunas; a
    fonte primária sempre tem prioridade e nenhum dado é inventado.

### Arquivos alterados

-   `f1dc/config.py`, `f1dc/wikipedia.py`, `f1dc/validate.py`,
    `f1dc/data.py`, `app.py`, `tests/test_wikipedia.py`, `README.md`,
    `docs/PROJETO_F1.md` e `docs/CHANGELOG.md`.

### O que foi implementado

-   Temporadas 2002-2005 importadas: **70 GPs** (17 + 16 + 18 + 19), 160
    requisições, status `ok`. A base passou a ter **523 GPs em 27
    temporadas**.
-   Campeões cadastrados e conferidos: M. Schumacher/Ferrari (2002, 2003
    e 2004) e Alonso/Renault (2005).
-   Parser da Wikipédia agora localiza a tabela **pelos cabeçalhos**
    (Grande Prêmio, Pole Position, Volta mais rápida, Vencedor, Equipe), em
    vez da primeira menção ao título da seção. Isso evita a tabela de
    legenda que aparece antes da tabela real em 2005.
-   Importador da Wikipédia passou a gravar **somente prêmios ausentes na
    fonte primária**. Não há mais cópia nem conflito quando a fonte
    primária já possui o dado.
-   Alias `"rubens barrichelo" -> barrichello` para a grafia usada na
    página de 2004.
-   Complementos resultantes: 2002 com 15 poles e 17 voltas rápidas; 2003
    com 0 poles e 16 voltas rápidas; 2004 e 2005 com 0 (fonte primária
    completa). Total da base: **111 prêmios complementares**.

### Testes realizados

-   Validação: **19/19 checagens aprovadas**, **0 conflitos** entre
    fontes, com 111 registros complementares rastreáveis.
-   **43 testes automatizados passando**, incluindo o novo teste de que
    prêmios já presentes na fonte primária não são duplicados.
-   Ranking 2000-2026: Hamilton 106 vitórias/7 títulos; Verstappen 74/4;
    Vettel 53/4; Alonso 32/2; M. Schumacher 56/5; Räikkönen 21/1; Rosberg
    23/1; Button 15/1; Norris 14/1; Antonelli 9/1 (título matemático de
    2026).
-   ZIP regenerado: `f1_data_center_2000_2026.zip` (~1.626 KB), com 523
    GPs, 111 prêmios complementares e o relatório de validação.

### Problemas conhecidos

-   Em 2002 a fonte primária só possui qualifying completo em 2 GPs; a
    pole de cada etapa é conhecida, mas a classificação completa continua
    ausente e não é preenchida por suposição. No total, 44 GPs de
    2000-2005 não têm classificação completa na fonte.
-   Em 2004 e 2005 a fonte primária já cobre pole e volta rápida, por isso
    a Wikipédia não acrescenta nenhuma linha.
-   Ao reimportar uma temporada antiga com `f1dc.ingest`, rode novamente
    `python -m f1dc.wikipedia` para repor os prêmios complementares.
-   A volta mais rápida de Spa 2021 continua como ausência real
    documentada.

### Próxima ação

-   Conferir no painel as temporadas 2002-2005, especialmente o aviso de
    qualifying indisponível em 2002, a origem Wikipédia das voltas rápidas
    de 2003 e as colunas de pódios e poles nos standings.

------------------------------------------------------------------------

## 2026-11-10 --- Qualifying completo de 2002 (Wikipédia en)

### Decisão

-   Completar a classificação de **2002** com as páginas de cada Grande
    Prêmio da **Wikipédia em inglês**, que citam os arquivos da FIA.
-   Manter a fonte primária com prioridade: só os **15 GPs sem nenhuma
    linha de qualifying** foram preenchidos. Malásia e Japão, que já
    existiam na fonte primária, serviram apenas para conferência.

### Arquivos alterados

-   `f1dc/wikipedia_qualifying.py` (novo), `f1dc/data.py`, `app.py`,
    `tests/test_wikipedia_qualifying.py`, `tests/test_app_smoke.py`,
    `README.md`, `docs/PROJETO_F1.md` e `docs/CHANGELOG.md`.

### O que foi implementado

-   Novo importador `python -m f1dc.wikipedia_qualifying`, com parser da
    tabela de qualifying, conferência de posições/tempos, resolução de
    pilotos e equipes, `source_url` e `fetched_at` por linha, modo
    `--dry-run` e gravação atômica por temporada.
-   **2002**: 15 GPs e **315 linhas complementares**. Os 2 GPs da fonte
    primária (Malásia e Japão, 42 linhas) foram conferidos sem nenhuma
    divergência. Total: **357 linhas em 17 GPs**.
-   Tempo da sessão única guardado em `q1`; quando não há Q2/Q3, o painel
    mostra a coluna **Tempo** em vez de "Q1".
-   Pilotos **DNQ/EX não recebem posição inventada**: 7 casos ignorados
    (6 DNQ e 1 EX) e registrados no resumo da importação.
-   `award_events` diferencia a origem do qualifying (`Jolpica` x
    `Wikipédia (en)`) e o painel exibe a legenda com a URL da fonte.
-   Reimportação idempotente: linhas complementares são reconhecidas por
    `source_url` e nunca são confundidas com a fonte primária.
-   `session_awards` de 2002 passou de 32 para **17 registros**: as 15
    poles complementares foram substituídas pelo qualifying completo; as
    17 voltas rápidas continuam complementares. Total da base: **96
    prêmios complementares**.

### Testes realizados

-   Validação: **19/19 checagens aprovadas**, **0 conflitos** e 96
    registros complementares rastreáveis. Restam **29 GPs sem qualifying**
    completo (2000–2001).
-   Suíte completa: **49 testes passando**, incluindo o novo parser, a
    prioridade da fonte primária, a atomicidade em caso de divergência e
    o smoke test do painel em 2002.
-   Ranking mantido: Hamilton 106 vitórias/7 títulos; Verstappen 74/4;
    M. Schumacher 56/5; Vettel 53/4; Alonso 32/2.
-   ZIP regenerado: `f1_data_center_2000_2026.zip` (~1.637 KB), com 523
    GPs, 10.327 linhas de classificação e 96 prêmios complementares.

### Problemas conhecidos

-   **2000–2001** continuam sem classificação completa na fonte e não são
    preenchidas por suposição.
-   Em **2002 R5** Eddie Irvine foi excluído da classificação (EX) e em
    **2002 R11** Giancarlo Fisichella não se classificou (DNQ); ambos
    constam no resultado, mas não recebem posição de qualifying.
-   A Wikipédia é editável; por isso cada linha guarda URL/data e os GPs
    com fonte primária são conferidos contra ela.
-   Ao reimportar 2002 com `f1dc.ingest`, rode
    `f1dc.wikipedia_qualifying --seasons 2002` e depois
    `f1dc.wikipedia --seasons 2002`.

### Próxima ação

-   Conferir no painel o GP da Austrália de 2002 (classificação
    complementar e coluna Tempo), o aviso de pole/volta rápida e as
    colunas de pódios e poles nos standings.

------------------------------------------------------------------------

## 2026-11-11 --- Qualifying completo de 2001 (Wikipédia en)

### Decisão

-   Completar a classificação de **2001** com as páginas de cada Grande
    Prêmio da **Wikipédia em inglês**, mantendo a fonte primária com
    prioridade. Apenas o GP dos Estados Unidos (R16) já tinha qualifying na
    fonte primária; ele foi usado só para conferência.

### Arquivos alterados

-   `f1dc/wikipedia_qualifying.py`, `tests/test_wikipedia_qualifying.py`,
    `README.md`, `docs/PROJETO_F1.md` (versão 1.7) e `docs/CHANGELOG.md`.

### O que foi implementado

-   O parser passou a reconhecer o cabeçalho **`Lap`** usado nas páginas de
    2001 e a predefinição **`{{Tooltip|Grid|...}}`**, com comparação exata
    de rótulos para não confundir a coluna `Laps` da tabela de corrida.
-   **2001**: 16 GPs e **349 linhas complementares**, com `source_url` e
    `fetched_at` por linha. O GP dos EUA (22 linhas da fonte primária) foi
    conferido sem divergência. Total: **371 linhas em 17 GPs**.
-   Tempo da sessão única guardado em `q1`, com Q2/Q3 nulos.
-   **DNQ/EX não recebem posição inventada**: 3 casos ignorados — Enrique
    Bernoldi (EX, R2), Fernando Alonso (EX, R8) e Tarso Marques (DNQ, R11).
-   `SUPPORTED_SEASONS` passou a incluir **2001**; reimportar continua
    idempotente (349 linhas complementares, sem duplicar).

### Testes realizados

-   Validação: **19/19 checagens aprovadas**, **0 conflitos** em 96
    registros complementares. Restam **13 GPs sem qualifying na fonte
    primária** (2000–2001), cobertura complementar já aplicada a 2001.
-   Suíte completa: **51 testes passando**, incluindo os novos casos do
    cabeçalho `Lap`/`Tooltip Grid` e da tabela de corrida com `Laps`.
-   ZIP regenerado: `f1_data_center_2000_2026.zip` com 523 GPs, **10.676
    linhas de classificação** e 96 prêmios complementares.

### Problemas conhecidos

-   **2000** continua sem classificação completa na fonte e não é
    preenchida por suposição.
-   A Wikipédia é editável; cada linha guarda URL/data e os GPs com fonte
    primária são conferidos contra ela.
-   Ao reimportar 2001 com `f1dc.ingest`, rode
    `f1dc.wikipedia_qualifying --seasons 2001,2002` e depois
    `f1dc.wikipedia --seasons 2000,2001,2002,2003`.

### Próxima ação

-   Conferir no painel a classificação de 2001 (coluna **Tempo** e legenda
    da Wikipédia) e as contagens de poles por piloto.

------------------------------------------------------------------------

## 2026-11-11 --- Qualifying completo de 2000 (Wikipédia en)

### Decisão

-   Fechar a cobertura de qualifying de **2000** usando as páginas de cada
    Grande Prêmio da **Wikipédia em inglês**, mantendo a fonte primária com
    prioridade. Quatro GPs já tinham qualifying na fonte primária
    (R1, R3, R4 e R16); três foram conferidos e um teve divergência
    documentada.

### Arquivos alterados

-   `f1dc/wikipedia_qualifying.py`, `f1dc/export.py`,
    `tests/test_wikipedia_qualifying.py`, `tests/test_app_smoke.py`,
    `README.md`, `docs/PROJETO_F1.md` (versão 1.8) e `docs/CHANGELOG.md`.

### O que foi implementado

-   O parser passou a aceitar as tabelas de 2000 **sem coluna Grid**,
    cabeçalhos compactos com `!!` (Austrália), cabeçalho antes do primeiro
    `|-` (Japão) e as predefinições `{{sort|01|1}}` e
    `{{sortname|Nome|Sobrenome}}`.
-   **2000**: 13 GPs e **285 linhas complementares**, com `source_url` e
    `fetched_at` por linha. R1, R4 e R16 (66 linhas primárias) foram
    conferidos sem divergência. Total: **373 linhas em 17 GPs**.
-   **Divergência conhecida em R3 (San Marino)**: a fonte primária repete o
    tempo de Ralf Schumacher para Barrichello (1:25.871); a Wikipédia e a
    formula1.com registram **1:25.242**. O valor da fonte primária foi
    mantido, com exceção documentada em `PRIMARY_DIVERGENCE_EXCEPTIONS`.
    A divergência vira aviso e não bloqueia os demais GPs.
-   **Nick Heidfeld (R6, European GP)** foi excluído (EX) da classificação e
    não recebeu posição inventada.
-   `SUPPORTED_SEASONS` passou a incluir **2000**; reimportar continua
    idempotente (285 linhas complementares, sem duplicar).
-   A cobertura de qualifying agora é **completa em todos os 523 GPs**.

### Testes realizados

-   Validação: **19/19 checagens aprovadas**, **0 conflitos** em 96
    registros complementares, e a checagem de cobertura agora informa
    **"Nenhum GP sem classificação"**.
-   Suíte completa: **54 testes passando**, incluindo o formato compacto de
    2000, a exceção de divergência e o smoke test do painel em 2000.
-   Poles de 2000 conferidas: M. Schumacher 9, Häkkinen 5, Coulthard 2,
    Barrichello 1 (total 17).
-   ZIP regenerado: `f1_data_center_2000_2026.zip` (~1.668 KB), com 523 GPs,
    **10.961 linhas de classificação** e 96 prêmios complementares.

### Problemas conhecidos

-   **2000 R3**: valor de tempo de Barrichello mantido da fonte primária
    (1:25.871), diferente da Wikipédia/formula1.com (1:25.242); exceção
    documentada no código e no README.
-   A Wikipédia é editável; cada linha guarda URL/data e os GPs com fonte
    primária são conferidos contra ela.
-   Ao reimportar 2000–2002 com `f1dc.ingest`, rode
    `f1dc.wikipedia_qualifying --seasons 2000,2001,2002` e depois
    `f1dc.wikipedia --seasons 2000,2001,2002,2003`.

### Próxima ação

-   Conferir no painel a classificação de 2000 (coluna **Tempo** e legenda
    da Wikipédia) e a cobertura completa na aba Qualidade dos dados.

------------------------------------------------------------------------

## 2026-11-11 --- Rotina de fim de semana de corrida (testada)

### Decisão

-   Documentar no README a rotina de atualização usada depois de cada GP da
    temporada em andamento (2026) e validar o comando antes de documentá-lo,
    rodando-o contra uma **cópia** do banco para não tocar na base real.

### Arquivos alterados

-   `README.md` (nova seção "Rotina depois de cada GP" e linha na tabela de
    comandos úteis) e `docs/CHANGELOG.md`.

### O que foi implementado

-   A rotina documentada é:
    `f1dc.ingest --seasons 2026` seguido de `f1dc.validate`, com reinício do
    painel em seguida.
-   O README explica que etapas futuras são ignoradas com o aviso
    `sem resultado na fonte; etapa ainda não realizada, ignorada`, que a
    importação não duplica registros e que reimportar 2000--2003 exige rodar
    de novo os complementos da Wikipédia.

### Testes realizados

-   Comando executado com `--db` apontando para uma cópia de `data/f1.db`:
    status **ok**, **54 requisições HTTP**, **20 GPs** gravados e as 3 etapas
    futuras (Las Vegas, Qatar e Abu Dhabi) ignoradas com aviso.
-   Comparação cópia × base real: todas as tabelas com contagens idênticas
    (523 GPs, 10.990 resultados, 10.961 classificações, 612 sprints, 644 e 287
    linhas de standings) e **0 duplicatas** de qualifying em 2026.
-   A base real não foi alterada (última gravação anterior ao teste mantida) e
    a cópia temporária foi removida.

### Problemas conhecidos

-   O resumo do CLI mostra `campeão: — / —` em temporada em andamento por
    decisão do projeto (há líder, não campeão); o painel exibe Antonelli e
    Mercedes por causa de `CLINCHED_CHAMPIONS`.

### Próxima ação

-   Depois do GP de Las Vegas (22/11/2026), rodar a rotina e conferir o painel.

------------------------------------------------------------------------

## 2026-11-11 --- Circuito onde cada piloto mais venceu e top 10 do século

### Decisão

-   Mostrar no painel o **circuito onde cada piloto mais venceu** e os
    **10 maiores vencedores desde 2000**, com empates explícitos e sem
    escolher um circuito "no chute". Tudo é calculado sobre a base local
    (2000--2026), sem importação nova.

### Arquivos alterados

-   `f1dc/data.py` (novas funções), `app.py` (abas Ranking, Pilotos e
    Histórico), `tests/test_data.py` (8 testes novos), `README.md`,
    `docs/PROJETO_F1.md` (versão 1.9) e `docs/CHANGELOG.md`.

### O que foi implementado

-   `driver_circuit_stats`: largadas, vitórias e aproveitamento (%) por
    circuito, contando apenas corridas principais e pilotos classificados
    (P1 desclassificado não vira vitória).
-   `favorite_circuit`: circuito com mais vitórias do piloto; em caso de
    empate devolve todos os empatados (ordem alfabética) para exibição
    transparente.
-   `period_top_winners`: top 10 por vitórias com corridas, % vitórias e
    circuito favorito; desempate por pódios e corridas.
-   `circuit_top_winners`: top 5 de quem mais venceu em cada traçado.
-   **Ranking**: seção "Maiores vencedores do século --- top 10 (desde 2000)"
    com Títulos, Vitórias, Corridas, % vitórias, circuito onde mais venceu e
    Equipe(s); empates aparecem com `*` e nota de rodapé.
-   **Pilotos**: seção "Onde ele mais venceu (carreira 2000--2026)" com
    circuito, vitórias, total de circuitos com vitória e tabela expansível por
    circuito.
-   **Histórico**: "Top 5 que mais venceram neste circuito" com % de
    aproveitamento, ao lado das edições do circuito já existentes.
-   A contagem é **por traçado** (`circuit_id`), não por nome de GP, e
    **sprints não contam** como vitória.

### Testes realizados

-   8 testes novos cobrindo vitórias por circuito, P1 desclassificado,
    empates, top 10 e top 5, além de casos sem vitória/circuito inexistente.
-   Conferência com dados reais: Hamilton 106 vitórias (Silverstone 9),
    Verstappen 74 (Hermanos Rodríguez 6), M. Schumacher 56 (Imola 5, empate
    com Indianápolis), Massa 11 (Istanbul Park 3; Interlagos 2, em 2006 e
    2008), Interlagos com Hamilton, Vettel e Verstappen empatados em 3.
-   Painel aberto via AppTest sem exceções, com as três seções renderizando.

### Problemas conhecidos

-   O rótulo "século" significa **desde 2000**, início da base; resultados
    anteriores a 2000 não entram.
-   Em empates, o circuito exibido como principal é o primeiro em ordem
    alfabética; todos os empatados são listados na nota/tabela.

### Próxima ação

-   Conferir visualmente as três seções e, se quiser, revisar a decisão da
    divergência de Barrichello em San Marino 2000.

------------------------------------------------------------------------

## 2026-11-12 --- Circuitos fora do calendário atual (aba Histórico)

### Decisão

-   Mostrar os circuitos que **não recebem GP na temporada atual** com
    última edição, número de edições e maior vencedor, **calculados** a
    partir do calendário importado. Não existe lista manual: quando uma
    temporada nova é importada, a lista se ajusta sozinha.
-   O painel **não prevê calendário futuro**. Ausência de uma temporada pode
    ser rotação (Barcelona e Spa a partir de 2027) e não extinção, então a
    nota da tela diz isso explicitamente em vez de afirmar "extinto".

### Arquivos alterados

-   `f1dc/data.py` (`inactive_circuits`), `app.py` (nova seção na aba
    Histórico), `tests/test_data.py` (4 testes novos), `README.md`,
    `docs/PROJETO_F1.md` (versão 2.0) e `docs/CHANGELOG.md`.

### O que foi implementado

-   `inactive_circuits(frames, reference_season=None, min_seasons_absent=1)`:
    uma linha por traçado fora do calendário da temporada de referência
    (padrão: última temporada da base), com `first_season`, `last_season`,
    `editions`, `seasons_absent`, `last_race_name`, `biggest_winner`,
    `biggest_wins` e `tied`.
-   Maior vencedor contado por `circuit_id` (não por nome de GP), com
    **empates listados** e P1 desclassificado fora da conta.
-   **Temporada em andamento:** como as etapas futuras não são importadas,
    a tela exige `min_seasons_absent=2` para não marcar como ausente um
    circuito que ainda vai receber corrida. A nota da tela explica a regra.
-   Tabela com Circuito, País, Último GP, Estreia, Última edição, Edições,
    "Ausente há" e Maior vencedor, além de CSV para download.

### Testes realizados

-   4 testes novos: circuito que saiu, circuito que voltou ao calendário
    (ignorado), empate de vitórias no maior vencedor, regra de 2 temporadas
    e base vazia. `tests/test_data.py`: 25 passando.
-   Conferência com dados reais (2026 em andamento): 13 traçados listados,
    de Paul Ricard (2022) a Indianápolis (2007), com destaque para Istanbul
    Park (Massa, 3) e Mugello (1 edição).
-   Painel aberto via AppTest sem exceções, com a tabela e o CSV renderizando.

### Problemas conhecidos

-   Com a temporada em andamento, circuitos cuja última edição foi a
    temporada anterior (Imola, Bahrein, Jeddah em 2026) só entram na lista
    quando a temporada seguinte for importada. É o preço de não inventar
    calendário.
-   "Ausente há" é diferença de temporadas, não de anos civis.

### Próxima ação

-   Depois de Abu Dhabi, reimportar 2026: a lista passa a incluir
    automaticamente Imola, Bahrein e Jeddah.

------------------------------------------------------------------------

## 2026-11-19 --- Extensão histórica para 1995–1999

### Decisão

-   Atender ao pedido do usuário de ampliar a base para **1995 a 1999**,
    mantendo a regra de prioridade da fonte primária (Jolpica) e a
    complementação via Wikipédia apenas onde a primária tem lacuna.
-   "Século" continua sendo, por definição do painel, o recorte **desde 2000**:
    a seção de maiores vencedores do século não inclui 1995–1999, embora o
    ranking acumulado geral passe a incluí-los.

### Arquivos alterados

-   `f1dc/config.py` (1995–1999 em `SEASONS`, `EXPECTED_RACES`,
    `EXPECTED_SPRINTS` e `EXPECTED_CHAMPIONS`), `f1dc/__init__.py` (1.3.0),
    `f1dc/wikipedia_qualifying.py`, `f1dc/export.py`, `app.py`, `README.md`,
    `docs/PROJETO_F1.md`, `data/f1.db` e `data/validation_report.json`.

### O que foi implementado

-   Importação de 1995 (17 GPs, qualifying completo na primária) e de
    1996–1999 (16/17/16/16 GPs) pela Jolpica, com campeões oficiais
    conferidos: 1995 Schumacher/Benetton, 1996 Hill/Williams, 1997
    Villeneuve/Williams, 1998 Häkkinen/McLaren e 1999 Häkkinen/Ferrari.
-   Poles e voltas rápidas de 1995–1999 complementadas pela Wikipédia (pt),
    com `source_url` e `fetched_at`.
-   Qualifying de 1996–1999 complementado pela Wikipédia (en): 9, 7, 9 e 13
    GPs preenchidos, respectivamente. O parser passou a aceitar o cabeçalho
    `Lap Time` (1998), posições anotadas com `*` (1997 Bélgica) e tempo em
    branco em posições que não a pole (1996 França), gravando `NULL` sem
    inventar valor.
-   Divergências pontuais conhecidas registradas com justificativa e fonte:
    1997 R2/R3/R8/R9, 1998 R3 e 1999 R2 (além da já existente em 2000 R3).
    A fonte primária é sempre mantida nesses GPs.
-   Rótulos e documentação atualizados de "2000–2026" para "1995–2026"; a base
    passa a ter **32 temporadas e 605 GPs** (585 encerrados + 20 de 2026),
    12.808 resultados, 12.778 classificações, 612 sprints, 187 prêmios e 44
    circuitos.

### Testes realizados

-   `python -m f1dc.validate`: **APROVADO** (19/19).
-   `python -m pytest -q`: **66 testes passando**.
-   Dry run do importador de qualifying para 1996–1999: `status=ok` nas
    quatro temporadas, com as divergências conhecidas sinalizadas como aviso.
-   AppTest sem exceções com a temporada 1995 selecionada; campeões e
    standings conferidos na base.

### Problemas conhecidos

-   Ainda faltam Las Vegas (22/11), Qatar (29/11) e Abu Dhabi (06/12) em 2026.
-   A divergência de nome "Barcelona Grand Prix" (base) × "Barcelona-Catalunya
    Grand Prix" (oficial) segue pendente de registro.

### Próxima ação

-   Regenerar o ZIP com o novo período e publicar; depois de Las Vegas,
    reimportar 2026 e validar novamente.

------------------------------------------------------------------------

## 2026-11-20 --- Atualização automática das etapas restantes de 2026

-   **Decisão:** Programar as três etapas finais (Las Vegas, Qatar e Abu
    Dhabi) no Agendador de Tarefas do Windows, com espera pelo resultado na
    Jolpica em vez de horário fixo. O encerramento oficial de 2026 continua
    manual, para não publicar campeão antes da conferência externa.
-   **Arquivos alterados:** `scripts/update_season.py` (novo), `README.md`,
    `docs/CHANGELOG.md`.
-   **O que foi implementado:**
    -   script idempotente que espera o resultado do GP na API (15 em 15
        minutos, até 6 horas), recusa pular etapa anterior sem resultado,
        reimporta 2026, valida a base, faz `wal_checkpoint(TRUNCATE)` e só
        então commita/pusha `f1.db` + `validation_report.json`;
    -   barreira extra: aborta se a importação reduzir o número de GPs;
    -   log em `logs/update_season.log`;
    -   tarefas `Atualiza2026-R21-LasVegas` (23/11 09:00),
        `Atualiza2026-R22-Qatar` (29/11 16:00) e
        `Atualiza2026-R23-AbuDhabi` (06/12 13:00), criadas com sucesso e
        verificadas como `Pronto`.
-   **Testes realizados:** `py_compile` do script, `python -m pytest -q`
    (66 passando), dry-run de espera confirmando que o GP 21 ainda não está
    na API e que o timeout não publica nada, consulta ao calendário 2026
    confirmando R21/R22/R23, e `/query` das três tarefas no Agendador.
-   **Problemas conhecidos:** `/rl HIGHEST` foi recusado (sem privilégio
    administrativo), então as tarefas rodam no nível padrão do usuário —
    suficiente porque banco, log e repositório estão no perfil dele. Se o PC
    estiver desligado no disparo, a tarefa não executa depois: é preciso
    rodar o script manualmente (comando no README).
-   **Próxima ação:** conferir o log após cada GP; depois de Abu Dhabi,
    remover 2026 de `IN_PROGRESS_SEASONS` e `CLINCHED_CHAMPIONS`, reimportar,
    validar, atualizar docs/ZIP e publicar.

------------------------------------------------------------------------

## 2026-11-20 --- Extensão histórica para 1990–1994

-   **Decisão:** atender ao pedido do usuário de ampliar a base agora,
    incluindo 1990–1994. Frageado sobre os "vencedores dos séculos XX e XXI",
    o usuário escolheu manter o recorte disponível com aviso: painel do
    século XX usando 1990–1999 e painel do século XXI usando 2000–2026, com
    alerta explícito de que faltam 1950–1989 para um século XX completo. Em
    1994, o campeonato de construtores oficial é da Williams (a Benetton ficou
    de fora), enquanto Schumacher é o campeão de pilotos.
-   **Arquivos alterados:** `f1dc/config.py` (temporadas, contagens,
    campeões, ajustes de pontos e exclusão de Benetton 1994),
    `f1dc/wikipedia.py`, `f1dc/wikipedia_qualifying.py`, `f1dc/validate.py`,
    `f1dc/export.py`, `f1dc/__init__.py` (1.4.0), `app.py`, `README.md`,
    `docs/PROJETO_F1.md` (2.2), `scripts/seed_wiki_entities.py` (novo) e
    testes.
-   **O que foi implementado:**
    -   importação Jolpica de 1990–1994: 80 GPs, 2.076 resultados e os
        standings oficiais; em 1990–1993 a primária não tem nenhuma linha de
        qualifying e em 1994 cobre 15 de 16 GPs;
    -   parser de qualifying da Wikipédia (en) estendido para as tabelas com
        Q1/Q2 (1990–1994), incluindo o separador malformado `|-|` de Itália
        1994 e a escolha da tabela principal quando há pré-classificação;
    -   parser da tabela de GPs da Wikipédia (pt) estendido para 1990–1992,
        onde a rodada aparece como célula e não como cabeçalho;
    -   cadastro complementar mínimo (nome, nacionalidade e URL) de Michael
        Bartels, Giovanna Amati e Coloni, que não aparecem em nenhum resultado
        da fonte primária; as linhas de qualifying gravadas levam
        `source_url`/`fetched_at`;
    -   poles e voltas rápidas de 1990–1994 complementadas pela Wikipédia
        (pt), e qualifying de 1990–1994 complementado/confirmado pela
        Wikipédia (en); divergências conhecidas em 1994 R1, R3 e R12 mantidas
        na fonte primária e documentadas;
    -   ajuste oficial de pontos de pilotos em 1990 (descarte dos piores
        resultados: Prost 71 em vez de 73 e Piquet 43 em vez de 44), aplicado
        apenas na reconciliação da validação;
    -   painel "Maiores vencedores por século" na aba Ranking, com um top 10
        para 1990–1999 (século XX, com aviso de recorte incompleto) e outro
        para 2000–2026 (século XXI), ambos calculados pela mesma função de
        ranking, com empates explícitos e download CSV separado.
-   **Testes realizados:** `python -m f1dc.validate` APROVADO (19/19),
    `python -m pytest -q` (71 passando), AppTest sem exceções e conferência
    dos campeões de 1990–1994 na base.
-   **Problemas conhecidos:** a divergência de nome "Barcelona Grand Prix"
    (base) × "Barcelona-Catalunya Grand Prix" (oficial) segue pendente de
    registro; o encerramento oficial de 2026 continua manual. Após o push,
    o Streamlit Cloud ainda exibia o rótulo antigo (2000–2026) na primeira
    conferência, indicando deploy/rebuild pendente.
-   **Próxima ação:** confirmar que o Streamlit Cloud subiu a versão 1990–2026
    com os dois painéis de século; se o serviço seguir com a versão antiga,
    solicitar ao usuário o restart manual do app (com login).

------------------------------------------------------------------------

## 2026-11-20 --- Extensão da base para 1985–1989

-   **Decisão:** atender ao pedido do usuário ("qualquer coisa ja faz de 85 a
    89.."), ampliando a base de 1990–2026 para 1985–2026.
-   **Arquivos alterados:** `f1dc/config.py`, `f1dc/wikipedia.py`,
    `f1dc/wikipedia_qualifying.py`, `f1dc/export.py`, `f1dc/__init__.py`,
    `app.py`, `README.md`, `docs/PROJETO_F1.md`,
    `scripts/seed_wiki_entities.py`, `tests/test_app_smoke.py`,
    `data/f1.db`, `data/validation_report.json` e o ZIP de exportação.
-   **O que foi implementado:**
    -   importação de 80 GPs (16 por temporada) e 2.061 resultados de
        1985–1989 via Jolpica, com standings oficiais e campeões conferidos:
        Prost/McLaren (85), Prost/Williams (86), Piquet/Williams (87),
        Senna/McLaren (88) e Prost/McLaren (89);
    -   qualifying completo de 1985–1989 (2.100 linhas em 80 GPs)
        complementado pela Wikipédia (en), com `source_url`/`fetched_at`
        por linha, mantendo DNQ/EX sem posição inventada;
    -   poles e 80 voltas rápidas complementadas pela Wikipédia (pt),
        também com proveniência;
    -   cadastro mínimo de Joachim Winkelhock (que só aparece no
        qualifying de 1989 na Wikipédia) no script de seed;
    -   ajustes oficiais de descartes de pontos em 1985–1989 (regra dos
        melhores resultados, vigente até 1990), aplicados apenas na
        reconciliação da validação, nunca nos resultados importados;
    -   painel "Maiores vencedores por século — século XX" ampliado para
        1985–1999, com aviso de recorte incompleto para 1950–1984;
    -   textos de cobertura (README, PROJETO_F1, export) atualizados para
        1985–2026 (745 GPs encerrados + etapas de 2026).
-   **Testes realizados:** `python -m f1dc.validate` APROVADO (19/19),
    `python -m pytest -q`, AppTest sem exceções.
-   **Problemas conhecidos:** a divergência de nome "Barcelona Grand Prix"
    (base) × "Barcelona-Catalunya Grand Prix" (oficial) segue pendente;
    o encerramento oficial de 2026 continua manual.
-   **Próxima ação:** publicar o commit e confirmar que o Streamlit Cloud
    subiu a versão 1985–2026 com o painel do século XX atualizado.

------------------------------------------------------------------------

## 2026-11-21 --- Extensão da base para 1980–1984

-   **Decisão:** atender ao pedido do usuário ("80 a 84 agora?"), ampliando a
    base de 1985–2026 para 1980–2026.
-   **Arquivos alterados:** `f1dc/config.py`, `f1dc/wikipedia.py`,
    `f1dc/wikipedia_qualifying.py`, `f1dc/export.py`, `f1dc/__init__.py`,
    `app.py`, `README.md`, `docs/PROJETO_F1.md`,
    `scripts/seed_wiki_entities.py`, `tests/test_app_smoke.py`,
    `data/f1.db`, `data/validation_report.json` e o ZIP de exportação.
-   **O que foi implementado:**
    -   importação de 76 GPs (14, 15, 16, 15 e 16 por temporada) e 1.897
        resultados de 1980–1984 via Jolpica, com standings oficiais e
        campeões conferidos: Jones/Williams (80), Piquet/Williams (81),
        Rosberg/Ferrari (82), Piquet/Ferrari (83) e Lauda/McLaren (84);
    -   qualifying completo de 1980–1984 (2.078 linhas em 76 GPs)
        complementado pela Wikipédia (en), com `source_url`/`fetched_at`
        por linha, mantendo DNQ/EX/DNA sem posição inventada. A Jolpica não
        retorna nenhuma linha de qualifying nesses anos;
    -   parser do qualifying aceita `Team` como sinônimo de `Constructor`
        (necessário em 3 GPs de 1980) e tempos com 2 ou 3 casas decimais;
    -   76 voltas rápidas complementadas pela Wikipédia (pt), com
        proveniência. As poles já vêm das classificações importadas;
    -   cadastro mínimo de 9 pilotos que só aparecem no qualifying desses
        anos (David Kennedy, Harald Ertl, Kevin Cogan, Giorgio Francia,
        Emilio de Villota, Stephen South e outros) no script de seed;
    -   ajustes oficiais de descartes de pontos em 1980 (Jones -4,
        Reutemann -7 — regra dos 5 melhores resultados por metade do
        campeonato), aplicados apenas na reconciliação da validação,
        nunca nos resultados importados;
    -   painel "Maiores vencedores por século — século XX" ampliado para
        1980–1999, com aviso de recorte incompleto para 1950–1979;
    -   textos de cobertura (README, PROJETO_F1, export) atualizados para
        1980–2026 (821 GPs encerrados + etapas de 2026).
-   **Testes realizados:** `python -m f1dc.validate` APROVADO (19/19),
    `python -m pytest -q`, AppTest sem exceções.
-   **Problemas conhecidos:** a divergência de nome "Barcelona Grand Prix"
    (base) × "Barcelona-Catalunya Grand Prix" (oficial) segue pendente;
    o encerramento oficial de 2026 continua manual.
-   **Próxima ação:** publicar o commit e confirmar que o Streamlit Cloud
    subiu a versão 1980–2026 com o painel do século XX atualizado.

------------------------------------------------------------------------

## 2026-11-21 --- Arruma as duas pendências: nome de GP e fechamento de 2026

-   **Decisão:** atendendo ao pedido "da pra arrumar essas pendencias?", o
    usuário escolheu (1) alias na exibição para a divergência do nome do GP
    de Barcelona e (2) script + agendamento para o encerramento oficial de
    2026. Nenhum dado foi inventado: o nome bruto continua no banco e o
    fechamento só acontece depois que a fonte primária tiver os dados finais.
-   **Arquivos alterados:** `f1dc/config.py` (`RACE_NAME_ALIASES`),
    `f1dc/data.py`, `f1dc/export.py`, `app.py`,
    `scripts/finalize_season.py` (novo), `tests/test_data.py`,
    `tests/test_finalize_season.py` (novo), `README.md`, `docs/CHANGELOG.md`.
-   **O que foi implementado:**
    -   alias de `(2026, R7)` para `Barcelona-Catalunya Grand Prix`, com URL
        oficial e data de conferência aplicados apenas em `frames` (painel e
        exportação). O CSV do calendário ganhou `race_name_source`,
        `race_name_source_url` e `race_name_verified_at`; o detalhe do GP no
        painel mostra o link da fonte oficial. O alias só é aplicado quando o
        nome bruto no banco é exatamente `Barcelona Grand Prix`.
    -   `scripts/finalize_season.py` com `--check-only`: confere na Jolpica as
        23 etapas, as 6 sprints, o resultado da R23 e standings finais no R23,
        além de confrontar os campeões com os títulos matemáticos já
        registrados. Só então altera `config.py` (2026 sai de "em andamento" e
        entra nas expectativas de temporada encerrada), reimporta, valida, faz
        `wal_checkpoint(TRUNCATE)`, commita e faz push. Backup/rollback protegem
        a base se algo falhar antes do commit; se o push falhar depois dele, o
        script mantém os arquivos e avisa.
    -   tarefa `F1DataCenter\Fecha2026` criada para 07/12/2026 13:00, com
        comando e horário verificados por `/query /xml`.
-   **Testes realizados:** `py_compile` dos arquivos alterados,
    `python -m pytest -q` (76 passando), `--check-only` contra a API real
    (bloqueou corretamente: standings ainda no R21 e sem resultado na R23),
    comparação do `config.py` resultante no teste unitário e verificação da
    tarefa no Agendador.
-   **Problemas conhecidos:** em 21/11 a temporada ainda tem 20 de 23 GPs no
    banco; o fechamento depende da publicação dos resultados finais na API. As
    tarefas do Agendador não disparam se o PC estiver desligado no horário. A
    conferência visual no Streamlit Cloud segue bloqueada por redirect/403.
-   **Próxima ação:** acompanhar as tarefas R21–R23, conferir o log de
    `finalize_season.py` em 07/12, regenerar o ZIP com a temporada encerrada e
    pedir ao usuário que confirme visualmente o deploy.

------------------------------------------------------------------------

## 2026-11-21 --- Grava o nome oficial de Barcelona no banco

-   **Decisão:** a confirmação visual mostrou que o Streamlit Cloud ainda servia
    o código antigo e o dropdown exibia `Barcelona Grand Prix`. Para que o nome
    correto apareça independentemente do redeploy, a correção passou a ser
    gravada no próprio SQLite e reaplicada nas reimportações de 2026.
-   **Arquivos alterados:** `f1dc/config.py` (`official_race_name`),
    `f1dc/transform.py`, `f1dc/data.py`, `f1dc/export.py`,
    `tests/test_transform.py`, `tests/test_data.py`, `README.md`,
    `docs/CHANGELOG.md`, `data/f1.db`.
-   **O que foi implementado:**
    -   `config.official_race_name()` substitui o nome da primária pelo oficial
        somente em `(2026, R7)` e somente quando a primária trouxer
        `Barcelona Grand Prix`. `transform.race_row()` usa essa função, então a
        reimportação de 2026 não devolve o nome antigo.
    -   `apply_race_name_aliases()` continua preenchendo `race_name_source`,
        `race_name_source_url` e `race_name_verified_at`, agora tanto para o
        banco antigo (nome bruto) quanto para o banco já corrigido. O
        `LEIA-ME.txt` do ZIP foi ajustado para descrever a correção gravada no
        banco, sem afirmar que o nome bruto permanece lá.
    -   linha de `(2026, R7)` do banco publicado atualizada para
        `Barcelona-Catalunya Grand Prix`, com `wal_checkpoint(TRUNCATE)`.
-   **Testes realizados:** casos novos para `race_row()` e para a proveniência
    com o nome já gravado; suíte completa e validação da base a registrar abaixo.
-   **Problemas conhecidos:** se o processo do app estiver com cache antigo, o
    nome gravado no banco exige uma nova sessão (ou reboot) para aparecer.
-   **Próxima ação:** publicar, recarregar o app sem cache e conferir o dropdown.

------------------------------------------------------------------------

## 2026-11-22 --- Importa Las Vegas (R21) de 2026

-   **Decisão:** o usuário avisou que a corrida de Las Vegas já tinha ocorrido.
    A Jolpica já trazia o resultado e os standings no R21, então a importação
    foi feita imediatamente, sem esperar a tarefa agendada para 23/11. Isso
    evita também uma segunda rodada de requisições no dia seguinte.
-   **Arquivos alterados:** `data/f1.db`, `data/validation_report.json`,
    `README.md`, `docs/CHANGELOG.md`.
-   **O que foi implementado:**
    -   `f1dc.ingest --seasons 2026`: 21 GPs gravados, 462 resultados, 457
        classificações e 132 linhas de sprint, com 55 requisições HTTP e status
        `ok`. R22 (Qatar) e R23 (Abu Dhabi) seguem sem resultado na fonte e
        foram ignoradas, como previsto para temporada em andamento.
    -   R21: vencedor Max Verstappen (Red Bull), pole de Andrea Kimi Antonelli
        (P1 do qualifying, distinto do grid efetivo) e volta rápida de Liam
        Lawson — todos lidos da primária, sem inferência de penalidades.
    -   tarefa `Atualiza2026-R21-LasVegas` removida do Agendador por ter se
        tornado redundante. Permanecem `Atualiza2026-R22-Qatar`,
        `Atualiza2026-R23-AbuDhabi` e `Fecha2026`.
    -   o nome oficial de Barcelona continuou gravado no banco após a
        reimportação, confirmando a correção feita em 21/11.
-   **Testes realizados:** validação da base `APROVADO` (19/19 checagens),
    `pytest -q` com **79 passed**, `wal_checkpoint(TRUNCATE)` com `(0, 0, 0)`
    e ZIP regenerado.
-   **Problemas conhecidos:** 2026 segue em andamento com 21 de 23 GPs; o
    fechamento depende da publicação dos resultados finais de R23 na API.
-   **Próxima ação:** acompanhar R22 (29/11) e R23 (06/12) e conferir o
    `Fecha2026` em 07/12.

------------------------------------------------------------------------

## 2026-11-23 --- Extensão da base para 1975–1979

-   **Decisão:** atender ao pedido do usuário de encerrar o dia com a base a
    partir de 1975 ("acho que vou parar em 75 talvez"), mantendo 2026 em
    andamento. A faixa 1970–1974 ficou como possibilidade futura, não executada.
-   **Arquivos alterados:** `f1dc/config.py`, `f1dc/wikipedia_qualifying.py`,
    `f1dc/wikipedia.py`, `f1dc/export.py`, `f1dc/__init__.py`, `app.py`,
    `README.md`, `docs/PROJETO_F1.md`, `scripts/seed_wiki_entities.py`,
    `tests/test_app_smoke.py`, `data/f1.db`, `data/validation_report.json` e o
    ZIP de exportação.
-   **O que foi implementado:**
    -   importação via Jolpica de 78 GPs (14, 16, 17, 16 e 15 por temporada),
        1.903 resultados, standings oficiais e campeões conferidos:
        Lauda/Ferrari (75), Hunt/Ferrari (76), Lauda/Ferrari (77),
        Mario Andretti/Team Lotus (78) e Scheckter/Ferrari (79);
    -   qualifying completo de 1975–1979 (1.951 linhas em 78 GPs) pela
        Wikipédia (en), com `source_url`/`fetched_at` por linha. O parser passou
        a aceitar cabeçalho `time gap`, vírgula decimal (`1:26,40`), uma casa
        decimal (`6:58.6`), posições em itálico e construtor sem wikilink;
        gaps (`+0.43`) nunca viram tempo de volta, e DNQ/EX/DNA seguem sem
        posição inventada. A conferência das poles P1 contra a Wikipédia (pt)
        não encontrou divergência;
    -   78 voltas rápidas complementadas pela Wikipédia (pt), com proveniência.
        As poles já vêm do P1 do qualifying importado;
    -   cadastro mínimo de pilotos que só aparecem no qualifying antigo (Tony
        Trimmer, Masami Kuwashima, Bernard de Dryver, Mikko Kozarowitzky, Hans
        Heyer, Teddy Pilette, Divina Galica, Alberto Colombo e Gimax), da equipe
        Apollon e do alias `Carlo Franchi` → `gimax`;
    -   ajustes oficiais de reconciliação de pontos: descartes de pilotos em
        1977 (Lauda -2, Reutemann -1) e 1979 (Scheckter -9, Villeneuve -6,
        Jones -3, Regazzoni -3, Depailler -2, Reutemann -5), e a regra de
        construtores de 1975–1978 (só o melhor carro da equipe em cada GP,
        mais descarte). Nenhum resultado importado foi alterado;
    -   painel "Maiores vencedores por século — século XX" ampliado para
        1975–1999, com aviso de recorte incompleto para 1950–1974;
    -   textos de cobertura (README, PROJETO_F1, export) atualizados para
        1975–2026 (899 GPs encerrados + etapas de 2026).
-   **Testes realizados:** validação da base `APROVADO` (19/19 checagens),
    simulação do qualifying sem erros antes da gravação, `pytest -q` com
    **79 passed**, `py_compile` e `wal_checkpoint(TRUNCATE)` com `(0, 0, 0)`.
-   **Problemas conhecidos:** 2026 segue em andamento com 21 de 23 GPs; o
    fechamento depende da publicação dos resultados finais de R23 na API.
-   **Próxima ação:** publicar o commit e confirmar o Streamlit Cloud; depois
    acompanhar R22 (29/11), R23 (06/12) e `Fecha2026` (07/12).

------------------------------------------------------------------------

## 2026-11-24 --- Extensão final da base para 1970–1974

-   **Decisão:** atender ao pedido final do usuário ("vamos fszer eles, pra
    encerrar, de 1970 a 1974") e encerrar a expansão histórica com cobertura
    1970–2026, mantendo 2026 em andamento.
-   **Arquivos alterados:** `f1dc/config.py`, `f1dc/wikipedia_qualifying.py`,
    `f1dc/wikipedia.py`, `f1dc/export.py`, `f1dc/__init__.py`, `app.py`,
    `README.md`, `docs/PROJETO_F1.md`, `scripts/seed_wiki_entities.py`,
    `tests/test_app_smoke.py`, `data/f1.db`, `data/validation_report.json` e o
    ZIP de exportação.
-   **O que foi implementado:**
    -   importação via Jolpica de 66 GPs (13, 11, 12, 15 e 15 por temporada),
        1.573 resultados, standings oficiais e campeões conferidos:
        Rindt/Team Lotus (70), Stewart/Tyrrell (71), Emerson Fittipaldi/Team
        Lotus (72), Stewart/Team Lotus (73) e Emerson Fittipaldi/McLaren (74);
    -   qualifying completo de 1970–1974 (1.642 linhas em 66 GPs) pela
        Wikipédia (en), com `source_url`/`fetched_at` por linha. O parser passou
        a aceitar lacunas de posição em linhas DNQ/EX (por exemplo, 1970
        Espanha), sem inventar posição. As poles P1 foram conferidas pelo
        infobox da Wikipédia (en) em 1970–1971;
    -   66 voltas rápidas complementares com proveniência: infobox do GP na
        Wikipédia (en) em 1970–1971 e tabela da Wikipédia (pt) em 1972–1974.
        As poles já vêm do P1 do qualifying importado;
    -   cadastro mínimo de pilotos que só aparecem no qualifying antigo (William
        Ferguson e Carlo Facetti) e o alias `iso`/`iso marlboro` →
        `iso_marlboro`;
    -   ajustes oficiais de reconciliação dos construtores de 1970–1974, todos
        negativos e calculados contra o standings oficial da Jolpica. Nenhum
        resultado importado foi alterado;
    -   painel "Maiores vencedores por século — século XX" ampliado para
        1970–1999, com aviso de recorte incompleto para 1950–1969;
    -   textos de cobertura (README, PROJETO_F1, export) atualizados para
        1970–2026 (965 GPs encerrados + etapas de 2026).
-   **Testes realizados:** validação da base `APROVADO` (19/19 checagens),
    `pytest -q` com **79 passed**, `py_compile` e `wal_checkpoint(TRUNCATE)`
    com `(0, 0, 0)`.
-   **Problemas conhecidos:** 2026 segue em andamento com 21 de 23 GPs; o
    fechamento depende da publicação dos resultados finais de R23 na API.
-   **Próxima ação:** publicar o commit e confirmar o Streamlit Cloud; depois
    acompanhar R22 (29/11), R23 (06/12) e `Fecha2026` (07/12).

------------------------------------------------------------------------

## Modelo para próximas atualizações

### AAAA-MM-DD --- Título da alteração

-   **Decisão:**
-   **Arquivos alterados:**
-   **O que foi implementado:**
-   **Testes realizados:**
-   **Problemas conhecidos:**
-   **Próxima ação:**
