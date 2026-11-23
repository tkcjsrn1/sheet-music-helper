import hashlib,json,shutil,sys
from pathlib import Path
from PIL import Image
root=Path.cwd();sys.path.insert(0,str(root));work=root/'output/release-1ad8323';out=root/'output/release-1ad8323-record';out.mkdir(parents=True,exist_ok=True)
tag='1ad8323c6155-20261012-211342-994454';build=root/'dist'/tag
info=json.loads((build/'build-info.json').read_text(encoding='utf-8'));assert not info['dirty'] and info['commit']=='1ad8323c6155b8ce5f277df1fc9034f38cb86c2c'
assert info['tests']['failed']==info['tests']['skipped']==0
artifacts=dict(build_commit=info['commit'])
for name,path in [('exe',build/'악보헬퍼.exe'),('zip',root/'dist'/f'악보헬퍼-{tag}.zip')]:
 with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest().upper()
 artifacts[name]=dict(path=str(path),bytes=path.stat().st_size,sha256=digest)
assert artifacts['exe']['sha256']==info['exe']['sha256']
(out/'artifacts.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
verification=json.loads((work/'verification.json').read_text(encoding='utf-8'));assert len(verification['cases'])==8 and verification['d3']['edited_check_draws_as_certain']
for name in ('aoharu_p1','chopin_Db_p1','bach_p1'):shutil.copy2(next((work/(name+'_exe')).glob('*_계이름.png')),out/(name+'.png'))
Image.open(next((work/'alto_beethoven1_exe').glob('*_계이름.png'))).crop((280,160,530,355)).save(out/'beethoven_header_detail.png')
target=verification['d3']['target'];x,y=target['x'],target['y']
Image.open(next((work/'d3_edited_exe').glob('*_계이름.png'))).crop((max(0,x-90),max(0,y-100),x+90,y+70)).save(out/'d3_edited_detail.png')
shutil.copy2(build/'build-info.json',out/'build-info.json')
shutil.copy2(work/'새 폴더 첫 실행'/'먼저 읽어주세요.txt',out/'먼저 읽어주세요.txt')
assert (out/'먼저 읽어주세요.txt').read_bytes()==(root/'먼저 읽어주세요.txt').read_bytes()
for name in ('verification.json','clean-cwd.json'):shutil.copy2(work/name,out/name)
shutil.copy2(root/'output/release-1ad8323-verification.log',out/'verification.log')
shutil.copy2(root/'docs/measurements/beta_20261012_prep_run_all.log',out/'prebuild-tests.log')
for name in ('build.log','tests.log'):shutil.copy2(root/'debug/build-pipeline'/tag/name,out/name)
for kind in ('exe','zip'):
 for suffix in ('.json','-status.json','.log'):shutil.copy2(root/'output/1ad8323-defender'/(kind+suffix),out/('defender-'+kind+suffix))
 scan=json.loads((out/('defender-'+kind+'.json')).read_text(encoding='utf-8-sig'));assert scan['exit_code']==0 and not scan['target_detections']
old=root/'output/release-d6cf163';before=work/'comparison-before';after=work/'comparison-after';before.mkdir(exist_ok=True);after.mkdir(exist_ok=True)
for case,label in [('aoharu_p1','aoharu_p1'),('aoharu_p2','aoharu_p2'),('aoharu_p3','aoharu_p3'),('chopin_Db_p1','chopin_Db_p1'),('bach_p1','bach_p1'),('clara_p1','clef_change_clara1')]:
 for directory,source in [(before,old),(after,work)]:shutil.copy2(next((source/(label+'_exe')).glob('*_라벨.json')),directory/(case+'.json'))
from tools.compare_beta_labels import main
sys.argv=['compare_beta_labels.py',str(before),str(after),str(out),'--old-commit','d6cf163eea020a6afe2b57cc577b98ee9fd2f98a','--new-commit',info['commit']];main()
actions=json.loads((out/'actions.json').read_text(encoding='utf-8-sig'));assert actions['headSha']==info['commit'] and actions['conclusion']=='success'
changes=json.loads((out/'BETA_CHANGES.json').read_text(encoding='utf-8'))
print(json.dumps(artifacts,ensure_ascii=False,indent=2))
print([(c['case'],c['counts']) for c in changes['cases']])
friend=(root/'docs/releases/d6cf163/FRIEND_MESSAGE.md').read_text(encoding='utf-8');(out/'FRIEND_MESSAGE.md').write_text('# 메시지 초안 — 친구 배포 보류\n\n'+friend,encoding='utf-8')

