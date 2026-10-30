from __future__ import annotations

import json
from typing import Any

import requests


OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:1b"
DEFAULT_TIMEOUT = 300
MAX_OUTPUT_TOKENS = 1200


def _build_prompt(analysis_results: dict[str, Any]) -> str:
    """Build a concise prompt from evidence calculated by Python."""

    findings = analysis_results.get("findings", [])

    if not isinstance(findings, list):
        raise ValueError("analysis_results findings must be a list.")

    valid_findings = [
        finding
        for finding in findings
        if isinstance(finding, dict)
    ]

    evidence = {
        "overall_status": analysis_results.get("overall_status"),
        "total_findings": len(valid_findings),
        "findings": [
            {
                "finding_number": index,
                "type": finding.get("type"),
                "severity": finding.get("severity"),
                "evidence": {
                    key: value
                    for key, value in finding.items()
                    if key not in {"type", "severity"}
                },
            }
            for index, finding in enumerate(valid_findings, start=1)
        ],
    }

    return f"""
You are Gemma, the reasoning engine of DataSentinel AI.

Analyze the following data-quality findings calculated by Python.
Your task is to explain the evidence, suggest possible causes,
identify potential business impacts, and recommend investigation steps.

EVIDENCE:
{json.dumps(evidence, separators=(",", ":"), default=str)}

RULES:
1. Produce exactly one root-cause hypothesis for each finding.
2. Follow the finding order and reference each finding's evidence.
3. Clearly treat causes as hypotheses, not confirmed facts.
4. Do not invent measurements or external system information.
5. Recommend investigation and verification, not automatic data changes.
6. Keep explanations concise and specific to the supplied evidence.
7. Human review is mandatory before production data changes.
8. Return only the JSON object matching the required output schema.
""".strip()


def _build_output_schema(expected_findings: int) -> dict[str, Any]:
    """Build a JSON schema for Ollama structured output."""

    return {
        "type": "object",
        "properties": {
            "incident_summary": {
                "type": "string",
            },
            "root_cause_hypotheses": {
                "type": "array",
                "minItems": expected_findings,
                "maxItems": expected_findings,
                "items": {
                    "type": "object",
                    "properties": {
                        "hypothesis": {
                            "type": "string",
                        },
                        "supporting_evidence": {
                            "type": "string",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": [
                        "hypothesis",
                        "supporting_evidence",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
            "business_impacts": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "recommended_actions": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "human_review_required": {
                "type": "boolean",
            },
        },
        "required": [
            "incident_summary",
            "root_cause_hypotheses",
            "business_impacts",
            "recommended_actions",
            "human_review_required",
        ],
        "additionalProperties": False,
    }


def _validate_explanation(
    explanation: dict[str, Any],
    expected_findings: int,
) -> None:
    """Validate the completeness of the generated explanation."""

    if not isinstance(explanation, dict):
        raise ValueError("The AI response must be a JSON object.")

    required_keys = {
        "incident_summary",
        "root_cause_hypotheses",
        "business_impacts",
        "recommended_actions",
        "human_review_required",
    }

    missing_keys = required_keys - explanation.keys()

    if missing_keys:
        raise ValueError(
            f"The AI response is missing keys: {sorted(missing_keys)}"
        )

    summary = explanation["incident_summary"]

    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("incident_summary must be a non-empty string.")

    hypotheses = explanation["root_cause_hypotheses"]

    if not isinstance(hypotheses, list):
        raise ValueError("root_cause_hypotheses must be a list.")

    if len(hypotheses) != expected_findings:
        raise ValueError(
            f"Expected exactly {expected_findings} root-cause hypotheses, "
            f"but received {len(hypotheses)}."
        )

    for index, hypothesis in enumerate(hypotheses, start=1):

        if not isinstance(hypothesis, dict):
            raise ValueError(
                f"Hypothesis {index} must be a JSON object."
            )

        required_hypothesis_keys = {
            "hypothesis",
            "supporting_evidence",
            "confidence",
        }

        missing_hypothesis_keys = (
            required_hypothesis_keys - hypothesis.keys()
        )

        if missing_hypothesis_keys:
            raise ValueError(
                f"Hypothesis {index} is missing fields: "
                f"{sorted(missing_hypothesis_keys)}"
            )

        for field in ("hypothesis", "supporting_evidence"):
            value = hypothesis[field]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Hypothesis {index}: {field} must be a "
                    "non-empty string."
                )

        if hypothesis["confidence"] not in {"low", "medium", "high"}:
            raise ValueError(
                f"Hypothesis {index}: confidence must be "
                "low, medium, or high."
            )

    for field in ("business_impacts", "recommended_actions"):

        items = explanation[field]

        if not isinstance(items, list):
            raise ValueError(f"{field} must be a list.")

        if not items:
            raise ValueError(f"{field} cannot be empty.")

        if not all(
            isinstance(item, str) and item.strip()
            for item in items
        ):
            raise ValueError(
                f"Every item in {field} must be a non-empty string."
            )

    if explanation["human_review_required"] is not True:
        raise ValueError(
            "Human review must be required before production changes."
        )


def explain_findings(
    analysis_results: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Generate a validated explanation using a local Ollama model."""

    if not isinstance(analysis_results, dict):
        raise TypeError("analysis_results must be a dictionary.")

    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string.")

    if (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or timeout < 1
    ):
        raise ValueError("timeout must be a positive integer.")

    findings = analysis_results.get("findings", [])

    if not isinstance(findings, list):
        raise ValueError("analysis_results findings must be a list.")

    valid_findings = [
        finding
        for finding in findings
        if isinstance(finding, dict)
    ]

    expected_findings = len(valid_findings)

    payload = {
        "model": model,
        "prompt": _build_prompt(analysis_results),
        "stream": False,
        "format": _build_output_schema(expected_findings),
        "options": {
            "temperature": 0,
            "num_predict": MAX_OUTPUT_TOKENS,
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

        if not isinstance(api_result, dict):
            raise ValueError(
                "Ollama API response must be a JSON object."
            )

        generated_text = api_result.get("response", "")

        if (
            not isinstance(generated_text, str)
            or not generated_text.strip()
        ):
            raise ValueError("Ollama returned an empty response.")

        if api_result.get("done") is False:
            raise ValueError(
                "Ollama did not finish generating the response."
            )

        explanation = json.loads(generated_text)

        _validate_explanation(
            explanation=explanation,
            expected_findings=expected_findings,
        )

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