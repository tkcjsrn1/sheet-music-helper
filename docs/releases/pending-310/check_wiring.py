"""실제 main/GUI 호출 표현식의 인자 순서와 photo 활성/비활성을 대조한다."""
import ast,json,sys
from pathlib import Path
from types import SimpleNamespace
root=Path.cwd();sys.path.insert(0,str(root))
expected=[object() for _ in range(12)]
names=['result','contexts','clef_arg','key_letters','key_symbol','notation','tonic','pitched','accidentals','named','diag_rows','rare_warnings']
rows=[]
for filename in ('main.py','gui.py'):
    tree=ast.parse((root/filename).read_text(encoding='utf-8'))
    calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='apply_chord_middles']
    assert len(calls)==1,(filename,len(calls))
    for photo in (False,True):
        captured=[]
        def spy(*args,**kwargs):captured.append((args,kwargs))
        env=dict(zip(names,expected));env.update(pitched_notes=expected[7],notes_with_solfege=expected[9],args=SimpleNamespace(notation=expected[5],photo=photo),photo=photo,apply_chord_middles=spy)
        eval(compile(ast.Expression(calls[0]),filename,'eval'),env)
        args,kwargs=captured[0]
        assert list(args)==expected,(filename,'인자 순서/의미')
        assert kwargs=={'enable':not photo},(filename,'사진 모드 비활성')
        rows.append(dict(file=filename,line=calls[0].lineno,photo=photo,enable=kwargs['enable'],positional_names=names))
from modules.chord_rescue import apply_chord_middles
notes,acc,named,diag,warnings=[],[],[],[],[]
result=apply_chord_middles(None,None,None,(),'','solfege','',notes,acc,named,diag,warnings,enable=False)
assert all(a is b for a,b in zip(result[:4],(notes,acc,named,diag))) and result[4]==0 and warnings==[]
Path('output/beta310-wiring.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('main/GUI 실제 호출 인자12개 동일 · photo OFF 활성/ON 비활성 · 실제 disabled 반환 불변',flush=True)
