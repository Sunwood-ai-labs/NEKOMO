# NEKOMO

「ねこのAI職人たちのおもちゃ工場」。FreeCADとA1 miniを使い、バス型のおもちゃを設計・試作し、人間のレビューと造形結果から改良するプロジェクトです。

![v09の設計レンダ。白い屋根、赤い車体と固定輪、傾斜したボンネット](designs/school-bus-v09-sloped/evidence/sloped-front.png)

**v09・傾斜ボンネット**。外形42 × 21 × 24 mm。写真型のバスから、逆さ印刷時に前層へ重なるようボンネットの形状を見直しました。[FreeCADモデル](designs/school-bus-v09-sloped/cad/sloped-bus.FCStd) · [STEP](designs/school-bus-v09-sloped/exports/sloped-bus.step) · [スライス済み3MF](designs/school-bus-v09-sloped/exports/sloped-two-color-sliced.3mf) · [設計コード](designs/school-bus-v09-sloped/build_sloped.py)

[版別の設計・DR星取表](docs/バスの版一覧.md) · [人間のレビュー](docs/人間のレビュー記録.md) · [取得後の検証と再現手順](docs/reproduce.md)

## 🚌 形状と構造の変遷

大型の3部品構造、60 mm級への小型化、一体化、床を抜いた空洞構造、傾斜ボンネットを比較しています。画像は各版のCADレンダです。

| v02・大型3部品 | v03・60 mm級の3部品 |
| --- | --- |
| ![v02のCADレンダ](designs/school-bus-v02/evidence/model-v02-isometric.png) | ![v03のCADレンダ](designs/school-bus-v03-mini/evidence/model-v03-isometric.png) |
| 車体・シャーシ・屋根を分け、位置決めと部品の干渉を確認。[CAD](designs/school-bus-v02/cad/nekomo-school-bus-v02.FCStd) · [設計記録](docs/designs/school-bus-v02/版の案内.md) | 赤白の配色と60 mm級の大きさに合わせ、肉厚と組立形状を調整。[CAD](designs/school-bus-v03-mini/cad/nekomo-school-bus-v03.FCStd) · [設計記録](docs/designs/school-bus-v03-mini/版の案内.md) |

| v04・60 mm級の一体構造 | v07・40 mm級の床なし構造 |
| --- | --- |
| ![v04のCADレンダ](designs/school-bus-v04-dr/evidence/model-v04-isometric.png) | ![v07のCADレンダ](designs/school-bus-v07-open-bottom/candidate-r00/evidence/final-view-r03.png) |
| 屋根と底板を一体化し、幅34 mmの形状と内部の補強を検討。[CAD](designs/school-bus-v04-dr/cad/nekomo-school-bus-v04.FCStd) · [設計記録](docs/designs/school-bus-v04-dr/版の案内.md) | 床をなくし、窓の開口、輪の張り出し、赤白の色境界を見直し。[CAD](designs/school-bus-v07-open-bottom/candidate-r00/cad/nekomo-bus-v07-final.FCStd) · [設計記録](docs/designs/school-bus-v07-open-bottom/版の案内.md) |

| v07・底側から見る空洞 | v09・逆さ姿勢で見るボンネット |
| --- | --- |
| ![v07の底面と車内の空洞](designs/school-bus-v07-open-bottom/candidate-r00/evidence/final-underside-r03.png) | ![v09を逆さ姿勢にしたCADレンダ](designs/school-bus-v09-sloped/evidence/sloped-inverted.png) |
| 開いた底面と車内の形状を確認。G-codeでも空洞中央を横切る押出経路を検査しました。[レビュー記録](docs/designs/school-bus-v07-open-bottom/evidence/design-review-r00.md) | 前層との経路の重なりをボンネット中央で検査しました。[検査コード](designs/school-bus-v09-sloped/verify_toolpaths.py) · [比較の再実行](docs/reproduce.md) |

## 📐 版ごとの設計と成果物

