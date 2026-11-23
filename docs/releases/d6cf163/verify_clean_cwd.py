import os, json, subprocess, hashlib
from pathlib import Path
from PIL import Image, ImageChops
root=Path.cwd(); work=root/'output/release-d6cf163'; clean=work/'새 폴더 첫 실행'; exe=clean/'악보헬퍼.exe'
env=dict(os.environ, PATH=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot'], PYTHONPATH='', PYTHONIOENCODING='utf-8')
cases=[('aoharu_p1',root/'sample_images/KakaoTalk_20260731_162400402.png'),('chopin_Db_p1',root/'tests/fixtures/selftest/chopin_Db_p1.png'),('alto_beethoven1',root/'test_scores/verovio/beethoven_op18no1_bravura_p1.png')]
rows=[]
for name,input_file in cases:
    target=work/(name+'_clean_cwd')
    r=subprocess.run([str(exe),'--selftest',str(input_file),str(target)],cwd=clean,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (work/(name+'_clean_cwd.log')).write_bytes(r.stdout)
    assert r.returncode==0,(name,r.returncode)
    expected=work/(name+'_source')
    assert json.loads(next(target.glob('*_라벨.json')).read_text(encoding='utf-8'))==json.loads(next(expected.glob('*_라벨.json')).read_text(encoding='utf-8'))
    assert ImageChops.difference(Image.open(next(target.glob('*_계이름.png'))).convert('RGB'),Image.open(next(expected.glob('*_계이름.png'))).convert('RGB')).getbbox() is None
    rows.append(dict(case=name,clean_cwd=True,pythonpath_empty=True,json_equal=True,pixels_equal=True))
    print(name,'clean cwd JSON/PNG pass',flush=True)
(work/'clean-cwd.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
