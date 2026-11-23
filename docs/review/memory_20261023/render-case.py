"""고정 인식 JSON/같은 세 배치 비교를 저장소 밖으로만 출력한다."""
import runpy
from pathlib import Path
root=Path('F:/sheet-music-helper-beta-cf4dd44-20261019')
out=Path(__file__).parent/'render-output'
ns=runpy.run_path(str(root/'docs/review/label_lanes_20261019/make-preview.py'))
g=ns['main_preview'].__globals__
g.update(ROOT=out,OUT=out/'figures',LOCAL=out/'pages')
g['OUT'].mkdir(parents=True,exist_ok=True);g['LOCAL'].mkdir(parents=True,exist_ok=True)
ns['main_preview']()
