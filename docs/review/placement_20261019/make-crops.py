import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path.cwd();local=root/'output/placement-20261019';out=root/'docs/review/placement_20261019';out.mkdir(exist_ok=True)
b={r['case']:r for r in json.loads((local/'baseline/results.json').read_text(encoding='utf-8'))};a={r['case']:r for r in json.loads((local/'ink-revision/candidate/results.json').read_text(encoding='utf-8'))}
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',19)
specs=[('01_irregular','chopin_Db_p1',(980,1290,1980,1660),'들쭉날쭉 / 반복 왼손 음형'),('02_chord','chopin_Db_p1',(500,2670,1190,2930),'화음 열 / 머리 x가 조금 다른 음들'),('03_dense','chopin_Db_p1',(1420,2650,2420,2950),'밀집 구간 / 긴 표기·점선·화음'),('04_ink_tradeoff','chopin_Db_p1',(300,2040,1140,2390),'기각안의 잉크 증가 구간 / 수정안은 증가 금지'),('05_aoharu_column','aoharu_p2',(470,1470,910,1640),'작은 보표 / 공통 열'),('06_control','aoharu_p3',(200,430,1150,560),'대조 / 이 쪽은 PNG 전체 동일'),('07_rejected_guard','schubert_bravura',(1150,1040,1810,1370),'초기 기각안 반례 / 현재 후보의 거리 보존')]
records=[]
for name,case,box,title in specs:
 before=Image.open(root/b[case]['png']).convert('RGB');after=Image.open(root/a[case]['png']).convert('RGB');w=box[2]-box[0];h=box[3]-box[1]
 canvas=Image.new('RGB',(max(700,w),2*h+110),'white');draw=ImageDraw.Draw(canvas)
 draw.text((10,7),title,fill='black',font=font);draw.text((10,36),'전 (같은 배율)',fill='#444444',font=font);canvas.paste(before.crop(box),(0,65));draw.text((10,h+70),'후 (라벨 원자료 동일)',fill='#444444',font=font);canvas.paste(after.crop(box),(0,h+105));canvas.save(out/(name+'.png'))
 records.append(dict(file=name+'.png',case=case,crop=list(box),scale=1))
(out/'crops.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# 원본 기호 교차 점검: 각 행 좌=전, 우=후.
spec=[('clara2_leipzig',402),('schubert_bravura',12),('clara1_leipzig',76),('chopin_Db_p1',123)]
canvas=Image.new('RGB',(1000,1000),'white');draw=ImageDraw.Draw(canvas)
for k,(case,i) in enumerate(spec):
    r=a[case]['labels'][i];x,y=r['x'],r['y'];box=(max(0,x-170),max(0,y-90),x+270,y+100)
    draw.text((5,k*250+3),f'{case} #{i} ({x},{y}) / 전 → 후',font=font,fill='black')
    for side,data in enumerate((b,a)):
        canvas.paste(Image.open(root/data[case]['png']).crop(box),(side*500,k*250+38))
canvas.save(out/'08_ink_audit.png')

# 같은 원본에서 운지 숫자/악센트를 2배 확대한다(위 원본, 가운데 기존, 아래 수정).
box=(550,2700,1205,2815);w=(box[2]-box[0])*2;h=(box[3]-box[1])*2
zoom=Image.new('RGB',(w,3*(h+48)),'white');draw=ImageDraw.Draw(zoom)
source=Image.open(root/'tests/fixtures/selftest/chopin_Db_p1.png').convert('RGB')
views=[('원본 / 운지·악센트',source),('전 / 기존 배치',Image.open(root/b['chopin_Db_p1']['png'])),('후 / 원본 기호 보호 우선',Image.open(root/a['chopin_Db_p1']['png']))]
for k,(title,im) in enumerate(views):
    draw.text((10,k*(h+48)+10),title,font=font,fill='black')
    zoom.paste(im.crop(box).resize((w,h)),(0,k*(h+48)+48))
zoom.save(out/'09_fingering_zoom.png')
records.append(dict(file='09_fingering_zoom.png',case='chopin_Db_p1',crop=list(box),scale=2,panels=['source','before','after']))
(out/'crops.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
