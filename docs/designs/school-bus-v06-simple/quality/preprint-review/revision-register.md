# v06-simple 品質文書の版・証拠台帳

## 正本と審査記録

版: 0.1.0  
状態: DR0正本と品質文書の初期版を登録  
日付: 2026-11-09

DR0のbefore/after記録は親担当が `ローカル保存 に保存した。品質文書はその補足であり、DR0の別記録ではない。

| 対象 | 状態 | 保存先 | SHA-256 |
| --- | --- | --- | --- |
| DR0 before入力 r00 | 親担当の正本 | `reviews/DR0/before/user-input-r00.txt` | `2BB49C2477D599BEC29AD7E1CFF44EA9A9CDDE40ADAAF95695B57B27ACDCF1EC` |
| DR0 after判定 r00 | 親担当の正本 | `reviews/DR0/after/parent-decision-r00.md` | `2F2E888787F33DD4F9425762DC3A431CCE3485297E92D6BC8C277974D56AC2C6` |

親担当のDR0正本は、それぞれ同じフォルダーのmanifestにファイルパスとSHA-256を記録している。品質文書の版保存は次の表のとおりである。文書のSHA-256はファイル全体に対して計算した。

| 文書 | 版・状態 | 保存先 | SHA-256 |
| --- | --- | --- | --- |
| 要求仕様 | 0.1.0、初期品質案 | `revisions/requirements-v0.1.0-initial-quality-draft.md` | `8854CF8A8AC6E41886E329A476583723A8368582C648F9CF25590E57C32BA73C` |
| 要求仕様 | 0.2.0、DR0判定反映後 | `revisions/requirements-v0.2.0-after-dr0.md` | `F919C4F2CF1F1C841393D0BDE83B305BD955BE7D67D96C738255BDDC3C7ADCBA` |
| DFMEA | 0.1.0、CADレビュー前 | `revisions/dfmea-v0.1.0-before-cad-review.md` | `4C76469C896E39D77ACB10BCAAE940BCB99F95AD23B00D6D1AFAD5B1DDFB1BEA` |
| PFMEA | 0.1.0、スライスレビュー前 | `revisions/pfmea-v0.1.0-before-slice-review.md` | `1D8632D4BDAD8BCE1D27BE358F5C35044CC6B27F9498C5C349DAB61D3812F656` |
| 試験計画 | 0.1.0、初回造形前 | `revisions/test-plan-v0.1.0-before-trial.md` | `6B3E2367BA0AB3FC6365ED7A6A657AA657EE0A9B5BCE585111250FEF750AF309` |
| 審査状況 | 0.1.0、初期記録 | `revisions/dr-review-v0.1.0-initial.md` | `B9A6D775487412FE4F0FCE275439F22433BE94AC91393ADDB863E79E1B4F066D` |

## 指摘から再確認までの対応

| ID | 指摘・決定 | 品質文書への反映 | 再確認と状態 |
| --- | --- | --- | --- |
| Q-01 | DR0で約40 × 20 × 22 mm級の別案、車内・座席・組立の削除を確認した。 | `requirements.md` R-02〜R-04に記載した。 | 親担当のDR0 afterと照合した。CADは未生成で、寸法と形状の確認は保留。 |
| Q-02 | タイヤの形を浅い円形Pocketにし、回転させない案を選んだ。 | `requirements.md` R-06、`dfmea.md` D-02に記載した。 | 文書の要求反映を照合した。CAD上の形状と欠けは未確認。 |
| Q-03 | 45分印刷と冷却・取外し15分を目標にし、予測値と実測値を分ける。 | `requirements.md` R-09、`test-plan.md` T-05、T-07に記載した。 | 時間の記録方法を照合した。スライス予測と実測は未取得。 |
| Q-04 | 旧v04の34 mm幅条件を小型別案へ流用しない。 | `requirements.md` の要望内容に記載した。 | v04要求仕様を参照し、v06の条件から除外した。v06のCAD幅は未確認。 |
| Q-05 | 親担当の工程候補は単色赤PLA Basic、0.4 mm、0.20 mm、3 walls、15% gyroidである。 | `requirements.md` と`pfmea.md`に初期候補として記載した。 | 親担当の読み取り専用メッセージと照合した。実機ノズル、最終3MF、現物は未確認。 |

## DR1以降の保存状況

DR1〜DR4の親担当によるbefore/after manifestはまだ保存されていない。本書のFMEAと試験計画はCAD・スライス前の予備文書であり、DR1またはDR2の合格記録ではない。各審査を実施した担当が `reviews/DRx/before/` と `reviews/DRx/after/` に入力・判定の写しとmanifestを保存する。CAD、メッシュ、3MF、試作品のハッシュも該当段階に追加する。設計指摘、変更箇所、再確認結果を一組で記録する。

品質文書を更新するときは版番号を上げ、旧版を残し、新しい版のSHA-256を本台帳に追記する。ハッシュ値は現物評価や内容の妥当性を示さない。
