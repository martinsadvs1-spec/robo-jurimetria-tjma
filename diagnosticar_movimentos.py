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

DATAJUD_URL = (
    "https://api-publica.datajud.cnj.jus.br/"
    "api_publica_tjma/_search"
)

# Primeiro diagnóstico controlado
LIMITE = 50


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
                f"{numero_processo}: "
                f"HTTP {resposta.status_code}"
            )
            return []

        conteudo = resposta.json()

        hits = (
            conteudo
            .get("hits", {})
            .get("hits", [])
        )

        if not hits:
            print(
                f"{numero_processo}: "
                "não encontrado"
            )
            return []

        return (
            hits[0]
            .get("_source", {})
            .get("movimentos", [])
        )

    except Exception as erro:
        print(
            f"{numero_processo}: "
            f"erro - {erro}"
        )
        return []


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

    base["numeroProcesso"] = (
        base["numeroProcesso"]
        .apply(normalizar_numero)
    )

    processos = (
        base["numeroProcesso"]
        .dropna()
        .drop_duplicates()
        .head(LIMITE)
        .tolist()
    )

    contador = Counter()
    linhas = []

    print(
        "Processos selecionados para diagnóstico:",
        len(processos)
    )

    for posicao, numero in enumerate(
        processos,
        start=1
    ):
        print(
            f"[{posicao}/{len(processos)}] "
            f"Consultando {numero}..."
        )

        movimentos = consultar_movimentos(
            numero,
            api_key
        )

        for movimento in movimentos:
            codigo = movimento.get(
                "codigo",
                ""
            )

            nome = movimento.get(
                "nome",
                ""
            )

            chave = (
                str(codigo),
                str(nome)
            )

            contador[chave] += 1

        time.sleep(0.3)

    for (
        codigo,
        nome
    ), quantidade in contador.most_common():

        linhas.append({
            "codigo": codigo,
            "movimento": nome,
            "ocorrencias": quantidade
        })

    diagnostico = pd.DataFrame(
        linhas
    )

    arquivo_saida = os.path.join(
        PASTA,
        "diagnostico_movimentos_datajud.csv"
    )

    diagnostico.to_csv(
        arquivo_saida,
        index=False
    )

    print()
    print(
        "================================"
    )
    print(
        "DIAGNÓSTICO CONCLUÍDO"
    )
    print(
        "================================"
    )
    print(
        "Processos consultados:",
        len(processos)
    )
    print(
        "Códigos/movimentos diferentes:",
        len(diagnostico)
    )

    print()
    print(
        "20 MOVIMENTOS MAIS FREQUENTES:"
    )

    if diagnostico.empty:
        print(
            "Nenhum movimento encontrado."
        )
    else:
        print(
            diagnostico
            .head(20)
            .to_string(index=False)
        )

    print()
    print(
        "Arquivo gerado:",
        arquivo_saida
    )


if __name__ == "__main__":
    main()
