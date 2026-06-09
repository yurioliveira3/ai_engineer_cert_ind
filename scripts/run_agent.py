"""CLI runner for the SRAG Agent.

Usage:
    python scripts/run_agent.py
"""

from src.agent.orchestrator import create_agent
from src.config import Settings


def main():
    settings = Settings()
    agent = create_agent(settings=settings)

    result = agent.invoke(
        {
            "messages": [("user", "Gere o relatório SRAG")],
        }
    )

    print("\n" + "=" * 80)
    print("RELATÓRIO SRAG GERADO")
    print("=" * 80)
    print(result.get("report_markdown", "No report generated"))

    if result.get("report_pdf_path"):
        print(f"\nPDF salvo em: {result['report_pdf_path']}")

    metrics = result.get("metrics", {})
    if metrics:
        print("\nMétricas:")
        for key, value in metrics.items():
            if key != "warnings":
                print(f"  {key}: {value}")
        if "warnings" in metrics:
            print("\nAvisos:")
            for w in metrics["warnings"]:
                print(f"  {w}")


if __name__ == "__main__":
    main()
