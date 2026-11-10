# NEKOMOのデータ検証と再現手順

公開済みのCADとスライスを使って確認します。比較例はv08とv09です。[版一覧](バスの版一覧.md)から他の版の設計と記録も確認できます。

## 1. 取得直後の検証

GitとPython 3.12を用意し、リポジトリの直下で実行します。

```powershell
git clone https://github.com/Sunwood-ai-labs/NEKOMO.git
cd NEKOMO
python tools/update_manifest.py --check
python tools/verify_snapshot.py
```

最初の検査はGitの追跡対象とマニフェストの対応を調べます。次の検査は各ファイルのSHA-256、文書リンク、CAD・3MFの格納構造とレビュー記録を確認します。両方ともPythonの標準ライブラリで動きます。

## 2. 保存3MFのサポート材を検査

```powershell
python quality/support-removal-preflight.py --help
python quality/support-removal-preflight.py designs/school-bus-v09-sloped/exports/sloped-two-color-sliced.3mf
python quality/support-removal-preflight.py designs/school-bus-v06-empty-inverted/two-color-red-tyres/red-tyres-inverted-sliced.3mf
```

| 例 | 期待する結果 | 終了コード |
| --- | --- | --- |
| v09傾斜ボンネット | `PASS_FILE_ONLY`。保存3MFのファイル検査を通過 | 0 |
| v06赤タイヤ | `BLOCK`。専用サポート材の界面割当が確認できない旧データ | 1 |

検査対象は3MFに含まれる設定とG-codeです。AMSの実際の配置、サポートの除去結果、造形可否は[DR手順](../.agents/skills/nekomo-dr-review/references/stages.md)で個別に扱います。GitHub Actionsもこの2件の結果と、取得直後の検証を確認します。

## 3. v08とv09のボンネットの経路を比較

NumPyを使えるPythonを用意します。次のPowerShell手順は入力とスクリプトを一時フォルダにコピーし、結果もそこへ保存します。

```powershell
$reproRoot = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
$v08 = Join-Path $reproRoot 'school-bus-v08-photo'
$v09 = Join-Path $reproRoot 'school-bus-v09-sloped'
New-Item -ItemType Directory -Path "$v08/exports", "$v09/exports", "$v09/evidence" | Out-Null
Copy-Item -LiteralPath designs/school-bus-v08-photo/exports/fast-two-color-sliced.3mf -Destination "$v08/exports/"
Copy-Item -LiteralPath designs/school-bus-v09-sloped/exports/sloped-two-color-sliced.3mf -Destination "$v09/exports/"
Copy-Item -LiteralPath designs/school-bus-v09-sloped/verify_toolpaths.py -Destination $v09
python "$v09/verify_toolpaths.py"
```

Python 3.12.10とNumPy 2.5.3で再実行し、スクリプトのすき間のしきい値を超えた抽出点はv08で858件／18,030点、v09で0件／25,497点でした。結果は一時フォルダ内の `school-bus-v09-sloped/evidence/toolpath-overlap.json` に出ます。測定範囲はボンネット中央の経路で、接着や仕上がりは現物の評価項目です。

## 4. v09のCAD生成とスライスを試す

保存済みの形状はFreeCADで [sloped-bus.FCStd](../designs/school-bus-v09-sloped/cad/sloped-bus.FCStd) を開いて確認できます。生成コードは [build_sloped.py](../designs/school-bus-v09-sloped/build_sloped.py) です。FreeCADのGUI用モジュールを使うため、FreeCADのPythonコンソールで次を実行します。最初のパスは取得先に合わせて変更します。

```python
from pathlib import Path
from tempfile import mkdtemp

source = Path(r'C:\path\to\NEKOMO\designs\school-bus-v09-sloped\build_sloped.py')
output = Path(mkdtemp(prefix='nekomo-v09-'))
for folder in ('cad', 'exports', 'evidence'):
    (output / folder).mkdir()
code = source.read_text(encoding='utf-8')
original = "ROOT='C:/Prj/NEKOMO/designs/school-bus-v09-sloped'"
if code.count(original) != 1:
    raise ValueError('Archived v09 output path has changed')
code = code.replace(original, 'ROOT=' + repr(output.as_posix()), 1)
exec(compile(code, str(source), 'exec'), {'__name__': '__main__'})
print(output)
```

1. 出力先の `cad/sloped-bus.FCStd`、`exports/sloped-bus.step`、色別STL、`evidence/geometry.json` を確認します。
2. Bambu Studioで [v09の保存3MF](../designs/school-bus-v09-sloped/exports/sloped-two-color-sliced.3mf) を開き、プリンター、材料、配置、レイヤー、サポート設定を参照します。
3. 再生成した `RedBodyAndTires-inverted.stl` と `WhiteRoof-inverted.stl` を同じ座標を共有する別パーツとして読み込み、赤い車体・タイヤと白い屋根に材料を割り当てます。STLは逆さ姿勢で書き出すため、保存3MFの配置と比較して向きを確認します。
4. 保存3MFの条件に合わせてスライスします。レイヤー表示で形状・色領域を確認し、G-codeを含むスライス済み3MFを別名で書き出します。手順2のファイル検査を新しい3MFにも実行します。

この節はアーカイブのコードとデータから確認した手順です。今回の整備ではCADの再生成と再スライスまでは実行していません。FreeCAD、形状計算ライブラリ、スライサーの版や設定が変わると生成データも変わるため、保存済みのファイルとのバイト一致は確認項目に含めません。

## 5. 公開ファイルを更新

1. 公開する変更を確認し、対象ファイルを指定して `git add` します。
2. `python tools/update_manifest.py` で、Gitの追跡対象からマニフェストを更新します。
3. `python tools/update_manifest.py --check` と `python tools/verify_snapshot.py` を実行します。
4. `git add -- public-manifest.json` を実行し、ステージ済みの差分を確認してコミットします。
