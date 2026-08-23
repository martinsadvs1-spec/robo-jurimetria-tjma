
import streamlit as st
import pandas as pd
import os
import requests
st.set_page_config(
    page_title="Robô de Jurimetria TJMA",
    layout="wide"
)

st.title("⚖️ ROBÔ DE JURIMETRIA TJMA")
st.subheader("Vara da Saúde Suplementar do Termo Judiciário de São Luís")
st.caption("Inteligência processual baseada em dados públicos do DataJud/CNJ")

PASTA = os.path.dirname(os.path.abspath(__file__))

ARQUIVO_BASE = os.path.join(
    PASTA,
    "base_processos_vara_saude.csv"
)

ARQUIVO_TUTELA = os.path.join(
    PASTA,
    "primeira_decisao_tutela.csv"
)

# TESTE DATAJUD - 1 PROCESSO
DATAJUD_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_tjma/_search"

def consultar_datajud_teste():
    numero = "08535527720268100001"

    headers = {
        "Authorization": f"APIKey {st.secrets['DATAJUD_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": {
            "match": {
                "numeroProcesso": numero
            }
        }
    }

    resposta = requests.post(
        DATAJUD_URL,
        headers=headers,
        json=payload,
        timeout=30
    )

    return resposta
resposta_teste = consultar_datajud_teste()
st.write("TESTE DATAJUD - STATUS:", resposta_teste.status_code)
dados_teste = resposta_teste.json()

hits_teste = dados_teste.get("hits", {}).get("hits", [])

if hits_teste:
    movimentos_teste = hits_teste[0].get("_source", {}).get("movimentos", [])

    linhas_movimentos = []

    for mov in movimentos_teste:
        complementos = mov.get("complementosTabelados", [])

        detalhes = " | ".join(
            [
                f"{c.get('descricao', '')}: {c.get('nome', c.get('valor', ''))}"
                for c in complementos
            ]
        )

        linhas_movimentos.append({
            "Código": mov.get("codigo"),
            "Movimento": mov.get("nome"),
            "Data": mov.get("dataHora"),
            "Complementos": detalhes
        })

    st.write("MOVIMENTOS DO PROCESSO:")
    st.dataframe(pd.DataFrame(linhas_movimentos), hide_index=True)
else:
    st.warning("Processo não localizado no DataJud.")
@st.cache_data
def carregar_dados():

    base = pd.read_csv(ARQUIVO_BASE)
    tutela = pd.read_csv(ARQUIVO_TUTELA)

    return base, tutela

base, tutela = carregar_dados()

dados = base.merge(
    tutela,
    on="numeroProcesso",
    how="left"
)

def converter_data(valor):

    if pd.isna(valor):
        return pd.NaT

    valor = str(valor).strip()

    if valor.isdigit() and len(valor) >= 14:
        return pd.to_datetime(
            valor[:14],
            format="%Y%m%d%H%M%S",
            errors="coerce"
        )

    dt = pd.to_datetime(
        valor,
        errors="coerce",
        utc=True
    )

    if pd.isna(dt):
        return pd.NaT

    return dt.tz_localize(None)

dados["data_ajuizamento_convertida"] = (
    dados["dataAjuizamento"]
    .apply(converter_data)
)

dados["data_tutela_convertida"] = (
    dados["dataPrimeiraTutela"]
    .apply(converter_data)
)

dados["ano"] = (
    dados["data_ajuizamento_convertida"]
    .dt.year
)

dados["dias_ate_decisao"] = (
    dados["data_tutela_convertida"]
    -
    dados["data_ajuizamento_convertida"]
).dt.total_seconds() / 86400

st.sidebar.header("Filtros")

assuntos_lista = ["TODOS"]

for valor in dados["assuntos"].dropna():

    for assunto in str(valor).split(" | "):

        if assunto not in assuntos_lista:
            assuntos_lista.append(assunto)

