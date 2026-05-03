"""Logic-Checker-Flow demo — find contradictions in a sample document."""
from __future__ import annotations

from praxia import Praxia
from praxia.flows import LogicCheckerFlow

SAMPLE = """
# 新製品 A の市場戦略案

## 1. 市場概観
日本国内のスマート家電市場は 2024 年に 1 兆円規模に達し、年率 8% で成長している。
特に 30 代女性を中核ターゲットとした製品の伸長が著しい。

## 2. ターゲット顧客
当社の新製品 A の主要ターゲットは 60 代以上のシニア層である。
彼らは可処分所得が高く、健康志向の高い製品を好む。

## 3. 価格戦略
30 代の女性層が無理なく購入できる価格帯として、
税込 19,800 円を想定する。シニア層には別ラインで対応する。

## 4. 流通戦略
量販店ではなく、口コミ中心のオンライン直販チャネルに絞る。
"""


def main() -> None:
    loom = Praxia(user_id="bob", default_model="auto")
    result = loom.run(LogicCheckerFlow, inputs={"document": SAMPLE})

    print("\n=== Reader's verdict ===\n")
    print(result.final_output)
    print("\n=== Contradictions found ===\n")
    print(result.step_outputs["contradiction"].output)


if __name__ == "__main__":
    main()
