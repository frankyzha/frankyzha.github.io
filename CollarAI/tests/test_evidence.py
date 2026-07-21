from __future__ import annotations

import json

from collarai.evidence import EvidenceStore
from collarai.models import LegacyDebtRefinancingResult


def test_historical_debt_results_remain_readable(tmp_path) -> None:
    run_id = "11111111-1111-1111-1111-111111111111"
    store = EvidenceStore(tmp_path)
    run_dir = store.create_run(run_id)
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "operation": "sum_debt_refinancing_transactions",
                "run_id": run_id,
                "status": "complete",
                "platform": "pitchbook",
                "request": {"platform": "pitchbook", "company_name": "Nvidia"},
                "transactions": [],
                "total_amount_usd": 42,
            }
        ),
        encoding="utf-8",
    )

    result = store.load_result(run_id)

    assert isinstance(result, LegacyDebtRefinancingResult)
    assert result.total_amount_usd == 42
