from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from database import initialize_database, insert_job
from filters import evaluate_job
from serpapi_client import SerpApiError, search_google_jobs


CONFIG_PATH = Path("config/searches.json")


def configure_logging() -> None:
    Path("logs").mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(
                "logs/job-search.log",
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo de configuração não encontrado: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def print_new_job(
    job: dict[str, Any],
    evaluation: dict[str, Any],
    search_name: str,
) -> None:
    apply_options = job.get("apply_options", [])
    link = ""

    if apply_options:
        link = apply_options[0].get("link", "")

    print("\n" + "=" * 80)
    print(f"NOVA VAGA | Pesquisa: {search_name}")
    print(f"Título: {job.get('title', 'Não informado')}")
    print(f"Empresa: {job.get('company_name', 'Não informada')}")
    print(f"Local: {job.get('location', 'Não informado')}")
    print(f"Origem: {job.get('via', 'Não informada')}")
    print(f"LinkedIn: {'Sim' if evaluation['linkedin_source'] else 'Não'}")
    print(f"Pontuação: {evaluation['score']}")
    print(f"Link: {link}")
    print("=" * 80)


def ask_language() -> str:
    while True:
        print("\nIdioma da pesquisa:")
        print("  en = English")
        print("  pt = Português")

        language = input("Idioma [en/pt]: ").strip().lower()

        if language in {"en", "pt"}:
            return language

        print("\nValor inválido. Digite apenas 'en' ou 'pt'.")


def ask_country() -> str:
    while True:
        print("\nPaís da pesquisa:")
        print("  br = Brazil")
        print("  us = United States")

        country = input("País [br/us]: ").strip().lower()

        if country in {"br", "us"}:
            return country

        print("\nValor inválido. Digite apenas 'br' ou 'us'.")


def ask_interactive_search() -> dict[str, Any]:
    print("\n" + "=" * 70)
    print("PYTHON JOB SEARCH AUTOMATION")
    print("=" * 70)

    while True:
        query = input(
            "\nCargo ou termo que deseja pesquisar: "
        ).strip()

        if query:
            break

        print("O cargo não pode ficar vazio.")

    print("\nInforme a localização no formato:")
    print("city, state, country")
    print("Exemplo:")
    print("Orlando, Florida, United States")
    print("Porto Alegre, Rio Grande do Sul, Brazil")

    while True:
        location = input("\nLocalização: ").strip()

        if location:
            break

        print("A localização não pode ficar vazia.")

    language = ask_language()
    country = ask_country()

    print("\n" + "-" * 70)
    print("CONFIGURAÇÃO DA PESQUISA")
    print("-" * 70)
    print(f"Cargo:       {query}")
    print(f"Localização: {location}")
    print(f"Idioma:      {language}")
    print(f"País:        {country}")
    print("-" * 70)

    return {
        "name": query,
        "query": query,
        "location": location,
        "language": language,
        "country": country,

        # No modo manual, inicialmente não aplicamos
        # filtros obrigatórios do searches.json.
        "include_patterns": [],
        "exclude_patterns": [],
        "blocked_companies": [],
        "preferred_companies": [],
    }


def process_search(
    search_config: dict[str, Any],
    location: str,
    language: str,
    country: str,
    pages: int = 1,
    linkedin_only: bool = False,
) -> tuple[int, int, int]:
    search_name = search_config["name"]

    logging.info("Executando pesquisa: %s", search_name)

    try:
        jobs = search_google_jobs(
            query=search_config["query"],
            location=location,
            language=language,
            country=country,
            pages=pages,
        )
    except SerpApiError:
        logging.exception(
            "A pesquisa %s não pôde ser concluída.",
            search_name,
        )

        return 0, 0, 0

    total_received = len(jobs)
    total_approved = 0
    total_new = 0

    for job in jobs:
        evaluation = evaluate_job(
            job,
            search_config,
            linkedin_only=linkedin_only,
        )

        if not evaluation["approved"]:
            logging.debug(
                "Vaga rejeitada: %s | %s",
                job.get("title"),
                evaluation["rejection_reasons"],
            )
            continue

        total_approved += 1

        is_new = insert_job(
            job=job,
            search_name=search_name,
            score=evaluation["score"],
            linkedin_source=evaluation["linkedin_source"],
        )

        if is_new:
            total_new += 1
            print_new_job(
                job,
                evaluation,
                search_name,
            )

    return (
        total_received,
        total_approved,
        total_new,
    )


def run_interactive() -> None:
    search_config = ask_interactive_search()

    total_received, total_approved, total_new = process_search(
        search_config=search_config,
        location=search_config["location"],
        language=search_config["language"],
        country=search_config["country"],
        pages=1,
        linkedin_only=False,
    )

    logging.info(
        "Finalizado | Recebidas: %d | Aprovadas: %d | Novas: %d",
        total_received,
        total_approved,
        total_new,
    )


def run_configured(selected_search: str) -> None:
    config = load_config()
    settings = config.get("settings", {})

    location = settings.get("location", "")
    language = settings.get("language", "en")
    country = settings.get("country", "us")
    pages = int(settings.get("pages_per_search", 1))
    linkedin_only = bool(
        settings.get("linkedin_only", False)
    )

    total_received = 0
    total_approved = 0
    total_new = 0

    search_found = False

    for search_config in config.get("searches", []):
        search_name = search_config["name"]

        if search_name != selected_search:
            continue

        search_found = True

        received, approved, new = process_search(
            search_config=search_config,
            location=location,
            language=language,
            country=country,
            pages=pages,
            linkedin_only=linkedin_only,
        )

        total_received += received
        total_approved += approved
        total_new += new

    if not search_found:
        logging.error(
            "Pesquisa configurada não encontrada: %s",
            selected_search,
        )

        return

    logging.info(
        "Finalizado | Recebidas: %d | Aprovadas: %d | Novas: %d",
        total_received,
        total_approved,
        total_new,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Automação de busca de vagas "
            "com Google Jobs e SerpApi."
        )
    )

    parser.add_argument(
        "--search",
        help=(
            "Executa uma pesquisa previamente "
            "configurada no searches.json."
        ),
    )

    return parser.parse_args()


def main() -> None:
    load_dotenv()
    configure_logging()
    initialize_database()

    arguments = parse_arguments()

    if arguments.search:
        run_configured(arguments.search)
    else:
        run_interactive()


if __name__ == "__main__":
    main()