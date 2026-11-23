"""피아노 88건반 좌표와 재생 오버레이 상태. 음높이는 label_audio에서만 계산한다."""
import math

BLACK={1,3,6,8,10}
NAMES=('C','C#','D','D#','E','F','F#','G','G#','A','A#','B')


def keyboard_keys(width, height):
    if not math.isfinite(width) or not math.isfinite(height) or width<=0 or height<=0:
        raise ValueError('건반 표시 크기를 확인해 주세요.')
    unit=width/52;white=0;keys=[]
    for midi in range(21,109):
        black=midi%12 in BLACK
        if black:
            rect=(unit*(white-.3),0,unit*(white+.3),height*.62)
        else:
            rect=(unit*white,0,unit*(white+1),height);white+=1
        keys.append(dict(midi=midi,black=black,rect=rect,name=NAMES[midi%12]+str(midi//12-1)))
    return keys


class PlaybackCursor:
    """재생 세대가 다른 알림은 현재 쪽의 강조를 바꾸지 못한다."""
    def __init__(self):
        self.token=0
        self.reset()

    def reset(self):
        self.token+=1;self.plan=[];self.group_index=None;self.notes=[];self.indices=[]
        return self.token

    def apply(self,token,kind,value=None):
        if token!=self.token:return False
        if kind=='plan':
            self.plan=value;self.group_index=None;self.notes=[];self.indices=[]
        elif kind=='start':
            if type(value) is not int or not 0<=value<len(self.plan):return False
            row=self.plan[value];self.group_index=value
            self.notes=list(row['notes']);self.indices=list(row['indices'])
        elif kind=='end':
            if value!=self.group_index:return False
            self.group_index=None;self.notes=[];self.indices=[]
        elif kind=='finished':
            self.reset()
        else:return False
        return True


from tkinter import Canvas


class PianoKeyboard(Canvas):
    def __init__(self,parent,*,on_key_click=None,**options):
        super().__init__(parent,height=60,highlightthickness=0,**options)
        self.selected=set();self.playing=set()
        self._on_key_click = on_key_click
        self.bind('<Configure>',self._draw)
        if on_key_click is not None:
            self.bind('<Button-1>',self._key_clicked)

    def hit_test(self, x, y):
        keys = keyboard_keys(max(1,self.winfo_width()), max(1,self.winfo_height()))
        # 위쪽에서 두 색이 같은 좌표를 덮으면 검은 건반이 앞에 있다.
        for key in sorted(keys, key=lambda row: row['black'], reverse=True):
            x0,y0,x1,y1 = key['rect']
            if x0 <= x < x1 and y0 <= y < y1:
                return key['midi']
        return None

    def _key_clicked(self, event):
        note = self.hit_test(event.x, event.y)
        if note is not None:
            self._on_key_click(note)

    def set_notes(self,selected=(),playing=()):
        self.selected=set(selected);self.playing=set(playing);self._draw()

    def _draw(self,event=None):
        self.delete('all')
        keys=keyboard_keys(max(1,self.winfo_width()),max(1,self.winfo_height()))
        for key in sorted(keys,key=lambda row:row['black']):
            note=key['midi']
            color=('#F59E0B' if note in self.playing else '#3B82F6' if note in self.selected
                   else '#252525' if key['black'] else '#ffffff')
            self.create_rectangle(*key['rect'],fill=color,outline='#555555',width=1,
                                  tags=('piano-key',f'midi-{note}'))
            if note%12==0:
                x0,_y0,x1,y1=key['rect']
                self.create_text((x0+x1)/2,y1-7,text=key['name'],fill='#555555',font=('맑은 고딕',7))
