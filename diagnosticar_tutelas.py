import os
import time
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

# Códigos de interesse para diagnóstico de tutela/liminar
CODIGOS_TUTELA = {
    332,
    339,
    785,
    792,
    889,
    892,
}

# Diagnóstico controlado
LIMITE = 100


def normalizar_numero(valor):
    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    if valor.endswith(".0"):
        valor = valor[:-2]

    return valor


def consultar_processo(numero_processo, api_key):
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

        movimentos = (
            hits[0]
            .get("_source", {})
            .get("movimentos", [])
        )

        return movimentos

    except Exception as erro:
        print(
            f"{numero_processo}: "
            f"erro - {erro}"
        )
        return []


def extrair_complementos(movimento):
    complementos = movimento.get(
        "complementosTabelados",
        []
    )

    if not complementos:
        return ""

    partes = []

    for complemento in complementos:
        descricao = str(
            complemento.get(
                "descricao",
                ""
            )
        ).strip()

        nome = str(
            complemento.get(
                "nome",
                ""
            )
        ).strip()

        valor = str(
            complemento.get(
                "valor",
                ""
            )
        ).strip()

        codigo = str(
            complemento.get(
                "codigo",
                ""
            )
        ).strip()

        partes.append(
            (
                f"codigo={codigo}; "
                f"descricao={descricao}; "
                f"nome={nome}; "
                f"valor={valor}"
            )
        )

    return " | ".join(partes)


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

    linhas = []

    print(
        "Processos selecionados:",
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

        movimentos = consultar_processo(
            numero,
            api_key
        )

        for movimento in movimentos:
            try:
                codigo = int(
                    movimento.get(
                        "codigo"
                    )
                )
            except (
                TypeError,
                ValueError
            ):
                continue

            if codigo not in CODIGOS_TUTELA:
                continue

            linhas.append({
                "numeroProcesso":
                    numero,
                "codigo":
                    codigo,
                "movimento":
                    movimento.get(
                        "nome",
                        ""
                    ),
                "dataHora":
                    movimento.get(
                        "dataHora",
                        ""
                    ),
                "complementos":
                    extrair_complementos(
                        movimento
                    )
            })

        time.sleep(0.3)

    diagnostico = pd.DataFrame(
        linhas
    )

    if not diagnostico.empty:
        diagnostico = (
            diagnostico
            .sort_values(
                by=[
                    "numeroProcesso",
                    "dataHora"
                ]
            )
        )

    arquivo_saida = os.path.join(
        PASTA,
        "diagnostico_tutelas_datajud.csv"
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
        "DIAGNÓSTICO DE TUTELAS CONCLUÍDO"
    )
    print(
        "================================"
    )
    print(
        "Processos consultados:",
        len(processos)
    )
    print(
        "Movimentos de tutela encontrados:",
        len(diagnostico)
    )

    if not diagnostico.empty:
        print()
        print(
            "AMOSTRA DOS MOVIMENTOS:"
        )
        print(
            diagnostico
            .head(50)
            .to_string(index=False)
        )

    print()
    print(
        "Arquivo gerado:",
        arquivo_saida
    )


if __name__ == "__main__":
    main()
