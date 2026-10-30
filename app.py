from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analysis_engine import analyze_datasets
from src.agents.reasoning_agent import explain_findings
from src.utils.data_loader import load_csv


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"

st.set_page_config(
    page_title="DataSentinel AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------
# STYLING
# ---------------------------------------------------------

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.4rem;
        font-weight: 750;
        margin-bottom: 0.1rem;
    }

    .sub-header {
        color: #9CA3AF;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }

    .status-critical {
        padding: 1rem;
        border-radius: 0.6rem;
        background-color: rgba(220, 38, 38, 0.12);
        border: 1px solid #DC2626;
    }

    .status-warning {
        padding: 1rem;
        border-radius: 0.6rem;
        background-color: rgba(217, 119, 6, 0.12);
        border: 1px solid #D97706;
    }

    .status-healthy {
        padding: 1rem;
        border-radius: 0.6rem;
        background-color: rgba(22, 163, 74, 0.12);
        border: 1px solid #16A34A;
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.25);
        padding: 1rem;
        border-radius: 0.7rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def display_value(value: Any) -> str:
    """Convert values into readable dashboard text."""

    if isinstance(value, float):
        return f"{value:,.4f}"

    if isinstance(value, dict):
        return json.dumps(value, indent=2, default=str)

    if isinstance(value, list):
        return ", ".join(str(item) for item in value)

    return str(value)


def get_status_class(status: str) -> str:
    """Return the CSS class for an overall status."""

    normalized = status.lower()

    if normalized == "critical":
        return "status-critical"

    if normalized in {"warning", "medium"}:
        return "status-warning"

    return "status-healthy"


def build_report(
    analysis: dict[str, Any],
    ai_result: dict[str, Any],
) -> dict[str, Any]:
    """Combine Python findings and optional AI reasoning."""

    explanation = ai_result.get("explanation", {})

    human_review_required = (
        analysis.get("overall_status") == "critical"
        or explanation.get("human_review_required", False)
    )

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "workflow_status": "success",
        "overall_status": analysis.get("overall_status", "unknown"),
        "analysis": analysis,
        "ai_reasoning": ai_result,
        "human_review_required": human_review_required,
    }


def render_ai_reasoning(ai_result: dict[str, Any]) -> None:
    """Display Gemma's structured reasoning."""

    if ai_result.get("status") != "success":
        st.warning(
            "AI reasoning is unavailable. The Python analysis results "
            "remain available."
        )

        if ai_result.get("error"):
            with st.expander("AI diagnostic details"):
                st.code(ai_result["error"])

        return

    explanation = ai_result.get("explanation", {})

    st.subheader("🧠 Gemma AI Analysis")

    st.markdown("#### Incident Summary")
    st.write(explanation.get("incident_summary", "No summary provided."))

    st.markdown("#### Root-Cause Hypotheses")

    hypotheses = explanation.get("root_cause_hypotheses", [])

    if hypotheses:
        for index, hypothesis in enumerate(hypotheses, start=1):
            if not isinstance(hypothesis, dict):
                continue

            with st.expander(
                f"Hypothesis {index}: "
                f"{hypothesis.get('hypothesis', 'Possible cause')}"
            ):
                st.write(
                    "**Supporting evidence:** "
                    + str(hypothesis.get("supporting_evidence", "Not provided"))
                )

                st.write(
                    "**Confidence:** "
                    + str(hypothesis.get("confidence", "Unknown")).title()
                )
    else:
        st.info("No root-cause hypotheses were returned.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Potential Business Impacts")

        impacts = explanation.get("business_impacts", [])

        if impacts:
            for impact in impacts:
                st.markdown(f"- {impact}")
        else:
            st.write("No business impacts provided.")

    with col2:
        st.markdown("#### Recommended Actions")

        actions = explanation.get("recommended_actions", [])

        if actions:
            for action in actions:
                st.markdown(f"- {action}")
        else:
            st.write("No recommended actions provided.")

    st.info(
        "AI-generated explanations are hypotheses, not verified root causes. "
        "Human review is required before production changes."
    )


# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

if "final_report" not in st.session_state:
    st.session_state.final_report = None


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:
    st.markdown("## 🛡️ DataSentinel AI")
    st.caption("Intelligent Data Quality Monitoring")

    st.divider()

    st.markdown("### How it works")
    st.markdown(
        """
        1. Upload trusted baseline data.
        2. Upload current pipeline data.
        3. Detect data-quality anomalies.
        4. Ask Gemma to explain findings.
        5. Review and export the report.
        """
    )

    st.divider()

    st.markdown("### Analysis Engine")
    st.write("Python · Pandas · Statistical Detection")

    st.markdown("### Reasoning Engine")
    st.write("Gemma via Ollama")

    st.markdown("### Orchestration")
    st.write("LangGraph")

    if st.button("Clear Analysis", use_container_width=True):
        st.session_state.analysis_results = None
        st.session_state.ai_result = None
        st.session_state.final_report = None
        st.rerun()


# ---------------------------------------------------------
# MAIN HEADER
# ---------------------------------------------------------

st.markdown(
    '<div class="main-header">🛡️ DataSentinel AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="sub-header">
        Detect silent data pipeline failures before they affect downstream systems.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    DataSentinel AI compares trusted baseline data against current data,
    identifies anomalies using deterministic Python analysis and uses
    Gemma to explain potential causes and recommend investigation steps.
    """
)


# ---------------------------------------------------------
# DATA UPLOAD
# ---------------------------------------------------------

st.subheader("📂 Upload Datasets")

left_upload, right_upload = st.columns(2)

with left_upload:
    baseline_file = st.file_uploader(
        "Trusted Baseline CSV",
        type=["csv"],
        key="baseline_upload",
        help="Upload the trusted reference dataset.",
    )

with right_upload:
    current_file = st.file_uploader(
        "Current Pipeline CSV",
        type=["csv"],
        key="current_upload",
        help="Upload the latest dataset to investigate.",
    )


# ---------------------------------------------------------
# ANALYSIS CONTROLS
# ---------------------------------------------------------

run_analysis = st.button(
    "🔍 Analyze Datasets",
    type="primary",
    use_container_width=True,
    disabled=baseline_file is None or current_file is None,
)


if run_analysis:
    st.session_state.analysis_results = None
    st.session_state.ai_result = None
    st.session_state.final_report = None

    try:
        with st.spinner("Loading and validating datasets..."):
            baseline_df = load_csv(baseline_file)
            current_df = load_csv(current_file)

        if baseline_df.empty or current_df.empty:
            st.error("Both datasets must contain data rows.")
            st.stop()

        with st.spinner("Detecting data-quality anomalies..."):
            analysis_results = analyze_datasets(
                baseline=baseline_df,
                current=current_df,
            )

        st.session_state.analysis_results = analysis_results

        st.success("Python data-quality analysis completed.")

        # Run Gemma separately so AI failure does not erase Python findings.
        with st.spinner(
            "Gemma is analyzing the findings. "
            "This may take some time on a CPU-only machine..."
        ):
            ai_result = explain_findings(analysis_results)

        st.session_state.ai_result = ai_result

        st.session_state.final_report = build_report(
            analysis_results,
            ai_result,
        )

        if ai_result.get("status") == "success":
            st.success("Gemma reasoning completed.")
        else:
            st.warning(
                "Python analysis succeeded, but Gemma reasoning failed. "
                "You can still inspect and export the detected findings."
            )

    except Exception as exc:
        st.error(f"Analysis could not be completed: {exc}")


# ---------------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------------

analysis = st.session_state.analysis_results
ai_result = st.session_state.ai_result
final_report = st.session_state.final_report


if analysis:
    st.divider()
    st.subheader("📊 Data Quality Overview")

    overall_status = str(analysis.get("overall_status", "unknown"))
    severity_counts = analysis.get("severity_counts", {})
    findings = analysis.get("findings", [])

    status_class = get_status_class(overall_status)

    st.markdown(
        f"""
        <div class="{status_class}">
            <strong>Overall Status: {overall_status.upper()}</strong><br>
            {len(findings)} finding(s) detected during comparison.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:
        st.metric(
            "Baseline Rows",
            f"{analysis.get('baseline_rows', 'N/A'):,}"
            if isinstance(analysis.get("baseline_rows"), (int, float))
            else "N/A",
        )

    with metric2:
        st.metric(
            "Current Rows",
            f"{analysis.get('current_rows', 'N/A'):,}"
            if isinstance(analysis.get("current_rows"), (int, float))
            else "N/A",
        )

    with metric3:
        st.metric("Total Findings", len(findings))

    with metric4:
        st.metric(
            "High Severity",
            severity_counts.get("high", 0),
        )

    st.markdown("#### Findings by Severity")

    if severity_counts:
        severity_df = pd.DataFrame(
            [
                {"Severity": severity.title(), "Count": count}
                for severity, count in severity_counts.items()
            ]
        )

        fig = px.bar(
            severity_df,
            x="Severity",
            y="Count",
            color="Severity",
            title="Detected Anomalies by Severity",
            text="Count",
        )

        fig.update_layout(
            showlegend=False,
            xaxis_title="Severity",
            yaxis_title="Number of Findings",
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🚨 Detected Anomalies")

    if findings:
        for index, finding in enumerate(findings, start=1):
            severity = str(finding.get("severity", "unknown")).upper()
            finding_type = str(
                finding.get("type", "unknown")
            ).replace("_", " ").title()

            with st.expander(
                f"{index}. [{severity}] {finding_type}",
                expanded=index == 1,
            ):
                for key, value in finding.items():
                    if key in {"type", "severity"}:
                        continue

                    st.markdown(f"**{key.replace('_', ' ').title()}**")
                    st.write(display_value(value))

    else:
        st.success("No anomalies were detected.")

    st.divider()

    if ai_result:
        render_ai_reasoning(ai_result)

    st.divider()
    st.subheader("🛡️ Human Review")

    review_required = (
        final_report.get("human_review_required", True)
        if final_report
        else overall_status == "critical"
    )

    if review_required:
        st.error(
            "Human review required. Do not make production data changes "
            "based solely on automated recommendations."
        )
    else:
        st.info(
            "Review the findings and recommendations before taking action."
        )

    st.divider()
    st.subheader("📥 Export Report")

    if final_report:
        report_json = json.dumps(
            final_report,
            indent=2,
            default=str,
        )

        st.download_button(
            label="Download Full Report (JSON)",
            data=report_json,
            file_name="datasentinel_report.json",
            mime="application/json",
            use_container_width=True,
        )

        if st.button("Save Report to Project Folder"):
            try:
                REPORTS_DIR.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = (
                    REPORTS_DIR / f"datasentinel_report_{timestamp}.json"
                )

                report_path.write_text(
                    report_json,
                    encoding="utf-8",
                )

                st.success(f"Report saved to {report_path}")

            except OSError as exc:
                st.error(f"Could not save the report: {exc}")

else:
    st.info(
        "Upload a baseline CSV and a current CSV, then select "
        "**Analyze Datasets** to begin."
    )

    st.markdown("### What DataSentinel AI checks")

    feature1, feature2 = st.columns(2)

    with feature1:
        st.markdown(
            """
            **📋 Schema Changes**
            - Added or removed columns
            - Incompatible data types

            **🕳️ Missing Values**
            - Missing-value increases
            - Newly incomplete columns
            """
        )

    with feature2:
        st.markdown(
            """
            **📑 Duplicate Records**
            - Duplicate row increases

            **📈 Distribution Drift**
            - Numerical distribution changes
            - Unexpected categorical changes
            """
        )