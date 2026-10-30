from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "protection"


def build_baseline() -> pd.DataFrame:
    """Create a deterministic, balanced reference dataset."""

    return pd.DataFrame(
        {
            "record_id": range(1, 101),
            "measurement": [row % 10 for row in range(100)],
            "segment": ["A" if row % 2 == 0 else "B" for row in range(100)],
        }
    )


def build_scenarios() -> dict[str, pd.DataFrame]:
    baseline = build_baseline()

    healthy = baseline.copy(deep=True)

    suspicious = baseline.copy(deep=True)
    suspicious.loc[0:19, "measurement"] = pd.NA

    critical = baseline.drop(columns=["measurement"]).copy(deep=True)

    duplicate = pd.concat(
        [baseline, baseline.iloc[:10]],
        ignore_index=True,
    )

    numerical_drift = baseline.copy(deep=True)
    numerical_drift["measurement"] = numerical_drift["measurement"] * 4

    categorical_drift = baseline.copy(deep=True)
    categorical_drift.loc[:39, "segment"] = "C"

    multiple = suspicious.copy(deep=True)
    multiple = pd.concat(
        [multiple, multiple.iloc[:10]],
        ignore_index=True,
    )

    return {
        "healthy": healthy,
        "suspicious": suspicious,
        "critical": critical,
        "duplicate": duplicate,
        "numerical_drift": numerical_drift,
        "categorical_drift": categorical_drift,
        "multiple": multiple,
    }


def generate_fixtures() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    baseline = build_baseline()

    for scenario, current in build_scenarios().items():
        baseline.to_csv(FIXTURE_DIR / f"{scenario}_baseline.csv", index=False)
        current.to_csv(FIXTURE_DIR / f"{scenario}_current.csv", index=False)


if __name__ == "__main__":
    generate_fixtures()