10個の版フォルダーがあります。v06は40 mmのシンプル版と60 mm級の空洞版を別系統で保存し、赤タイヤ版は空洞版の派生として扱います。

| 版・派生 | 設計の内容 | FreeCAD | 印刷データ・記録 |
| --- | --- | --- | --- |
| v01 | 大型・一体固定輪。外観と窓上端の橋渡しを検討 | [CAD](designs/school-bus-v01/cad/nekomo-school-bus-v01.FCStd) | [2色3MF](designs/school-bus-v01/print/nekomo-school-bus-v01-two-color-sliced.3mf) · [案内](docs/designs/school-bus-v01/版の案内.md) |
| v02 | 車体・シャーシ・屋根の3部品 | [CAD](designs/school-bus-v02/cad/nekomo-school-bus-v02.FCStd) | [部品別3MFと記録](docs/designs/school-bus-v02/版の案内.md) |
| v03 | 60 mm級・赤白・3部品 | [CAD](designs/school-bus-v03-mini/cad/nekomo-school-bus-v03.FCStd) | [部品別3MFと記録](docs/designs/school-bus-v03-mini/版の案内.md) |
| v04 | 60 mm級・幅34 mm・一体構造 | [CAD](designs/school-bus-v04-dr/cad/nekomo-school-bus-v04.FCStd) | [3MF](designs/school-bus-v04-dr/print/final-bus-sliced.3mf) · [案内](docs/designs/school-bus-v04-dr/版の案内.md) |
| v05 | 底面2開口とサポート除去の検討 | [CAD](designs/school-bus-v05-dfam/cad/nekomo-school-bus-v05-open-underside.FCStd) | 候補本体のスライスなし · [検証片と記録](docs/designs/school-bus-v05-dfam/版の案内.md) |
| v06・シンプル | 40 × 20 × 22 mm・単色・一体 | [CAD](designs/school-bus-v06-simple/candidate-r01/cad/final-bus-r01.FCStd) | [3MF](designs/school-bus-v06-simple/candidate-r01/print/school-bus-r01-sliced.3mf) · [案内](docs/designs/school-bus-v06-simple/版の案内.md) |
| v06・空洞 | 60 mm級・床と座席を抜いた車内 | [CAD](designs/school-bus-v06-empty-inverted/corrected/nekomo-v06-clear-cabin.FCStd) | [姿勢・サポート・配色の記録](docs/designs/school-bus-v06-empty-inverted/版の案内.md) |
| v06・赤タイヤ | 赤い屋根・タイヤ、白い車体・ハブ | [CAD](designs/school-bus-v06-empty-inverted/two-color-red-tyres/nekomo-v06-red-tyres.FCStd) | [3MF](designs/school-bus-v06-empty-inverted/two-color-red-tyres/red-tyres-inverted-sliced.3mf) · [不具合報告](docs/evidence/print-quality-feedback.json) |
| v07 | 40 mm級・床なし・空洞・2色 | [CAD](designs/school-bus-v07-open-bottom/candidate-r00/cad/nekomo-bus-v07-final.FCStd) | [3MF](designs/school-bus-v07-open-bottom/candidate-r00/print/bus-two-colour-final.3mf) · [案内](docs/designs/school-bus-v07-open-bottom/版の案内.md) |
| v08 | 42 × 21 × 24 mm・写真型のボンネット | [CAD](designs/school-bus-v08-photo/cad/photo-bus-fast.FCStd) | [3MF](designs/school-bus-v08-photo/exports/fast-two-color-sliced.3mf) · [案内](docs/designs/school-bus-v08-photo/版の案内.md) |
| v09 | 42 × 21 × 24 mm・連続した傾斜ボンネット | [CAD](designs/school-bus-v09-sloped/cad/sloped-bus.FCStd) | [3MF](designs/school-bus-v09-sloped/exports/sloped-two-color-sliced.3mf) · [案内](docs/designs/school-bus-v09-sloped/版の案内.md) |

## 🔧 設計で確認していること

