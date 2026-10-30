
from __future__ import annotations

import json
from typing import Any

import requests


OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 300


def _build_prompt(analysis_results: dict[str, Any]) -> str:
    """Build a concise prompt from findings calculated by Python."""

    evidence = {
        "overall_status": analysis_results.get("overall_status"),
        "total_findings": analysis_results.get("total_findings", 0),
        "severity_counts": analysis_results.get("severity_counts", {}),
        "baseline_rows": analysis_results.get("baseline_rows"),
        "current_rows": analysis_results.get("current_rows"),
        "findings": analysis_results.get("findings", []),
    }

    return f"""
You are the incident analysis agent for DataSentinel AI.

Your job is to explain ALL anomalies detected by Python.

PYTHON ANALYSIS EVIDENCE:
{json.dumps(evidence, indent=2, default=str)}

Requirements:

1. Summarize the overall incident and mention the most important findings.
2. Review EVERY finding supplied by Python.
3. Include at least one root-cause hypothesis for each finding.
4. Link each hypothesis to specific evidence from the findings.
5. Explain the potential business impact of each major anomaly.
6. Recommend practical investigation and prevention steps.
7. Clearly distinguish confirmed measurements from possible causes.
8. Do not invent statistics, measurements, logs, or causes.
9. Do not claim to have inspected external systems.
10. Do not recommend automatically modifying or deleting production data.
11. Require human review before production changes.
12. Keep the response concise but cover every finding.

Return valid JSON only, without Markdown fences, using exactly this structure:

{{
    "incident_summary": "Overall incident summary covering the major findings",
    "root_cause_hypotheses": [
        {{
            "hypothesis": "Possible explanation for a detected anomaly",
            "supporting_evidence": "Specific supplied finding supporting this hypothesis",
            "confidence": "low, medium, or high"
        }}
    ],
    "business_impacts": [
        "Potential business impact linked to a detected anomaly"
    ],
    "recommended_actions": [
        "Specific investigation or corrective action"
    ],
    "human_review_required": true
}}

Include at least one hypothesis per finding. If there are four findings,
include at least four hypotheses. Do not present hypotheses as confirmed causes.
""".strip()


def explain_findings(
    analysis_results: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Generate a structured explanation using a local Ollama model."""

    if not isinstance(analysis_results, dict):
        raise TypeError("analysis_results must be a dictionary.")

    if not model or not model.strip():
        raise ValueError("model must be a non-empty string.")

    if timeout < 1:
        raise ValueError("timeout must be at least 1 second.")

    payload = {
        "model": model,
        "prompt": _build_prompt(analysis_results),
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 1000,
        },
    }

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "model": model,
            "error": f"Ollama did not respond within {timeout} seconds.",
        }

    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "model": model,
            "error": (
                "Cannot connect to Ollama. Ensure Ollama is running "
                "and its local API is available."
            ),
        }

    except requests.exceptions.HTTPError as exc:
        return {
            "status": "error",
            "model": model,
            "error": f"Ollama returned an HTTP error: {exc}",
        }

    except requests.exceptions.RequestException as exc:
        return {
            "status": "error",
            "model": model,
            "error": f"Unable to contact Ollama: {exc}",
        }

    try:
        api_result = response.json()
        generated_text = api_result.get("response", "")

        if (
            not isinstance(generated_text, str)
            or not generated_text.strip()
        ):
            raise ValueError("Ollama returned an empty response.")

        explanation = json.loads(generated_text)

        required_keys = {
            "incident_summary",
            "root_cause_hypotheses",
            "business_impacts",
            "recommended_actions",
            "human_review_required",
        }

        if not isinstance(explanation, dict):
            raise ValueError("The AI response must be a JSON object.")

        missing_keys = required_keys - explanation.keys()

        if missing_keys:
            raise ValueError(
                f"The AI response is missing keys: {sorted(missing_keys)}"
            )

        if not isinstance(explanation["incident_summary"], str):
            raise ValueError("incident_summary must be a string.")

        if not isinstance(explanation["root_cause_hypotheses"], list):
            raise ValueError("root_cause_hypotheses must be a list.")

        if not isinstance(explanation["business_impacts"], list):
            raise ValueError("business_impacts must be a list.")

        if not isinstance(explanation["recommended_actions"], list):
            raise ValueError("recommended_actions must be a list.")

        if not isinstance(explanation["human_review_required"], bool):
            raise ValueError("human_review_required must be a boolean.")

        return {
            "status": "success",
            "model": model,
            "analysis_status": analysis_results.get("overall_status"),
            "explanation": explanation,
        }

    except (ValueError, TypeError) as exc:
        return {
            "status": "error",
            "model": model,
            "error": (
                "Ollama responded, but its output did not match the "
                f"expected JSON structure: {exc}"
            ),
        }
