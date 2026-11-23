"""D-2 음높이만: 인식 라벨을 유지하며 대보표 안의 가까운 음을 동시에 재생한다."""
from array import array
from collections import deque
from functools import lru_cache
import math
from pathlib import Path
import re
import sys
import wave
from modules.note_namer import FIXED_DO_MAP

PC=dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)
LETTERS='CDEFGAB'
DEGREES=list(FIXED_DO_MAP.values())
MAJOR=(0,2,4,5,7,9,11)


def pitch_to_midi(label: dict, music: dict):
    if isinstance(label.get('key'),dict):music={**music,**label['key']}  # 조바꿈 구간 조표(§1-43)
    pitch=label.get('pitch','')
    if not isinstance(pitch,str) or not re.fullmatch('[A-G][0-9]',pitch):
        raise ValueError('음고(C4 등)를 읽지 못했습니다.')
    letter,octave=pitch[0],int(pitch[1])
    alteration=0
    acc=label.get('accidental')
    if acc in ('#','b','##','bb'):alteration=acc.count('#')-acc.count('b')
    elif acc=='natural':alteration=0
    elif not acc and letter in music.get('key_letters',[]):
        alteration=-1 if music.get('key_symbol') in ('b','♭') else 1
    elif acc:raise ValueError('지원하지 않는 임시표입니다.')
    if label.get('edited'):
        music = label.get('edit_music', music)
        text=str(label.get('text','')).strip().replace('♯','#').replace('♭','b')
        found=re.fullmatch('(도|레|미|파|솔|라|시|[A-G])([#b]*)',text)
        if not found:raise ValueError('사용자 표기의 음높이를 해석하지 못했습니다.')
        name,marks=found.groups()
        if name in PC:
            letter=name;alteration=marks.count('#')-marks.count('b')
        elif music.get('notation')=='solfege-movable':
            tonic=music.get('tonic')
            if not isinstance(tonic,str) or not re.fullmatch('[A-G][#b]*',tonic):
                raise ValueError('이동도 으뜸음이 없습니다.')
            degree=DEGREES.index(name)
            letter=LETTERS[(LETTERS.index(tonic[0])+degree)%7]
            target=PC[tonic[0]]+tonic[1:].count('#')-tonic[1:].count('b')+MAJOR[degree]
            alteration=(target-PC[letter]+6)%12-6+marks.count('#')-marks.count('b')
        else:
            letter=next(k for k,v in FIXED_DO_MAP.items() if v==name)
            alteration=marks.count('#')-marks.count('b')
    midi=12*(octave+1)+PC[letter]+alteration
    if not 0<=midi<=127:raise ValueError('재생 가능한 음높이 범위를 벗어납니다.')
    return midi


