# F1 DATA CENTER --- Documento central do projeto

**Versão:** 2.3\
**Status:** base 1980–2025 importada e validada; temporada 2026 em andamento
(etapas concluídas importadas; títulos de pilotos e construtores já garantidos
matematicamente por Antonelli e Mercedes). As poles e voltas rápidas de
1980–2003, ausentes na fonte primária, foram complementadas pela Wikipédia
(pt), e o qualifying de 1980–2002 foi complementado pela Wikipédia (en), sempre
com fonte e data registradas. A fonte primária mantém prioridade.
O painel também mostra os **maiores vencedores por século** — século XX
(1980–1999, com aviso de recorte incompleto) e século XXI (2000–2026) —, com o
circuito onde cada piloto mais venceu (empates explícitos), as vitórias por
circuito e os **circuitos fora do calendário atual**, calculados a partir do
calendário importado.\
**Idioma da interface:** português (Brasil).

## 1. Objetivo

Construir um dashboard interativo de estatísticas históricas da Fórmula
1, cobrindo as temporadas de **1990 a 2025** (encerradas) e a temporada
**2026 em andamento**. O painel deve permitir navegar por temporada,
Grande Prêmio, piloto e equipe, consultar resultados completos e comparar
desempenhos.

A temporada 2026 entra em modo parcial: apenas as etapas já concluídas são
importadas e a classificação exibida é a posição atual. Títulos só são
exibidos quando matematicamente garantidos ou depois do encerramento.

## 2. Escopo inicial

### Temporadas e quantidade de etapas principais

  Temporada         GPs
  ----------- ---------
  1990               16
  1991               16
  1992               16
  1993               16
  1994               16
  1995               17
  1996               16
  1997               17
  1998               16
  1999               16
  2000               17
  2001               17
  2002               17
  2003               16
  2004               18
  2005               19
  2006               18
  2007               17
  2008               18
  2009               17
  2010               19
  2011               19
  2012               20
  2013               19
  2014               19
  2015               19
  2016               21
  2017               20
  2018               21
  2019               21
  2020               17
  2021               22
  2022               22
  2023               22
  2024               24
  2025               24
  **Subtotal encerrado** **665**
  2026               23 (20 concluídos)
  **Total do calendário** **688**

A contagem acima refere-se às corridas principais do calendário.
Corridas Sprint devem ser tratadas separadamente, sem serem confundidas
com os GPs principais.

Em 2026, entram apenas as etapas que já têm resultado na fonte. As etapas
futuras não são preenchidas por suposição. O título de pilotos de Antonelli
e o de construtores da Mercedes já estão matematicamente garantidos; eles
aparecem como "matemáticos" e a temporada continua em andamento até a
última etapa.

### Por Grande Prêmio

**Classificação (Qualifying):** - posição final na sessão; - piloto e
equipe; - tempos de Q1, Q2 e Q3, quando aplicáveis/disponíveis; -
identificação do pole position a partir do resultado oficial da
classificação; - grid efetivo de largada mantido como dado separado,
pois penalidades e alterações podem mudar a ordem de largada.

**Corrida:** - posição final e posição textual/status; - piloto, equipe
e número do carro; - grid de largada; - voltas completadas; - tempo de
corrida ou intervalo, quando fornecido; - pontos; - status (chegou,
abandono, desclassificação etc.); - volta mais rápida, número da volta,
tempo e velocidade média, quando disponíveis; - pódio e Top 10 derivados
dos resultados oficiais, sem descartar os demais classificados.

**Observação:** penalidades e decisões dos comissários só devem ser
exibidas quando houver uma fonte de dados confiável para elas. Não
inferir penalidades apenas pela diferença entre posição de classificação
e grid.

### Estatísticas por piloto

-   pontos;
-   vitórias;
-   pódios;
-   poles;
-   voltas mais rápidas;
-   posições de largada e chegada;
-   abandonos e status;
-   resultados por etapa;
-   comparação com companheiro de equipe.

### Estatísticas por equipe

-   pontos e posição no campeonato de construtores;
-   vitórias, pódios e poles (P1 do qualifying);
-   pilotos titulares por temporada;
-   resultados por GP;
-   comparação entre equipes e temporadas.

### Visões gerais

-   calendário e resultados de cada GP;
-   classificação dos campeonatos de pilotos e construtores;
-   gráficos e rankings;
-   filtros por temporada, piloto, equipe e circuito;
-   comparações históricas.

## 3. Fonte de dados e critérios de confiabilidade

Fonte primária de importação planejada: **Jolpica F1 API**, compatível
com a estrutura histórica da Ergast API.

-   API: https://api.jolpi.ca/ergast/f1/
-   Repositório/documentação: https://github.com/jolpica/jolpica-f1

