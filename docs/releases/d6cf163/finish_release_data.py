"""검증된 실제 exe 산출물에서 기록·6쪽 변화표·부분그림을 만든다."""
import hashlib,json,shutil,sys
from pathlib import Path
from PIL import Image
root=Path.cwd();sys.path.insert(0,str(root));work=root/'output/release-d6cf163';out=root/'output/release-d6cf163-record';out.mkdir(parents=True,exist_ok=True)
tag='d6cf163eea02-20261007-160020-688938';build=root/'dist'/tag
info=json.loads((build/'build-info.json').read_text(encoding='utf-8'));assert not info['dirty'] and info['commit']=='d6cf163eea020a6afe2b57cc577b98ee9fd2f98a'
artifacts=dict(build_commit=info['commit'])
for name,path in [('exe',build/'악보헬퍼.exe'),('zip',root/'dist'/f'악보헬퍼-{tag}.zip')]:
 artifacts[name]=dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest().upper())
assert artifacts['exe']['sha256']==info['exe']['sha256']
(out/'artifacts.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ('aoharu_p1','chopin_Db_p1','bach_p1'):
 shutil.copy2(next((work/(name+'_exe')).glob('*_계이름.png')),out/(name+'.png'))
Image.open(next((work/'alto_beethoven1_exe').glob('*_계이름.png'))).crop((280,160,530,355)).save(out/'beethoven_header_detail.png')
verify=json.loads((work/'verification.json').read_text(encoding='utf-8'));target=verify['d3']['target'];x,y=target['x'],target['y']
Image.open(next((work/'d3_edited_exe').glob('*_계이름.png'))).crop((max(0,x-90),max(0,y-100),x+90,y+70)).save(out/'d3_edited_detail.png')
for name in ('build-info.json','먼저 읽어주세요.txt','FRIEND_MESSAGE.md','PAGE_REOPEN_HUMAN_CHECK.md'):
 src=build/name if name=='build-info.json' else root/name if name=='먼저 읽어주세요.txt' else root/'docs/releases/ab93bf2'/name
 shutil.copy2(src,out/name)
old=root/'output/release-ab93bf2';before=work/'comparison-before';after=work/'comparison-after';before.mkdir(exist_ok=True);after.mkdir(exist_ok=True)
for case,label in [('aoharu_p1','aoharu_p1'),('aoharu_p2','aoharu_p2'),('aoharu_p3','aoharu_p3'),('chopin_Db_p1','chopin_Db_p1'),('bach_p1','bach_p1'),('clara_p1','clef_change_clara1')]:
 for directory,source in [(before,old),(after,work)]:shutil.copy2(next((source/(label+'_exe')).glob('*_라벨.json')),directory/(case+'.json'))
from tools.compare_beta_labels import main
sys.argv=['compare_beta_labels.py',str(before),str(after),str(out),'--old-commit','ab93bf294cd868ba80439e27bfac5921ec7db46e','--new-commit',info['commit']];main()
print(json.dumps(artifacts,ensure_ascii=False,indent=2))
