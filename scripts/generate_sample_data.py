from pathlib import Path

import numpy as np
import pandas as pd


def generate_sample_data() -> None:
    """Generate baseline and intentionally anomalous CSV datasets."""

    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)
    number_of_rows = 1000

    # Trusted historical dataset.
    baseline = pd.DataFrame(
        {
            "transaction_id": np.arange(1, number_of_rows + 1),
            "customer_age": rng.integers(18, 75, number_of_rows),
            "transaction_amount": rng.normal(
                loc=500,
                scale=120,
                size=number_of_rows,
            ).round(2),
            "payment_status": rng.choice(
                ["Approved", "Pending", "Rejected"],
                size=number_of_rows,
                p=[0.70, 0.20, 0.10],
            ),
            "region": rng.choice(
                ["North", "South", "East", "West"],
                size=number_of_rows,
            ),
        }
    )

    baseline["transaction_amount"] = (
        baseline["transaction_amount"].clip(lower=1)
    )

    # Current dataset starts as a copy of the baseline.
    current = baseline.copy(deep=True)

    # Anomaly 1: numerical distribution shift.
    current["transaction_amount"] = (
        current["transaction_amount"] * 3
    ).round(2)

    # Anomaly 2: increased missing values.
    missing_indices = rng.choice(
        current.index,
        size=300,
        replace=False,
    )
    current.loc[missing_indices, "customer_age"] = np.nan

    # Anomaly 3: unexpected categorical values.
    current.loc[
        current.index[:250],
        "payment_status",
    ] = "Unknown"

    # Anomaly 4: duplicate rows.
    duplicate_rows = current.iloc[:100].copy()
    current = pd.concat(
        [current, duplicate_rows],
        ignore_index=True,
    )

    # Save both datasets.
    baseline_path = output_dir / "baseline.csv"
    current_path = output_dir / "current.csv"

    baseline.to_csv(baseline_path, index=False)
    current.to_csv(current_path, index=False)

    print("Sample datasets generated successfully.")
    print(f"Baseline: {baseline_path}")
    print(f"Current:  {current_path}")
    print()
    print(f"Baseline rows: {len(baseline)}")
    print(f"Current rows:  {len(current)}")
    print()
    print("Intentional anomalies:")
    print("- Transaction amounts multiplied by 3")
    print("- Increased missing customer ages")
    print("- Unexpected 'Unknown' payment statuses")
    print("- 100 duplicate rows added")


if __name__ == "__main__":
    generate_sample_data()
