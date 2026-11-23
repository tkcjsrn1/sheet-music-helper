"""동일 절대 입력과 기본 GUI 설정으로 제품 브랜치 간 PNG/JSON을 대조한다."""
import sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]);out=Path(sys.argv[2]);case=sys.argv[3]
sys.path.insert(0,str(root));import gui
fixed=Path('F:/akbo-data/tmp/gui-performance-20261104')
inputs={'aoharu1':fixed/'sample_images/KakaoTalk_20260731_162400402.png',
        'db1':fixed/'tests/fixtures/selftest/chopin_Db_p1.png',
        'bach1':fixed/'test_scores/bach_minuet_Am.pdf'}
source=inputs[case];assert source.is_file();out.mkdir(parents=True,exist_ok=False)
with patch('gui.base_dir',return_value=str(out)),patch.object(sys,'argv',['gui.py']):
 app=gui.SheetHelperApp();app.withdraw();app.output_dir=str(out)
 try:
  app._set_input(str(source));app._run_request=None;app._run_photo=False;app._run_minor=False;app._run_legend=True;app._run_key_override=''
  png=Path(app._convert_page(0,''));labels=Path(app.labels_path)
  result=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),png=str(png),json=str(labels),png_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),json_sha256=hashlib.sha256(labels.read_bytes()).hexdigest())
  (out/'case-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(result,flush=True)
 finally:
  widgets=[app]
  for w in widgets:widgets.extend(w.winfo_children())
  owners={name:w for w in widgets for name in (getattr(w,'_tclCommands',None)or[])}
  for timer in app.tk.splitlist(app.tk.call('after','info')):
   owner=owners.get(str(app.tk.call('after','info',timer)[0]).split()[0])
   owner.after_cancel(timer)if owner else app.tk.call('after','cancel',timer)
  app._audio_timer=None;app._close_app()
