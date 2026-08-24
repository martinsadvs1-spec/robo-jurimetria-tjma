import os
import time
import pandas as pd
import requests


PASTA = os.path.dirname(os.path.abspath(__file__))

ARQUIVO_BASE = os.path.join(
    PASTA,
    "base_processos_vara_saude.csv"
)

ARQUIVO_TUTELA = os.path.join(
    PASTA,
    "primeira_decisao_tutela.csv"
)

ARQUIVO_SAIDA = os.path.join(
    PASTA,
    "primeira_decisao_tutela_atualizada.csv"
)


DATAJUD_URL = (
    "https://api-publica.datajud.cnj.jus.br/"
    "api_publica_tjma/_search"
)



CODIGOS_RESULTADO_TUTELA = {
    332: "CONCEDIDA",
    339: "CONCEDIDA",
    889: "CONCEDIDA EM PARTE",
    892: "CONCEDIDA EM PARTE",
    785: "NÃO CONCEDIDA",
    792: "NÃO CONCEDIDA",
}


# Primeiro teste: consultar somente 10 processos



def normalizar_numero(valor):
    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    if valor.endswith(".0"):
        valor = valor[:-2]

    return valor


def consultar_datajud(numero_processo, api_key):
    headers = {
        "Authorization": f"APIKey {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": {
            "match": {
                "numeroProcesso": numero_processo
            }
        }
    }

    try:
        resposta = requests.post(
            DATAJUD_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        if resposta.status_code != 200:
            print(
                f"{numero_processo}: "
                f"HTTP {resposta.status_code}"
            )
            return None

        conteudo = resposta.json()

        hits = (
            conteudo
            .get("hits", {})
            .get("hits", [])
        )

        if not hits:
            print(f"{numero_processo}: não encontrado")
            return None

        movimentos = (
            hits[0]
            .get("_source", {})
            .get("movimentos", [])
        )

        encontrados = []

        for movimento in movimentos:
            try:
                codigo = int(
                    movimento.get("codigo")
                )
            except (TypeError, ValueError):
                continue

            if codigo in CODIGOS_RESULTADO_TUTELA:
                encontrados.append({
                    "codigo": codigo,
                    "data": movimento.get(
                        "dataHora",
                        ""
                    )
                })

        if not encontrados:
            print(
                f"{numero_processo}: "
                "sem código classificável"
            )
            return None

        encontrados.sort(
            key=lambda item: item["data"]
        )

        primeira = encontrados[0]

        return {
            "numeroProcesso": numero_processo,
            "codigoMovimento": primeira["codigo"],
            "resultado":
                CODIGOS_RESULTADO_TUTELA[
                    primeira["codigo"]
                ],
            "dataPrimeiraTutela":
                primeira["data"]
        }

    except Exception as erro:
        print(
            f"{numero_processo}: erro - {erro}"
        )
        return None


def main():

    api_key = os.getenv("DATAJUD_API_KEY")

    if not api_key:
        raise RuntimeError(
            "DATAJUD_API_KEY não configurada."
        )

    base = pd.read_csv(
        ARQUIVO_BASE,
        dtype={"numeroProcesso": str}
    )

    tutela = pd.read_csv(
        ARQUIVO_TUTELA,
        dtype={"numeroProcesso": str}
    )

    base["numeroProcesso"] = (
        base["numeroProcesso"]
        .apply(normalizar_numero)
    )

    tutela["numeroProcesso"] = (
        tutela["numeroProcesso"]
        .apply(normalizar_numero)
    )

    resultados_validos = tutela[
        tutela["resultado"].notna()
        &
        (
            tutela["resultado"]
            .astype(str)
            .str.strip()
            != ""
        )
    ]

    processos_ja_classificados = set(
        resultados_validos["numeroProcesso"]
    )

    faltantes = base[
        ~base["numeroProcesso"].isin(
            processos_ja_classificados
        )
    ].copy()

    faltantes = faltantes.drop_duplicates(
        subset=["numeroProcesso"]
    )

    print(
        "Processos sem classificação:",
        len(faltantes)
    )

    novos_resultados = []

    for numero in faltantes["numeroProcesso"]:

        print(f"Consultando {numero}...")

        resultado = consultar_datajud(
            numero,
            api_key
        )

        if resultado:
            novos_resultados.append(
                resultado
            )

            print(
                numero,
                "=>",
                resultado["resultado"]
            )

        time.sleep(0.5)

    if novos_resultados:

        novos = pd.DataFrame(
            novos_resultados
        )

        tabela_final = pd.concat(
            [tutela, novos],
            ignore_index=True
        )

        tabela_final = (
            tabela_final
            .drop_duplicates(
                subset=["numeroProcesso"],
                keep="first"
            )
        )

    else:
        tabela_final = tutela.copy()

    tabela_final.to_csv(
        ARQUIVO_SAIDA,
        index=False
    )

    print()
    print("================================")
    print("ATUALIZAÇÃO CONCLUÍDA")
    print("================================")

    print(
        "Consultados:",
        len(faltantes)
    )

    print(
        "Novos classificados:",
        len(novos_resultados)
    )

    print(
        "Arquivo gerado:",
        ARQUIVO_SAIDA
    )


if __name__ == "__main__":
    main()
