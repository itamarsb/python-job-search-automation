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


def run(selected_search: str | None = None) -> None:
    load_dotenv()
    configure_logging()
    initialize_database()

    config = load_config()
    settings = config.get("settings", {})

    location = settings.get(
        "location",
        "Rio Grande do Sul, Brazil",
    )
    language = settings.get("language", "pt-br")
    country = settings.get("country", "br")
    pages = int(settings.get("pages_per_search", 1))
    linkedin_only = bool(settings.get("linkedin_only", False))

    total_received = 0
    total_approved = 0
    total_new = 0

    for search_config in config.get("searches", []):
        search_name = search_config["name"]

        if selected_search and search_name != selected_search:
            continue

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
            continue

        total_received += len(jobs)

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
                print_new_job(job, evaluation, search_name)

    logging.info(
        "Finalizado | Recebidas: %d | Aprovadas: %d | Novas: %d",
        total_received,
        total_approved,
        total_new,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automação de busca de vagas com Google Jobs e SerpApi."
    )

    parser.add_argument(
        "--search",
        help="Executa somente uma pesquisa pelo nome configurado.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    run(selected_search=arguments.search)