Endpoints de referência (confirmar a estrutura atual na documentação
antes de implementar): - `/{season}/races` - `/{season}/results` -
`/{season}/qualifying` - `/{season}/driverStandings` -
`/{season}/constructorStandings` - `/{season}/{round}/results` -
`/{season}/{round}/qualifying`

Usar também os resultados oficiais da Fórmula 1 e documentos da FIA para
validar resultados, decisões, penalidades e campeonatos: -
https://www.formula1.com/ - https://www.fia.com/

### Regras importantes

1.  Não afirmar que a base está completa antes de importar e conferir os
    resultados de GP de cada temporada (821 GPs encerrados de 1980 a 2025,
    mais as etapas concluídas de 2026).
2.  Preservar os registros completos, não somente o Top 10.
3.  Não confundir pole position com primeiro colocado no grid efetivo.
4.  Não presumir que volta mais rápida sempre gera ponto: a regra de
    pontuação mudou ao longo do período e teve condições específicas.
5.  Não calcular classificação oficial final apenas somando resultados
    de corrida sem conferir sprint, descartes históricos quando
    aplicáveis, penalidades, desempates e regras de pontuação.
6.  Distinguir dado ausente de dado igual a zero.
7.  Guardar a fonte e, se possível, a data/hora da importação.
8.  Tratar DNS, DNF, DSQ e demais status sem convertê-los em posições
    numéricas inventadas.
9.  Verificar corridas canceladas, substituições de calendário e etapas
    especiais.
10. Validar amostras e totais por temporada contra fontes oficiais.
11. Em temporada em andamento, importar somente etapas com resultado e
    mostrar a classificação atual. Títulos só podem ser exibidos/contados
    quando matematicamente garantidos (vantagem maior que o máximo de
    pontos ainda disponível) ou depois do encerramento oficial.
12. Respeitar exclusões oficiais de campeonato (ex.: McLaren em 2007):
    a equipe pode aparecer sem posição e com 0 ponto nos construtores,
    sem apagar seus resultados de pista (vitórias, pódios e poles).
13. Não comparar pontos brutos entre eras: até 2009 a vitória valia 10
    pontos; a partir de 2010, 25 (com o Top 10 pontuando). A soma de
    pontos do painel é informativa e não normalizada; para comparações
    históricas, priorizar vitórias, pódios e poles. Exceções pontuais,
    como Abu Dhabi 2014 em dobro, vêm da fonte oficial.
14. Quando a fonte primária não trouxer pole, volta mais rápida ou a
    classificação completa, a lacuna pode ser complementada por fonte
    alternativa confiável (Wikipédia em português para premiações e em
    inglês para o qualifying de 1980 a 2002), guardando URL e data. A fonte
    primária sempre tem prioridade e nenhum dado é preenchido por suposição.

## 4. Modelo de dados sugerido

Separar entidades em tabelas ou arquivos normalizados:

-   `seasons`: ano, total de etapas, campeão de pilotos, campeão de
    construtores.
-   `circuits`: identificador, nome, localização, país.
-   `races`: temporada, rodada, nome do GP, circuito, data, URL de
    origem.
-   `drivers`: identificador, nome, código, número, nacionalidade.
-   `constructors`: identificador, nome, nacionalidade.
-   `qualifying_results`: temporada, rodada, piloto, equipe, posição,
    Q1, Q2, Q3 (em 1980–2002, o tempo da sessão única fica em Q1 e Q2/Q3
    ficam nulos), URL e data da fonte.
-   `race_results`: temporada, rodada, piloto, equipe, posição, posição
    textual, grid, voltas, pontos, status, tempo.
-   `fastest_laps`: temporada, rodada, piloto, posição da volta rápida,
    número da volta, tempo, velocidade.
-   `driver_standings`: temporada, rodada, piloto, posição, pontos,
    vitórias.
-   `constructor_standings`: temporada, rodada, equipe, posição, pontos,
    vitórias.
-   `sprint_results`: temporada, rodada, piloto, equipe, posição, grid,
    voltas, pontos, status.

Manter chaves estáveis da API (`driverId`, `constructorId`,
identificador de circuito e temporada/rodada). Evitar usar apenas nomes
como identificadores.

## 5. Tecnologias planejadas

-   Python 3.10 ou superior;
-   Streamlit para a interface;
-   Pandas para tratamento de dados;
-   Requests para chamadas HTTP;
-   Plotly para gráficos;
-   Jolpica F1 API como fonte de importação.

Dependências iniciais em `requirements.txt`: - `streamlit` - `pandas` -
`requests` - `plotly`

## 6. Arquivos já preparados

O protótipo inicial foi empacotado em `f1_data_center_2021_2025.zip`,
contendo: - `app.py`: aplicação Streamlit inicial; - `requirements.txt`:
dependências; - `README.md`: instruções iniciais.

O protótipo tem seletores de temporada e GP, abas para corridas,
campeonato, pilotos e equipes, e tenta importar calendário, resultados e
classificação pela API.