| 設計課題 | 確認内容・参照先 |
| --- | --- |
| 組立から一体構造へ | v02・v03の3部品から、v04で屋根・底板を一体化。要求、形状、色領域を[DR記録](docs/designs/school-bus-v04-dr/quality/preprint-review/dr-review.md)に保存 |
| 床をなくして空洞を作る | 底面開口、窓、輪、補強部の接続を確認。v06空洞系とv07小型系で比較 |
| 赤白の色を形状として扱う | 色領域の重複・欠落、3MFの材料設定、実際の押出経路を確認 |
| ボンネットを逆さに造形する | v08からv09へ傾斜を変更。保存G-codeの抽出点による[比較手順](docs/reproduce.md)を公開 |
| サポートを取り外せる構造 | 取り出す方向、工具の通り道、窓枠や屋根端の破損リスクを審査。専用材の界面割当を[preflight](quality/support-removal-preflight.py)で確認 |

## 🧪 レビューと印刷の記録

公開記録で印刷完了を確認しているのは2件です。

| 版 | 印刷完了の根拠 | 人間による現物の報告 |
| --- | --- | --- |
| v06赤タイヤ | 本人報告 | サポートがほぼ全部外れなかったとの報告。写真の配色から版を照合し、ジョブIDとの直接照合はなし |
| v09 | 実機のFINISH・100%・119層と本人報告 | 完成品の品質レビューなし |

v04には保存CADのハッシュ不一致が残っています。[照合記録](docs/evidence/v04-packaging-check.json)を確認してください。

人間の設計コメント、エージェントによる検査、機械の記録を保存しています。正式なDR3現物試験の実施記録と、DR4の子ども使用に合格した版はありません。各版の状態は[DR0〜4の星取表](docs/バスの版一覧.md)で確認できます。

| 段階 | レビューする内容 |
| --- | --- |
| DR0 要求 | 用途・対象年齢・形状や工程の要求 |
| DR1 設計 | 保存CAD、断面、肉厚、空洞、色領域 |
| DR2 工程 | 姿勢、保存3MF、G-code、材料、サポート経路 |
| DR3 現物 | 外観や除去結果の報告、測定・試験の記録 |
| DR4 判断 | 改善継続、造形開始、子どもへの使用可否 |

家庭で確認できる範囲を進めるために、[NEKOMO専用のDRスキル](.agents/skills/nekomo-dr-review/SKILL.md)と[記録ひな形](.agents/skills/nekomo-dr-review/assets/review-record.md)を用意しています。設備が必要な未実施の試験は「なし」で残します。

## ▶️ 取得して検証する

GitとPython 3.12を用意し、リポジトリ直下で実行します。

```sh
git clone https://github.com/Sunwood-ai-labs/NEKOMO.git
cd NEKOMO
python tools/update_manifest.py --check
python tools/verify_snapshot.py
```

[再現手順](docs/reproduce.md)には、サポート材のファイル検査、v08とv09の経路比較、v09のCAD生成とスライス、公開ファイルの更新方法をまとめています。GitHub Actionsでもマニフェスト、ファイルのハッシュ・リンク、保存3MFの検査を実行します。[自動検証](https://github.com/Sunwood-ai-labs/NEKOMO/actions/workflows/verify.yml)

## 📁 リポジトリの構成

```text
designs/                         版ごとのCAD・STEP・STL・3MF・制作コード
docs/                            版の案内、人間レビュー、設計審査、再現手順
.agents/skills/nekomo-dr-review/  DR0〜4の方法と記録ひな形
quality/                         サポート材のファイル検査ツール
tools/                           マニフェスト更新・スナップショット検証
```

活動の背景と品質方針は[NEKOMOのコンセプト](docs/NEKOMO-concept-and-quality.md)にまとめています。

## 📄 ライセンス

[MITライセンス](LICENSE)の適用範囲は、NEKOMOで作成したCADモデルとそのSTEP・STL出力、および制作・検証コードです。