def audio_plan(doc: dict, skip_check: bool):
    """재생할 음과 시작 시점 문서의 라벨 번호를 같은 계산에서 보존한다."""
    tolerances = {}
    for i, staff in enumerate(doc.get('staves') or ()):
        if not isinstance(staff, dict):
            continue
        number, spacing = staff.get('id', i), staff.get('spacing')
        if (type(number) is int and number >= 0 and type(spacing) in (int, float)
                and math.isfinite(spacing) and spacing > 0):
            system = number // 2
            limit = spacing * .5
            tolerances[system] = min(tolerances.get(system, limit), limit)
    positions, skipped = [], []
    for index, label in enumerate(doc['labels']):
        if skip_check and label.get('confidence') == 'check' and not label.get('edited'):
            skipped.append(dict(label=label, reason='확인 필요 제외'))
            continue
        try:
            staff, x = label['staff'], label['x']
            if type(staff) is not int or staff < 0 or type(x) not in (float, int) or not math.isfinite(x):
                raise ValueError('보표/가로 좌표를 읽지 못했습니다.')
            note = pitch_to_midi(label, doc.get('music', {}))
            positions.append((staff // 2, x, index, note))
        except (ValueError, KeyError, TypeError) as exc:
            skipped.append(dict(label=label, reason=str(exc)))

    groups = []
    last_system = None
    for system, x, index, note in sorted(positions):
        if system != last_system or x - anchor > tolerances.get(system, 0):
            notes, indices = set(), []
            groups.append((notes, indices))
            last_system, anchor = system, x
        notes.add(note)
        indices.append(index)
    return [dict(notes=sorted(notes), indices=sorted(indices)) for notes, indices in groups], skipped


def _group_durations(count, duration, durations):
    values=[duration]*count if durations is None else durations
    if not isinstance(values,(list,tuple)) or len(values)!=count:
        raise ValueError('음 묶음 수와 재생 길이 수가 다릅니다.')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in values):
        raise ValueError('재생 길이는 유한한 양수여야 합니다.')
    return list(values)


def practice_plan(plan: list, *, speed=1.0, start=None, end=None, durations=None):
    """음높이/라벨 번호를 유지하고 구간과 시간 축만 선택한다."""
    if type(speed) not in (int,float) or not math.isfinite(speed) or not .5<=speed<=1.5:
        raise ValueError('빠르기는 0.5~1.5배로 골라 주세요.')
    times=_group_durations(len(plan),.28,durations)
    first,last=0,len(plan)
    if start is not None or end is not None:
        if any(type(v) is not int or v<0 for v in (start,end)):
            raise ValueError('시작 음과 끝 음을 모두 골라 주세요.')
        found=[]
        for boundary in (start,end):
            matches=[i for i,row in enumerate(plan) if boundary in row['indices']]
            if len(matches)!=1:
                raise ValueError('경계 음이 듣기에서 제외됐거나 유효하지 않습니다. 확인 필요 제외와 선택 영역을 확인해 주세요.')
            found.append(matches[0])
        first,last=found
        if first>last:raise ValueError('끝 음은 시작 음보다 앞에 있을 수 없습니다.')
        last+=1
    return plan[first:last],[v/speed for v in times[first:last]]


def audio_groups(doc: dict, skip_check: bool):
    plan,skipped=audio_plan(doc,skip_check)
    return [row['notes'] for row in plan],skipped


def write_wav(groups: list, path: Path, duration=.28):
    """모든 묶음은 같은 길이. 박자/음표 길이 인식이나 MIDI 내보내기는 하지 않는다."""
    rate=44100
    if not math.isfinite(duration) or duration<=0:raise ValueError('재생 길이를 확인해 주세요.')
    frames=round(rate*duration)
    if frames<1:raise ValueError('재생 길이가 너무 짧습니다.')
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
        for group in groups:
            if not group or any(type(n) is not int or not 0<=n<=127 for n in group):
                raise ValueError('재생할 음높이 목록을 확인해 주세요.')
            frequencies=[440*2**((n-69)/12) for n in group]
            samples=array('h',(round(12000*min(1,i/441,(frames-1-i)/441)*
                sum(math.sin(2*math.pi*f*i/rate) for f in frequencies)/len(group))
                for i in range(frames)))
            if sys.byteorder!='little':samples.byteswap()
            out.writeframes(samples.tobytes())
    return frames*len(groups)/rate



_PIANO_RATE = 44100
_PIANO_BLOCK = 882
_PIANO_TAIL = round(.45 * _PIANO_RATE)
_VOICE_TAIL = round(.30 * _PIANO_RATE)
_ROOM_TAPS = tuple((round(t * _PIANO_RATE), gain) for t, gain in (
    (.013, .070), (.023, .056), (.032, -.044), (.046, .039), (.059, .028),
    (.075, -.022), (.092, .017), (.113, .013), (.137, -.010)))
_ROOM_FRAMES = _ROOM_TAPS[-1][0]


def _validate_groups(groups):
    if any(not group or any(type(n) is not int or not 0 <= n <= 127 for n in group) for group in groups):
        raise ValueError('재생할 음높이 목록을 확인해 주세요.')


def _piano_spans(groups, times):
    # 합성기는 시작/끝 프레임을 받는다. 현재 듣기는 각 묶음을 쉬는 구간 없이 잇는다.
    start = 0
    spans = []
    for notes, seconds in zip(groups, times):
        end = start + max(1, round(seconds * _PIANO_RATE))
        spans.append((start, end, notes))
        start = end
    return spans


def _repeated_spans(spans, repeat):
    offset = 0
    while True:
        for index, (start, end, notes) in enumerate(spans):
            yield index, start + offset, end + offset, notes
        if not repeat:
            return
        offset += spans[-1][1]


@lru_cache(maxsize=128)
def _piano_voice(note):
    import numpy as np

    # 실측 피아노의 부분음 신장·음역별 감쇠를 따른다. Fletcher 외 (1962), doi:10.1121/1.1918192.
    pitch = 440 * 2 ** ((note - 69) / 12)
    register = float(np.clip((note - 21) / 87, 0, 1))
    stiffness = np.interp(note, (21, 43, 67, 91, 108), (.00018, .00015, .00016, .00020, .0011))
    n = np.arange(1, 29, dtype=np.float64)
    freq = pitch * n * np.sqrt((1 + stiffness * n * n) / (1 + stiffness))
    audible = freq < .45 * _PIANO_RATE
    n, freq = n[audible], freq[audible]
    strike = .13 - .043 * register
    weights = np.abs(np.sin(np.pi * strike * n)) / n ** (.75 + .75 * register)
    weights *= np.exp(-(freq - pitch) / (1150 + 360 * register))
    weights /= np.linalg.norm(weights)
    damping = (.48 + 3.5 * register ** 2) * (1 + .30 * (n - 1))
    rng = np.random.default_rng(note)
    phase = rng.uniform(-.8, .8, len(n))
    hammer = np.convolve(rng.normal(0, 1, 700), [.11, .26, .24, 0, -.24, -.26, -.11], 'same')
    hammer *= .06 * np.exp(-np.arange(700) / 155)
    pan = .50 + .32 * (2 * register - 1)
    stereo = np.sqrt([1 - pan, pan])
    return (2 * np.pi * freq[:, None], weights[:, None], damping[:, None],
            phase[:, None], hammer, stereo, register)


def _piano_pcm(spans, repeat=False):
    import numpy as np

    if not spans:
        return
    score = _repeated_spans(spans, repeat)
    nxt = next(score)
    active = []
    history = np.zeros((_ROOM_FRAMES, 2))
    stop = spans[-1][1] + _PIANO_TAIL
    cursor = 0
    while repeat or cursor < stop:
        end = cursor + _PIANO_BLOCK if repeat else min(stop, cursor + _PIANO_BLOCK)
        while nxt is not None and nxt[1] < end:
            active.append(nxt[1:])
            nxt = next(score, None)
        active = [voice for voice in active if cursor < voice[1] + _VOICE_TAIL]
        dry = np.zeros((end - cursor, 2))
        for onset, off, notes in active:
            first, last = max(cursor, onset), min(end, off + _VOICE_TAIL)
            age = np.arange(first - onset, last - onset)
            t = age / _PIANO_RATE
            released = np.maximum(0, (age + onset - off) / _PIANO_RATE)
            gain = .34 / len(notes) ** .4
            for note in notes:
                omega, weights, damping, phase, hammer, stereo, register = _piano_voice(note)
                angle = omega * t + phase
                string = np.sin(angle)
                if note >= 43:
                    # 두 현이 미세하게 어긋나면서 중·고음의 여운을 만든다.
                    string = .73 * string + .27 * np.sin(angle + omega * t * .00068)
                decay = .70 * np.exp(-damping * t) + .30 * np.exp(-.34 * damping * t)
                tone = np.sum(string * decay * weights, axis=0)
                strike_frames = max(0, min(len(hammer) - age[0], len(age)))
                tone[:strike_frames] += hammer[age[:strike_frames]]
                tone *= -np.expm1(-t / .0025)
                tone *= np.exp(-released / (.080 - .033 * register)) * np.minimum(1, (.30 - released) / .035)
                dry[first - cursor:last - cursor] += gain * tone[:, None] * stereo
        history = np.concatenate((history, dry))
        room = dry.copy()
        for i, (delay, gain) in enumerate(_ROOM_TAPS):
            reflected = history[_ROOM_FRAMES - delay:_ROOM_FRAMES - delay + len(dry)]
            room += gain * (reflected if i % 2 else reflected[:, ::-1])
        history = history[-_ROOM_FRAMES:]
        # 극단적으로 음이 많은 화음도 왜곡성 클리핑 없이 합산한다.
        yield np.rint(32766 * np.tanh(room)).astype('<i2').tobytes()
        cursor = end


def write_piano_wav(groups, path, duration=.28, *, durations=None):
    """실제 듣기와 같은 합성기로 스테레오 미리듣기 파일을 쓴다."""
    times = _group_durations(len(groups), duration, durations)
    _validate_groups(groups)
    spans = _piano_spans(groups, times)
    frames = 0
    with wave.open(str(path), 'wb') as out:
        out.setparams((2, 2, _PIANO_RATE, 0, 'NONE', 'not compressed'))
        for block in _piano_pcm(spans):
            out.writeframesraw(block)
            frames += len(block) // 4
    return frames / _PIANO_RATE


class _WaveError(OSError):
    pass


# 드라이버가 반환하지 못한 버퍼는 프로세스 종료 전까지 보존한다.
_wave_unreturned = []


def _play_wave(ct, dll, spans, repeat, cancel, emit):
    class Format(ct.Structure):
        _pack_ = 1
        _fields_ = [('tag', ct.c_uint16), ('channels', ct.c_uint16), ('rate', ct.c_uint32),
                    ('byte_rate', ct.c_uint32), ('align', ct.c_uint16), ('bits', ct.c_uint16),
                    ('extra', ct.c_uint16)]

    class Header(ct.Structure):
        _fields_ = [('data', ct.c_void_p), ('length', ct.c_uint32), ('recorded', ct.c_uint32),
                    ('user', ct.c_size_t), ('flags', ct.c_uint32), ('loops', ct.c_uint32),
                    ('next', ct.c_void_p), ('reserved', ct.c_size_t)]

    class Position(ct.Structure):
        _fields_ = [('kind', ct.c_uint32), ('value', ct.c_uint32), ('padding', ct.c_uint32)]

    handle_type = ct.c_void_p
    header_args = [handle_type, ct.POINTER(Header), ct.c_uint]
    signatures = {
        'waveOutOpen': [ct.POINTER(handle_type), ct.c_uint, ct.POINTER(Format),
                        ct.c_size_t, ct.c_size_t, ct.c_uint32],
        'waveOutPrepareHeader': header_args,
        'waveOutUnprepareHeader': header_args,
        'waveOutWrite': header_args,
        'waveOutGetPosition': [handle_type, ct.POINTER(Position), ct.c_uint],
        'waveOutReset': [handle_type],
        'waveOutClose': [handle_type],
    }
    try:
        for name, args in signatures.items():
            fn = getattr(dll, name)
            fn.argtypes, fn.restype = args, ct.c_uint
    except AttributeError as exc:
        raise _WaveError('Windows PCM 출력 장치를 사용할 수 없습니다.') from exc

    def check(code):
        if code:
            raise _WaveError(f'피아노 PCM 재생 실패 (WinMM {code}).')

    handle = handle_type()
    fmt = Format(1, 2, _PIANO_RATE, _PIANO_RATE * 4, 4, 16, 0)
    check(dll.waveOutOpen(ct.byref(handle), 0xffffffff, ct.byref(fmt), 0, 0, 0))
    prepared = []
    free, queued = deque(), deque()
    try:
        size = ct.sizeof(Header)
        for _ in range(3):
            buffer = ct.create_string_buffer(4 * _PIANO_BLOCK)
            header = Header(ct.addressof(buffer), len(buffer))
            check(dll.waveOutPrepareHeader(handle, ct.byref(header), size))
            prepared.append((buffer, header))
            free.append((buffer, header))
        blocks = _piano_pcm(spans, repeat)
        events = ((frame, tag, i) for i, start, end, _notes in _repeated_spans(spans, repeat)
                  for frame, tag in ((start, 'start'), (end, 'end')))
        event = next(events, None)
        complete = submitted = 0
        exhausted = False
        while not cancel.is_set():
            while free and not exhausted and not cancel.is_set():
                block = next(blocks, None)
                if block is None:
                    exhausted = True
                    break
                buffer, header = free.popleft()
                ct.memmove(buffer, block, len(block))
                header.length = len(block)
                check(dll.waveOutWrite(handle, ct.byref(header), size))
                submitted += len(block) // 4
                queued.append((buffer, header, submitted))
            if cancel.is_set():
                break
            pos = Position(2)
            check(dll.waveOutGetPosition(handle, ct.byref(pos), ct.sizeof(pos)))
            while queued and queued[0][1].flags & 1:
                buffer, header, complete = queued.popleft()
                free.append((buffer, header))
            reported = {1: pos.value * _PIANO_RATE // 1000, 2: pos.value, 4: pos.value // 4}.get(pos.kind, 0)
            played = min(submitted, max(reported, complete))
            # 장치의 첫 버퍼 준비 시간은 음이 실제로 흐르는 시간에 포함하지 않는다.
            while played and event is not None and event[0] <= played and not cancel.is_set():
                emit(event[1], event[2])
                event = next(events, None)
            if exhausted and not queued:
                break
            if (exhausted or not free) and cancel.wait(.004):
                break
    finally:
        failed = sys.exc_info()[0] is not None
        reset = dll.waveOutReset(handle)
        not_returned = [(buffer, header) for buffer, header in prepared
                        if dll.waveOutUnprepareHeader(handle, ct.byref(header), ct.sizeof(header))]
        closed = dll.waveOutClose(handle)
        if not_returned and closed:
            _wave_unreturned.extend(not_returned)
        if not failed and (reset or not_returned or closed):
            raise _WaveError(f'피아노 PCM 장치 정리 실패 (WinMM {reset}/{closed}).')


def play_piano(groups: list, cancel, duration=.28, on_group=None, *, durations=None, repeat=False):
    """피아노 합성음을 재생하며 PCM 장치 오류에는 Windows GM으로 이어서 듣는다."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('재생 길이를 확인해 주세요.')
    times = _group_durations(len(groups), duration, durations)
    if type(repeat) is not bool:
        raise ValueError('반복 여부를 확인해 주세요.')
    _validate_groups(groups)
    if not groups or cancel.is_set():
        return
    import ctypes as ct
    if not hasattr(ct, 'WinDLL'):
        raise OSError('피아노 듣기는 Windows에서 지원합니다.')
    dll = ct.WinDLL('winmm')
    active = None
    following = 0

    def event(tag, index):
        nonlocal active, following
        active = index if tag == 'start' else None
        if tag == 'start':
            following = index + 1
        if on_group is not None:
            on_group(tag, index)

    failure = None
    try:
        _play_wave(ct, dll, _piano_spans(groups, times), repeat, cancel, event)
    except _WaveError as error:
        failure = error
    if active is not None:
        event('end', active)
    if failure is not None and not cancel.is_set():
        if repeat or following < len(groups):
            _play_gm(ct, dll, groups, times, cancel, on_group, repeat, following % len(groups))
        else:
            raise failure


def _play_gm(ct, midi, groups, times, cancel, on_group, repeat, first):
    class Caps(ct.Structure):
        _fields_=[('mid',ct.c_ushort),('pid',ct.c_ushort),('version',ct.c_ulong),
                  ('name',ct.c_wchar*32),('technology',ct.c_ushort),
                  ('voices',ct.c_ushort),('notes',ct.c_ushort),
                  ('channels',ct.c_ushort),('support',ct.c_ulong)]
    signatures={
        'midiOutGetNumDevs':[],
        'midiOutGetDevCapsW':[ct.c_size_t,ct.POINTER(Caps),ct.c_uint],
        'midiOutOpen':[ct.POINTER(ct.c_void_p),ct.c_uint,ct.c_size_t,ct.c_size_t,ct.c_ulong],
        'midiOutShortMsg':[ct.c_void_p,ct.c_ulong],
        'midiOutReset':[ct.c_void_p], 'midiOutClose':[ct.c_void_p]}
    for name,args in signatures.items():
        function=getattr(midi,name);function.argtypes=args;function.restype=ct.c_uint
    device=None
    for index in range(midi.midiOutGetNumDevs()):
        caps=Caps()
        if midi.midiOutGetDevCapsW(index,ct.byref(caps),ct.sizeof(caps))==0 and caps.name=='Microsoft GS Wavetable Synth' and caps.technology==7:
            device=index;break
    if device is None:
        raise OSError('Windows 기본 피아노 음원을 찾지 못했습니다. 오디오 장치를 확인해 주세요.')
    handle=ct.c_void_p()
    code=midi.midiOutOpen(ct.byref(handle),device,0,0,0)
    if code:raise OSError(f'피아노 장치를 열지 못했습니다 (WinMM {code}).')
    def send(message):
        code=midi.midiOutShortMsg(handle,message)
        if code:raise OSError(f'피아노 재생 실패 (WinMM {code}).')
    try:
        # GM bank 0, Acoustic Grand Piano(program 0), 페달 해제.
        send(0xb0);send(0xb0|32<<8);send(0xc0);send(0xb0|64<<8)
        while True:
            for index in range(first, len(groups)):
                group = groups[index]
                if cancel.is_set():return
                for note in group:send(0x90|note<<8|80<<16)
                if on_group is not None:on_group('start',index)
                stopped=cancel.wait(times[index])
                for note in group:send(0x80|note<<8)
                if on_group is not None:on_group('end',index)
                if stopped:return
            first = 0
            if not repeat:
                # 마지막 note-off 뒤 여운을 남기고 중지 이벤트가 오면 즉시 정리한다.
                if not cancel.is_set():
                    cancel.wait(.45)
                return
    finally:
        failed=sys.exc_info()[0] is not None
        try:
            reset=midi.midiOutReset(handle)
        finally:
            closed=midi.midiOutClose(handle)
        if not failed and (reset or closed):
            raise OSError(f'피아노 장치 정리 실패 (WinMM {reset}/{closed}).')