**Estado real:** o código foi preparado, mas a importação ao vivo ainda
precisa ser executada no computador do usuário e testada. Não considerar
os dados baixados, completos ou validados até que o aplicativo execute
com sucesso e a checagem de qualidade seja concluída.

## 7. Próximas etapas de desenvolvimento

### Fase A --- Fazer o protótipo executar

1.  Instalar Python e dependências.
2.  Extrair o ZIP.
3.  Abrir CMD/terminal na pasta do projeto.
4.  Executar `python -m pip install -r requirements.txt`.
5.  Executar `streamlit run app.py`.
6.  Corrigir eventuais problemas de API, paginação ou compatibilidade.

### Fase B --- Importação robusta

1.  Consultar a documentação atual da API.
2.  Implementar paginação correta para cada endpoint.
3.  Importar temporadas de 1990 a 2025 e as etapas concluídas de 2026.
4.  Salvar os dados localmente (preferencialmente CSV/Parquet ou
    SQLite).
5.  Permitir atualização sem duplicar registros.
6.  Registrar falhas e dados ausentes.

### Fase C --- Validação

1.  Conferir quantidade de GPs por temporada encerrada: 16 em 1990, 1991,
    1992, 1993, 1994, 1996, 1998, 1999 e 2003; 17 em 1995, 1997, 2000,
    2001 e 2002; 18 em 2004; 19 em 2005; depois 18, 17, 18, 17, 19,
    19, 20, 19, 19, 19, 21, 20, 21, 21, 17, 22, 22, 22, 24 e 24; em 2026,
    conferir apenas as etapas concluídas contra o calendário.
2.  Conferir se cada GP possui resultados e classificação quando
    aplicável.
3.  Validar campeões e standings oficiais (nas temporadas encerradas).
4.  Validar poles, vencedores, pódios e voltas mais rápidas em amostras.
5.  Conferir corridas com Sprint, abandonos, DSQ e penalidades.
6.  Documentar divergências e limitações da API.

### Fase D --- Melhorias do dashboard

1.  Criar páginas de temporada, GP, piloto e equipe.
2.  Adicionar filtros e pesquisa.
3.  Criar gráficos de pontos, vitórias, pódios e evolução por etapa.
4.  Criar comparação entre pilotos e equipes.
5.  Exibir detalhes completos da classificação e corrida.
6.  Adicionar exportação CSV.
7.  Melhorar visual, responsividade e navegação.

### Fase E --- Temporada 2026

Enquanto a temporada estiver em andamento, importar somente as etapas já
concluídas, exibir a classificação atual e manter `2026` em
`IN_PROGRESS_SEASONS`. Títulos já garantidos matematicamente ficam em
`CLINCHED_CHAMPIONS` e são conferidos pela validação. Depois do
encerramento, remover `2026` dos dois conjuntos, reimportar, validar os
campeões e só então tratá-la como temporada encerrada, sem alterar
indevidamente os históricos anteriores.

## 8. Como outra IA deve continuar

Ao receber este documento, a IA deve: - ler este documento e o
`CHANGELOG.md`; - pedir ao usuário o arquivo ZIP do protótipo, caso não
esteja disponível; - continuar a partir do estado real descrito, sem
alegar que a importação já foi concluída; - orientar o usuário passo a
passo, em português simples; - fornecer arquivos completos atualizados
quando modificar o código; - explicar exatamente onde salvar/substituir
os arquivos e quais comandos executar no Windows; - testar a lógica e
tratar paginação, limites da API, erros de rede e dados ausentes; -
priorizar correção e integridade histórica sobre aparência; - não
inventar estatísticas nem preencher dados ausentes por suposição.

## 9. Definição de pronto da primeira versão

A primeira versão histórica será considerada pronta quando: - as quarenta e
seis temporadas encerradas (1980–2025) estiverem carregadas; - os 821 GPs
encerrados estiverem identificados; - cada GP tiver resultado completo
de corrida e pole identificada (classificação completa na fonte primária
ou complementada com proveniência); - pole, vencedor, pódio, Top 10 e volta
mais rápida forem apresentados corretamente quando houver dado; - standings
oficiais forem conferidos; - filtros por temporada e GP funcionarem; - os
dados puderem ser atualizados sem duplicação; - limitações e ausências
estiverem identificadas claramente.

Para 2026 (em andamento), a versão é considerada correta quando: - apenas
etapas concluídas estiverem no banco; - a classificação atual for exibida
sem ser tratada como final; - títulos só forem atribuídos quando
matematicamente garantidos (Antonelli e Mercedes) ou após o encerramento;
- a validação aprovar a base sem exigir campeão final nem total fixo de
GPs.

------------------------------------------------------------------------

**Princípio do projeto:** construir uma base histórica verificável e um
dashboard fácil de usar, não apenas uma tela visual com números sem
validação.