assunto_escolhido = st.sidebar.selectbox(
    "Assunto",
    sorted(assuntos_lista)
)

classes = (
    ["TODAS"]
    +
    sorted(
        dados["classe"]
        .dropna()
        .unique()
        .tolist()
    )
)

classe_escolhida = st.sidebar.selectbox(
    "Classe processual",
    classes
)

anos_disponiveis = sorted(
    [
        int(x)
        for x in dados["ano"]
        .dropna()
        .unique()
    ]
)

ano_escolhido = st.sidebar.selectbox(
    "Ano",
    ["TODOS"] + anos_disponiveis
)

amostra_minima = st.sidebar.selectbox(
    "Amostra mínima",
    [10, 20, 30, 50, 100],
    index=1
)

filtrado = dados.copy()

if assunto_escolhido != "TODOS":

    filtrado = filtrado[
        filtrado["assuntos"]
        .fillna("")
        .str.contains(
            assunto_escolhido,
            regex=False
        )
    ]

if classe_escolhida != "TODAS":

    filtrado = filtrado[
        filtrado["classe"] == classe_escolhida
    ]

if ano_escolhido != "TODOS":

    filtrado = filtrado[
        filtrado["ano"] == int(ano_escolhido)
    ]

filtrado = filtrado[
    filtrado["resultado"].notna()
].copy()

filtrado = filtrado[
    filtrado["dias_ate_decisao"].notna()
]

filtrado = filtrado[
    filtrado["dias_ate_decisao"] >= 0
]

st.header("📊 Resultado Jurimétrico")

total = len(filtrado)

concedidas = len(
    filtrado[
        filtrado["resultado"] == "CONCEDIDA"
    ]
)

parciais = len(
    filtrado[
        filtrado["resultado"] == "CONCEDIDA EM PARTE"
    ]
)

negadas = len(
    filtrado[
        filtrado["resultado"] == "NÃO CONCEDIDA"
    ]
)

perc_concedidas = (
    concedidas / total * 100
    if total else 0
)

perc_negadas = (
    negadas / total * 100
    if total else 0
)

mediana_geral = (
    filtrado["dias_ate_decisao"].median()
    if total else None
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Processos analisáveis",
    total
)

c2.metric(
    "Concedidas",
    f"{perc_concedidas:.2f}%"
)

c3.metric(
    "Não concedidas",
    f"{perc_negadas:.2f}%"
)

c4.metric(
    "Mediana até decisão",
    (
        f"{mediana_geral:.2f} dias"
        if mediana_geral is not None
        else "-"
    )
)

if total < 20:
    st.error("🔴 Amostra fraca")
elif total < 50:
    st.warning("🟡 Amostra moderada")
else:
    st.success("🟢 Amostra robusta")

if total < amostra_minima:
    st.warning(
        "A amostra encontrada é inferior "
        "ao mínimo selecionado."
    )

linhas = []

for resultado in [
    "CONCEDIDA",
    "CONCEDIDA EM PARTE",
    "NÃO CONCEDIDA"
]:

    grupo = filtrado[
        filtrado["resultado"] == resultado
    ]

    qtd = len(grupo)

    percentual = (
        qtd / total * 100
        if total else 0
    )

    mediana_dias = (
        grupo["dias_ate_decisao"].median()
        if qtd else None
    )

    linhas.append({
        "Resultado": resultado,
        "Processos": qtd,
        "Percentual (%)":
            round(percentual, 2),
        "Mediana até decisão (dias)":
            (
                round(mediana_dias, 2)
                if pd.notna(mediana_dias)
                else "-"
            )
    })

df_resultados = pd.DataFrame(linhas)

st.dataframe(
    df_resultados,
    use_container_width=True,
    hide_index=True
)

st.header("📂 Processos utilizados")

colunas_exibir = [
    "numeroProcesso",
    "classe",
    "assuntos",
    "resultado",
    "dias_ate_decisao"
]

