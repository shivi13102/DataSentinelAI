# DataSentinelAI

## Project structure

```text
DataSentinelAI/
├── .github/
│   └── workflows/
├── data/
│   ├── processed/
│   └── raw/
│       ├── baseline.csv
│       └── current.csv
├── frontend/
│   ├── public/
│   │   ├── favicon.svg
│   │   └── icons.svg
│   ├── src/
│   │   ├── assets/
│   │   │   ├── hero.png
│   │   │   ├── react.svg
│   │   │   └── vite.svg
│   │   ├── App.css
│   │   ├── App.tsx
│   │   ├── index.css
│   │   └── main.tsx
│   ├── .gitignore
│   ├── .oxlintrc.json
│   ├── index.html
│   ├── package-lock.json
│   ├── package.json
│   ├── README.md
│   ├── tsconfig.app.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
├── reports/
│   ├── ai_reasoning.json
│   ├── analysis_20261030T105258Z_1c5e721f.json
│   └── sample_analysis.json
├── scripts/
│   ├── generate_sample_data.py
│   ├── test_analysis.py
│   ├── test_reasoning_agent.py
│   └── test_workflow.py
├── src/
│   ├── agents/
│   │   ├── reasoning_agent.py
│   │   └── __init__.py
│   ├── detectors/
│   │   ├── categorical_drift_detector.py
│   │   ├── distribution_detector.py
│   │   ├── duplicate_detector.py
│   │   ├── missing_value_detector.py
│   │   ├── schema_detector.py
│   │   └── __init__.py
│   ├── graph/
│   │   ├── workflow.py
│   │   └── __init__.py
│   ├── utils/
│   │   ├── data_loader.py
│   │   └── __init__.py
│   ├── analysis_engine.py
│   ├── protection_gate.py
│   └── __init__.py
├── tests/
│   ├── test_analysis_engine.py
│   ├── test_categorical_drift_detector.py
│   ├── test_data_loader.py
│   ├── test_distribution_detector.py
│   ├── test_duplicate_detector.py
│   ├── test_missing_value_detector.py
│   ├── test_protection_gate.py
│   └── test_schema_detector.py
├── .gitignore
├── api.py
├── app.py
├── README.md
└── requirements.txt
```

Generated environments, dependency directories, and Python cache files such as
`.venv/`, `frontend/node_modules/`, `__pycache__/`, and `.pytest_cache/` are not
shown.