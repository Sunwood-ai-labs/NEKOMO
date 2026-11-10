# NEKOMOスクールバス v04

赤白・全長60 mm級・固定輪のバスです。DRで見つかった抜け止めのない屋根と底板を見直し、屋根・車体・床・車輪を含む一体の物理形状に改訂しました。成人が評価する試作データで、子どもの使用は未承認です。

画像はローカル保存

画像はローカル保存

## 設計と造形データ

| 項目 | v04の内容 |
| --- | --- |
| 外形 | 約60 × 34 × 35.568 mm |
| 構成 | 物理形状1ソリッド、赤白2色のモデル領域、固定輪 |
| 接合対策 | 屋根と床の接合に内部補強4本。断面約2.527 × 2.059 mm |
| 造形設定 | A1 mini、0.4 mmノズル、積層0.20 mm、外周5周、充填25% |
| 支持材 | モデル用PLAの支持基部と、Support for PLAの支持界面 |
| 予測 | 8時間42分34秒、約130.45 g、色替え158回。支持材・パージ・タワー込み |
| 実施状況 | プリンター送信・加熱・印刷・現物試験なし |

AMS割当はモデル白をA1、モデル赤をA3、支持界面の白PLA-SをA2へ割り当てる予定です。白PLAと白PLA-Sは別の材料です。この割当をプリンターへ送信した実績はありません。実際の品番・色材・ロット、保管・乾燥は試料記録で確認します。

- [FreeCAD文書](../../../designs/school-bus-v04-dr/cad/nekomo-school-bus-v04.FCStd)と[STEP](../../../designs/school-bus-v04-dr/exports/bus-v04.step)
- [検査済みのスライス済み3MF](../../../designs/school-bus-v04-dr/print/final-bus-sliced.3mf)
- 配置済みプロジェクト（ローカル保存）と造形設定（ローカル保存）
- [全体STL](../../../designs/school-bus-v04-dr/exports/bus-v04-solid.stl)、[白領域](../../../designs/school-bus-v04-dr/exports/bus-v04-white.stl)、[赤領域](../../../designs/school-bus-v04-dr/exports/bus-v04-red.stl)

全体STLは一体形状の確認用です。2色で造形する場合は、白と赤の領域を同じ位置の一つのアセンブリとして扱います。色領域を独立した組立部品として印刷する計画ではありません。

## DRと評価計画

- [DR0〜DR4の判定記録](quality/preprint-review/dr-review.md)
- [要求仕様](quality/preprint-review/requirements.md)
- [設計FMEA](quality/preprint-review/dfmea.md)と[工程FMEA](quality/preprint-review/pfmea.md)
- [T-00〜T-15の試験計画](quality/preprint-review/test-plan.md)と[一次資料](quality/preprint-review/sources.md)
- 最終データの自動照合（ローカル保存）

DR0〜DR2は要求、設計と造形工程のレビューを行い、成人評価用試作に限る条件付き判定です。DR3の造形・現物試験とDR4の使用開始判定は未実施です。データ検査を積層強度、規格適合、子どもの使用承認に読み替えません。

最初の現物評価はT-00の1個です。内部支持材を取り切れない場合や、亀裂・剥離・欠けがある場合は後続試験へ進まず、設計へ戻します。材料・化学評価、清掃、指挟み、必要な燃焼・端部評価は未完了です。

## 再生成と記録

元のスケッチ履歴を保持し、拡幅後の入力形状を固定してから結合しています。元の寸法を変えた場合は[生成スクリプト](../../../designs/school-bus-v04-dr/build_bus_v04.py)で再生成し、同じ検査をやり直します。派生形状がすべて元の寸法変更へ自動追従するとは扱いません。

色領域の体積和には数値積分の残差があるため、差集合と交差で領域の過不足を別途検査しました。残差と判定方法は[DR記録](quality/preprint-review/dr-review.md)と幾何検査（ローカル保存）に残しています。