df_processos = (
    filtrado[colunas_exibir]
    .rename(
        columns={
            "numeroProcesso": "Processo",
            "classe": "Classe",
            "assuntos": "Assuntos",
            "resultado": "Resultado",
            "dias_ate_decisao":
                "Dias até decisão"
        }
    )
)

st.dataframe(
    df_processos,
    use_container_width=True,
    hide_index=True
)

csv = df_processos.to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(
    "📥 Baixar relatório em CSV",
    csv,
    "relatorio_jurimetria_tjma.csv",
    "text/csv"
)

st.divider()

st.caption(
    "Os resultados são descritivos e não representam "
    "garantia ou probabilidade individual de êxito."
)
# ============================================================
# V2.0 — PESQUISA DIRETA DE PROCESSO
# ============================================================

st.divider()

st.header("🔎 Pesquisar Processo")

st.caption(
    "Consulte diretamente um processo existente "
    "na base jurimétrica."
)

numero_pesquisa = st.text_input(
    "Número do processo",
    placeholder="Ex.: 0862733-39.2025.8.10.0001"
)

if numero_pesquisa:

    numero_limpo = "".join(
        caractere
        for caractere in str(numero_pesquisa)
        if caractere.isdigit()
    )

    base_pesquisa = dados.copy()

    base_pesquisa["numero_busca"] = (
        base_pesquisa["numeroProcesso"]
        .astype(str)
        .str.replace(r"\D", "", regex=True)
    )

    processo_encontrado = base_pesquisa[
      base_pesquisa["numero_busca"].str.lstrip("0") == numero_limpo.lstrip("0")
    ].copy()

    if processo_encontrado.empty:

        st.warning(
            "⚠️ Processo não localizado na base atual."
        )

    else:

        st.success("✅ Processo localizado")

        registro = processo_encontrado.iloc[0]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Número do processo**")
            st.write(registro.get("numeroProcesso", "-"))

            st.markdown("**Classe processual**")
            st.write(registro.get("classe", "-"))

            st.markdown("**Assuntos**")
            st.write(registro.get("assuntos", "-"))

        with col2:

            st.markdown("**Resultado da primeira tutela**")

            resultado_processo = registro.get(
                "resultado",
                "-"
            )

            if pd.isna(resultado_processo):
                st.write("Resultado não identificado.")
            else:
                st.write(resultado_processo)

            st.markdown("**Dias até a decisão**")

            dias_processo = registro.get(
                "dias_ate_decisao",
                None
            )

            if pd.notna(dias_processo):
                st.write(f"{dias_processo:.2f} dias")
            else:
                st.write("Tempo não calculável.")

        st.caption(
            "Os dados exibidos correspondem às informações "
            "existentes na base pública utilizada pelo robô."
        )
        st.divider()

        st.subheader("🧭 Casos Semelhantes")

        st.caption(
            "Comparação automática com processos da mesma "
            "classe e com assuntos coincidentes."
        )

        classe_referencia = str(
            registro.get("classe", "")
        )

        assuntos_referencia = str(
            registro.get("assuntos", "")
        )

        lista_assuntos = [
            assunto.strip()
            for assunto in assuntos_referencia.split("|")
            if assunto.strip()
        ]

        semelhantes = dados.copy()

        semelhantes = semelhantes[
            semelhantes["numeroProcesso"].astype(str)
            != str(registro.get("numeroProcesso", ""))
        ].copy()

        semelhantes["pontos_semelhanca"] = 0

        semelhantes.loc[
            semelhantes["classe"].astype(str)
            == classe_referencia,
            "pontos_semelhanca"
        ] += 2
        semelhantes["assuntos_em_comum"] = ""
        for assunto in lista_assuntos:
            semelhantes.loc[
                semelhantes["assuntos"]
                .fillna("")
                .str.contains(
                    assunto,
                    regex=False
                ),
                "pontos_semelhanca"
            ] += 1
            mascara_assunto = (
                semelhantes["assuntos"]
                .fillna("")
                .str.contains(assunto, regex=False)
            )

            semelhantes.loc[
                mascara_assunto,
                "assuntos_em_comum"
            ] = semelhantes.loc[
                mascara_assunto,
                "assuntos_em_comum"
            ].apply(
                lambda atual: (
                    f"{atual} | {assunto}"
                    if atual
                    else assunto
                )
            )

        semelhantes = semelhantes[
    (semelhantes["classe"].astype(str) == classe_referencia)
    & (semelhantes["pontos_semelhanca"] >= 3)
        ].copy()

        semelhantes = semelhantes.sort_values(
            "pontos_semelhanca",
            ascending=False
        )

        semelhantes["assuntos_coincidentes"] = (
            semelhantes["pontos_semelhanca"] - 2
        )

        total_assuntos_referencia = max(len(lista_assuntos), 1)

        semelhantes["percentual_assuntos_coincidentes"] = (
            semelhantes["assuntos_coincidentes"]
            / total_assuntos_referencia
        )

        semelhantes["grau_semelhanca"] = (
            semelhantes["percentual_assuntos_coincidentes"].apply(
                lambda percentual: (
                    "ALTA"
                    if percentual == 1
                    else "MÉDIA"
                    if percentual >= 0.5
                    else "BAIXA"
                )
            )
        )

        alta = (semelhantes["grau_semelhanca"] == "ALTA").sum()
        media = (semelhantes["grau_semelhanca"] == "MÉDIA").sum()
        baixa = (semelhantes["grau_semelhanca"] == "BAIXA").sum()

        col_alta, col_media, col_baixa = st.columns(3)

        col_alta.metric("Alta similaridade", int(alta))
        col_media.metric("Média similaridade", int(media))
        col_baixa.metric("Baixa similaridade", int(baixa))

        if alta > 0:
            grupo_prioritario = semelhantes[
                semelhantes["grau_semelhanca"] == "ALTA"
            ].copy()
            nome_grupo = "Alta similaridade"

        elif media > 0:
            grupo_prioritario = semelhantes[
                semelhantes["grau_semelhanca"] == "MÉDIA"
            ].copy()
            nome_grupo = "Média similaridade"

        else:
            grupo_prioritario = semelhantes[
                semelhantes["grau_semelhanca"] == "BAIXA"
            ].copy()
            nome_grupo = "Baixa similaridade"

        st.subheader("🎯 Grupo comparativo prioritário")
        st.write(
            f"{nome_grupo}: {len(grupo_prioritario)} processos"
        )

        resultados_prioritarios = (
            grupo_prioritario["resultado"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        concedidas_prioritario = (
            resultados_prioritarios == "CONCEDIDA"
        ).sum()

        parcial_prioritario = (
            resultados_prioritarios == "CONCEDIDA EM PARTE"
        ).sum()

        nao_concedidas_prioritario = (
            resultados_prioritarios == "NÃO CONCEDIDA"
        ).sum()

        decisoes_identificadas = (
            concedidas_prioritario
            + parcial_prioritario
            + nao_concedidas_prioritario
        )

        sem_resultado = (
            len(grupo_prioritario) - decisoes_identificadas
        )

        if decisoes_identificadas > 0:
            perc_concedidas = (
                concedidas_prioritario / decisoes_identificadas
            ) * 100

            perc_parcial = (
                parcial_prioritario / decisoes_identificadas
            ) * 100

            perc_nao_concedidas = (
                nao_concedidas_prioritario / decisoes_identificadas
            ) * 100

            dias_prioritarios = pd.to_numeric(
                grupo_prioritario["dias_ate_decisao"],
                errors="coerce"
            ).dropna()

            mediana_prioritaria = (
                dias_prioritarios.median()
                if not dias_prioritarios.empty
                else None
            )
            st.subheader("📊 Jurimetria do grupo prioritário")
            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Decisões identificadas",
                int(decisoes_identificadas)
            )

            c2.metric(
                "Concedidas",
                f"{int(concedidas_prioritario)} de {int(decisoes_identificadas)} ({perc_concedidas:.1f}%)"
            )

            c3.metric(
                "Concedidas em parte",
                f"{int(parcial_prioritario)} de {int(decisoes_identificadas)} ({perc_parcial:.1f}%)"
            )

            c4.metric(
                "Não concedidas",
                f"{int(nao_concedidas_prioritario)} de {int(decisoes_identificadas)} ({perc_nao_concedidas:.1f}%)"
            )

            st.metric(
                "Sem resultado identificado",
                int(sem_resultado)
            )

            cobertura_resultados = (
            decisoes_identificadas / len(grupo_prioritario) * 100
            if len(grupo_prioritario) > 0
            else 0
        )

        st.metric(
            "Cobertura das decisões",
            f"{cobertura_resultados:.1f}%"
        )

        st.caption(
            f"{int(decisoes_identificadas)} de {len(grupo_prioritario)} processos "
            "do grupo prioritário possuem resultado identificado."
        )

        if cobertura_resultados < 50:
            st.warning(
                "Amostra limitada: os percentuais de concessão e não concessão "
                "devem ser interpretados com cautela."
            )

            if mediana_prioritaria is not None:
                st.metric(
                    "Mediana até decisão",
                    f"{mediana_prioritaria:.2f} dias"
                )

           
        

        st.metric(
            "Universo inicial de casos semelhantes",
            len(semelhantes)
        )

        if semelhantes.empty:

            st.warning(
                "Nenhum caso semelhante foi localizado."
            )

        else:

                    tabela_prioritaria = (
            grupo_prioritario[
                [
                    "numeroProcesso",
                    "classe",
                    "assuntos",
                    "resultado",
                    "dias_ate_decisao",
                    "pontos_semelhanca",
                    "assuntos_coincidentes",
                    "percentual_assuntos_coincidentes",
                    "assuntos_em_comum"
                ]
            ]
            .copy()
            .rename(
                columns={
                    "numeroProcesso": "Processo",
                    "classe": "Classe processual",
                    "assuntos": "Assuntos",
                    "resultado": "Resultado",
                    "dias_ate_decisao": "Dias até decisão",
                    "pontos_semelhanca": "Pontuação de semelhança",
                    "assuntos_coincidentes": "Assuntos coincidentes",
                    "percentual_assuntos_coincidentes": "Similaridade temática",
                "assuntos_em_comum": "Assuntos em comum"
                }
            )
        )

                    tabela_prioritaria["Processo"] = (
            tabela_prioritaria["Processo"]
            .astype(str)
            .str.replace(r"\D", "", regex=True)
            .str.zfill(20)
            .str.replace(
                r"(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})",
                r"\1-\2.\3.\4.\5.\6",
                regex=True
            )
        )
        tabela_prioritaria["Assuntos coincidentes"] = (
            tabela_prioritaria["Assuntos coincidentes"]
            .astype(int)
            .astype(str)
            + f" de {total_assuntos_referencia}"
        )
        tabela_prioritaria["Similaridade temática"] = (
            tabela_prioritaria["Similaridade temática"]
            .apply(lambda x: f"{x * 100:.1f}%")
        )

        tabela_prioritaria["Resultado"] = (
            tabela_prioritaria["Resultado"]
            .fillna("Não identificado")
            .replace("None", "Não identificado")
        )

        tabela_prioritaria["Dias até decisão"] = (
            pd.to_numeric(
                tabela_prioritaria["Dias até decisão"],
                errors="coerce"
            )
            .apply(
                lambda x: f"{x:.2f} dias"
                if pd.notna(x)
                else "Não identificado"
            )
        )
        st.dataframe(
            tabela_prioritaria,
            use_container_width=True,
            hide_index=True
        )
