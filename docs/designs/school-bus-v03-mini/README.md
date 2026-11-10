# NEKOMOスクールバス v03 mini

全長60 mmの小型スクールバス試作です。3歳未満向けを設計目標にしていますが、現時点では成人が形状と組付けを確認するための試作です。子ども向け使用は承認されておらず、小型化後の耐久性と安全性も評価していません。

画像はローカル保存

画像はローカル保存

## 寸法と配色

CAD上の組立外形は60.00 × 31.824 × 35.568 mmです。車輪は直径12.73 mmの固定輪です。

| 部品 | モデル色 |
| --- | --- |
| 車体 | 白。赤い帯、グリル、ライト外周があります。 |
| シャーシ | 赤。ハブは白です。 |
| 屋根 | 赤。 |

AMSの装填表示はA1が白PLA、A2が白PLA-S（Support for PLA）、A3が赤PLA、A4が空です。送信時の割当予定は次のとおりです。

| 部品 | モデル材とサポート材の割当予定 |
| --- | --- |
| 車体 | 白A1、赤A3、サポートA2。 |
| シャーシ | 赤A3、白A1、サポートA2。 |
| 屋根 | 赤A3、サポートA2。 |

プリンターへ送信していないため、AMS割当の実績はありません。現物の色味と色境界も未確認です。

[3DBenchy公式寸法](https://www.3dbenchy.com/dimensions/)は60 × 31 × 48 mmです。v03 miniの全長は同じで、幅は0.824 mm広く、高さは12.432 mm低くなっています。これは寸法だけの比較で、プリンター内蔵サンプルのファイルは特定していません。

## CADと確認記録

設計データは[編集可能なFreeCAD文書](../../../designs/school-bus-v03-mini/cad/nekomo-school-bus-v03.FCStd)と[STEP組立形状](../../../designs/school-bus-v03-mini/exports/school-bus-v03-assembly.step)です。形状の根拠はCAD形状レポート（ローカル保存）とメッシュ検査（ローカル保存）にあります。組付け手順は組付けと嵌合（ローカル保存）にまとめました。

| 部品 | スライス済み3MF |
| --- | --- |
| 車体 | [final-body-sliced.3mf](../../../designs/school-bus-v03-mini/print/final-body-sliced.3mf) |
| シャーシ | [final-chassis-sliced.3mf](../../../designs/school-bus-v03-mini/print/final-chassis-sliced.3mf) |
| 屋根 | [final-roof-sliced.3mf](../../../designs/school-bus-v03-mini/print/final-roof-sliced.3mf) |

3部品の3MFはファイル検査済みです。スライサー予測の合計は約7時間25分33秒、約113.94 g、色替え116回です。材料予測には支持材とパージタワーを含みます。プリンターへ送信しておらず、実際の造形時間と材料量は確認していません。予測記録（ローカル保存）
