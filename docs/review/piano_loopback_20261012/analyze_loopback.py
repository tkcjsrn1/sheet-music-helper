import json,hashlib,wave,sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks
control='--beep-control' in sys.argv
out=Path('output/beep-loopback-control-20261012' if control else 'output/piano-loopback-20261012');rate,data=wavfile.read(out/'piano_actual_output.wav')
x=data.mean(axis=1).astype(float)
# 녹음된 첫 C4의 20ms~220ms 구간: 단일 사인파와 여러 배음을 따로 기록한다.
energy=np.sqrt(np.mean(x[:len(x)//480*480].reshape(-1,480)**2,axis=1))
onset=int(np.flatnonzero(energy>energy.max()*.08)[0])*480
seg=x[onset+round(.02*rate):onset+round(.22*rate)];t=np.arange(len(seg))/rate
best=None
for f in np.linspace(259.5,263.5,81):
    A=np.array([np.sin(2*np.pi*f*t),np.cos(2*np.pi*f*t),np.ones(len(t))]).T
    pred=A@np.linalg.lstsq(A,seg,rcond=None)[0];fraction=1-np.sum((seg-pred)**2)/np.sum((seg-seg.mean())**2)
    if best is None or fraction>best[1]:best=(f,float(fraction))
freq=np.fft.rfftfreq(len(seg),1/rate);amp=np.abs(np.fft.rfft(seg*np.hanning(len(seg))))
peaks,_=find_peaks(amp);peaks=sorted((i for i in peaks if 100<freq[i]<5000),key=lambda i:amp[i],reverse=True)[:12]
r=dict(wav_sha256=hashlib.sha256((out/'piano_actual_output.wav').read_bytes()).hexdigest(),rate=rate,channels=data.shape[1],captured_seconds=len(data)/rate,onset_seconds=onset/rate,first_note_truth='C4',expected_hz=440*2**((60-69)/12),best_single_sine_hz=best[0],single_sine_explained_energy=best[1],spectral_peaks=[dict(hz=float(freq[i]),relative=float(amp[i]/amp.max())) for i in peaks],microphone_used=False,interpretation=('기존 사인파 WAV의 실제 출력 대조.' if control else 'GM Acoustic Grand Piano의 실제 출력. 음질의 사람 청취 판정은 별도.'))
assert best[1]>.98 if control else best[1]<.95
assert sum(p['relative']>.05 for p in r['spectral_peaks'])==1 if control else sum(p['relative']>.05 for p in r['spectral_peaks'])>=3
(out/'analysis.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# 브라우저에서 듣기 쉬운 PCM16. 볼륨 증폭/효과/음색 변경 없이 형식만 변환.
with wave.open(str(out/'piano_listen.wav'),'wb') as wav:
    wav.setnchannels(data.shape[1]);wav.setsampwidth(2);wav.setframerate(rate)
    wav.writeframes(np.rint(np.clip(data,-1,1)*32767).astype('<i2').tobytes())
print(json.dumps(r,ensure_ascii=False,indent=2))
