
import streamlit as st
import pandas as pd
import os

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
                    numero_exibicao = str(
            registro.get("numeroProcesso", "")
        )
        
        numero_exibicao = "".join(
            c for c in numero_exibicao if c.isdigit()
        )
        
        numero_exibicao = numero_exibicao.zfill(20)
        
        numero_formatado = (
            f"{numero_exibicao[:7]}-"
            f"{numero_exibicao[7:9]}."
            f"{numero_exibicao[9:13]}."
            f"{numero_exibicao[13]}."
            f"{numero_exibicao[14:16]}."
            f"{numero_exibicao[16:]}"
        )
        
        st.write(numero_formatado)

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

        semelhantes = semelhantes[
            semelhantes["pontos_semelhanca"] > 0
        ].copy()

        semelhantes = semelhantes.sort_values(
            "pontos_semelhanca",
            ascending=False
        )

        st.metric(
            "Casos semelhantes encontrados",
            len(semelhantes)
        )

        if semelhantes.empty:

            st.warning(
                "Nenhum caso semelhante foi localizado."
            )

        else:

            st.dataframe(
                semelhantes[
                    [
                        "numeroProcesso",
                        "classe",
                        "assuntos",
                        "resultado",
                        "dias_ate_decisao",
                        "pontos_semelhanca"
                    ]
                ].head(20),
                use_container_width=True,
                hide_index=True
            )
