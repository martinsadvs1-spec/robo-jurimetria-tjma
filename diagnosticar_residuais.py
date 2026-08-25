import os
import time
from collections import Counter

import pandas as pd
import requests


PASTA = os.path.dirname(os.path.abspath(__file__))

ARQUIVO_BASE = os.path.join(
    PASTA,
    "base_processos_vara_saude.csv"
)

ARQUIVO_ATUALIZADO = os.path.join(
    PASTA,
    "primeira_decisao_tutela_atualizada.csv"
)

ARQUIVO_SAIDA = os.path.join(
    PASTA,
    "diagnostico_residuais_datajud.csv"
)

DATAJUD_URL = (
    "https://api-publica.datajud.cnj.jus.br/"
    "api_publica_tjma/_search"
)

CODIGOS_JA_CLASSIFICADOS = {
    332,
    339,
    785,
    792,
    889,
    892,
}


def normalizar_numero(valor):
    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    if valor.endswith(".0"):
        valor = valor[:-2]

    return valor


def consultar_movimentos(numero_processo, api_key):
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
                numero_processo,
                "=> HTTP",
                resposta.status_code
            )
            return []

        conteudo = resposta.json()

        hits = (
            conteudo
            .get("hits", {})
            .get("hits", [])
        )

        if not hits:
            return []

        return (
            hits[0]
            .get("_source", {})
            .get("movimentos", [])
        )

    except Exception as erro:
        print(
            numero_processo,
            "=> ERRO:",
            erro
        )
        return []


def main():
    api_key = os.getenv("DATAJUD_API_KEY")

    if not api_key:
        raise RuntimeError(
            "DATAJUD_API_KEY não encontrada."
        )

    base = pd.read_csv(
        ARQUIVO_BASE,
        dtype=str
    )

    atualizada = pd.read_csv(
        ARQUIVO_ATUALIZADO,
        dtype=str
    )

    base["numeroProcesso"] = (
        base["numeroProcesso"]
        .apply(normalizar_numero)
    )

    atualizada["numeroProcesso"] = (
        atualizada["numeroProcesso"]
        .apply(normalizar_numero)
    )

    classificados = set(
        atualizada["numeroProcesso"]
        .dropna()
        .astype(str)
    )

    residuais = (
        base[
            ~base["numeroProcesso"]
            .isin(classificados)
        ]
        .drop_duplicates(
            subset=["numeroProcesso"]
        )
    )

    print(
        "PROCESSOS RESIDUAIS:",
        len(residuais)
    )

    contador = Counter()

    for numero in residuais["numeroProcesso"]:

        print(
            f"Diagnosticando {numero}..."
        )

        movimentos = consultar_movimentos(
            numero,
            api_key
        )

        for movimento in movimentos:
            try:
                codigo = int(
                    movimento.get("codigo")
                )
            except (TypeError, ValueError):
                continue

            if codigo in CODIGOS_JA_CLASSIFICADOS:
                continue

            nome = (
                movimento.get("nome")
                or ""
            )

            contador[
                (codigo, nome)
            ] += 1

        time.sleep(0.5)

    linhas = []

    for (
        codigo,
        movimento
    ), ocorrencias in contador.most_common():

        linhas.append({
            "codigo": codigo,
            "movimento": movimento,
            "ocorrencias": ocorrencias
        })

    diagnostico = pd.DataFrame(linhas)

    diagnostico.to_csv(
        ARQUIVO_SAIDA,
        index=False
    )

    print()
    print("==============================")
    print("DIAGNÓSTICO RESIDUAL CONCLUÍDO")
    print("==============================")
    print(
        "Processos residuais:",
        len(residuais)
    )
    print(
        "Códigos diferentes encontrados:",
        len(diagnostico)
    )
    print()
    print("CÓDIGOS MAIS FREQUENTES:")
    print(
        diagnostico.head(50).to_string(
            index=False
        )
    )
    print()
    print(
        "Arquivo gerado:",
        ARQUIVO_SAIDA
    )


if __name__ == "__main__":
    main()
