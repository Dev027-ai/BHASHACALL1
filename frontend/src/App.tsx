import { useEffect, useRef, useState } from 'react';
import {
  AudioLines,
  ArrowLeftRight,
  Check,
  Copy,
  FileText,
  FolderOpen,
  Languages,
  Mic,
  MessageSquare,
  Phone,
  Radio,
  ShieldCheck,
  Upload,
  Volume2,
  X,
  Home,
  Share2,
  Download,
  Play,
  Pause,
  RefreshCw,
  Sparkles
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS = API.replace(/^http/, 'ws');
const USER_ID =
  localStorage.getItem('bhashacall_user_id') ||
  (() => {
    const id = crypto.randomUUID();
    localStorage.setItem('bhashacall_user_id', id);
    return id;
  })();

type Tab = 'home' | 'rooms' | 'messages' | 'studio' | 'documents';
type Caption = {
  id: string;
  original: string;
  translated: string;
  from?: string;
  detected_language?: string;
  stt_model?: string;
  tts_model?: string;
  latency_ms?: number;
};
type Doc = {
  id: string;
  original_name: string;
  filename?: string;
  status: string;
  source_language?: string;
  target_language?: string;
  error?: string;
  created_at?: string;
};
type Chat = {
  id: string;
  client_message_id?: string;
  sender_id: string;
  original_text: string;
  translated_text: string;
  mine?: boolean;
  created_at?: string;
  pending?: boolean;
  translation_error?: string;
};

const LANGUAGES = [
  { code: 'hi', label: 'Hindi', locale: 'hi-IN' },
  { code: 'en', label: 'English', locale: 'en-IN' },
  { code: 'bn', label: 'Bengali', locale: 'bn-IN' },
  { code: 'ta', label: 'Tamil', locale: 'ta-IN' },
  { code: 'te', label: 'Telugu', locale: 'te-IN' },
  { code: 'mr', label: 'Marathi', locale: 'mr-IN' },
] as const;

export default function App() {
  const [tab, setTab] = useState<Tab>('home');
  const [roomCode, setRoomCode] = useState('');
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState('Create a room or join with a code');
  const [sourceLanguage, setSourceLanguage] = useState('hi');
  const [targetLanguage, setTargetLanguage] = useState('en');
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);

  // Call & media state
  const [callActive, setCallActive] = useState(false);
  const [callPhase, setCallPhase] = useState<'idle' | 'outgoing' | 'incoming' | 'connecting' | 'connected'>('idle');
  const [incomingCall, setIncomingCall] = useState<{ from: string; call_id: string } | null>(null);
  const [, setActiveCallId] = useState('');
  const [remoteStreams, setRemoteStreams] = useState<Record<string, MediaStream>>({});
  const [callSeconds, setCallSeconds] = useState(0);
  const [callMuted, setCallMuted] = useState(false);
  const [captionLive, setCaptionLive] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [latestLatency, setLatestLatency] = useState<number | null>(null);

  // Captions & Chat
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [chat, setChat] = useState<Chat[]>([]);
  const [chatText, setChatText] = useState('');

  // Documents
  const [docs, setDocs] = useState<Doc[]>([]);
  const [sharedDocs, setSharedDocs] = useState<Doc[]>([]);
  const [standaloneText, setStandaloneText] = useState('');
  const [standaloneResult, setStandaloneResult] = useState<any>(null);
  const [standaloneBusy, setStandaloneBusy] = useState(false);
  const [activeDoc, setActiveDoc] = useState<any>(null);
  const [source, setSource] = useState('auto');
  const [target, setTarget] = useState('en');
  const [uploading, setUploading] = useState(false);
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState('');
  const [copyDone, setCopyDone] = useState(false);

  // Audio player state
  const [listenIndex, setListenIndex] = useState(0);
  const [audioBusy, setAudioBusy] = useState(false);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [audioPaused, setAudioPaused] = useState(false);
  const [audioProgress, setAudioProgress] = useState({ current: 0, total: 0 });
  const [shared, setShared] = useState(false);

  // Refs
  const audioSequenceRef = useRef(false);
  const audioIndexRef = useRef(0);
  const audioTotalRef = useRef(0);
  const docAudioRef = useRef<HTMLAudioElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const participantRef = useRef('');
  const recorderRef = useRef<MediaRecorder | null>(null);
  const localCallStreamRef = useRef<MediaStream | null>(null);
  const peersRef = useRef<Record<string, RTCPeerConnection>>({});
  const pendingIceRef = useRef<Record<string, RTCIceCandidateInit[]>>({});
  const remoteAudioRefs = useRef<Record<string, HTMLAudioElement | null>>({});
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  // Web Audio streaming refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const callMutedRef = useRef(false);
  callMutedRef.current = callMuted;

  useEffect(() => {
    loadDocs();
    return () => {
      stopAudioStreaming();
      wsRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      localCallStreamRef.current?.getTracks().forEach((t) => t.stop());
      Object.values(peersRef.current).forEach((p) => p.close());
    };
  }, []);

  useEffect(() => {
    Object.entries(remoteStreams).forEach(([id, stream]) => {
      const el = remoteAudioRefs.current[id];
      if (el && el.srcObject !== stream) {
        el.srcObject = stream;
        el.play().catch(() => {});
      }
    });
  }, [remoteStreams]);

  useEffect(() => {
    if (!callActive) return;
    const timer = window.setInterval(() => setCallSeconds((v) => v + 1), 1000);
    return () => window.clearInterval(timer);
  }, [callActive]);

  async function request(path: string, init?: RequestInit) {
    const res = await fetch(`${API}${path}`, init);
    if (!res.ok) {
      let m = 'Request failed';
      try {
        const j = await res.json();
        m = j.detail || m;
      } catch {}
      throw new Error(m);
    }
    return res;
  }

  async function loadDocs() {
    try {
      const r = await request(`/api/documents?owner_id=${encodeURIComponent(USER_ID)}`);
      setDocs((await r.json()).documents || []);
    } catch {}
  }

  const swapLanguages = () => {
    const newSrc = targetLanguage;
    const newTgt = sourceLanguage;
    setSourceLanguage(newSrc);
    setTargetLanguage(newTgt);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'set_languages',
          source_language: newSrc,
          target_language: newTgt,
        })
      );
    }
  };

  async function createRoom() {
    if (sourceLanguage === targetLanguage) {
      return setStatus('Choose two different languages first.');
    }
    try {
      setStatus('Creating room…');
      const r = await request('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_language: sourceLanguage,
          target_language: targetLanguage,
          participant_id: USER_ID,
        }),
      });
      const d = await r.json();
      setRoomCode(d.room_code);
      await connectRoom(d.room_code);
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  async function connectRoom(code = roomCode) {
    const normalized = code.trim().toUpperCase();
    if (!normalized) return setStatus('Enter a room code first.');
    try {
      await request(`/api/rooms/${normalized}`);
      wsRef.current?.close();
      const participantId = crypto.randomUUID();
      participantRef.current = participantId;
      const ws = new WebSocket(`${WS}/ws/${normalized}/${participantId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setRoomCode(normalized);
        setStatus('Connected — Gnani STT & TTS ready for voice call');
        setTab('rooms');
        loadRoomMessages(normalized);
      };

      ws.onclose = () => {
        setConnected(false);
        stopAudioStreaming();
      };

      ws.onerror = () => setStatus('Connection error. Check the backend server.');

      ws.onmessage = async (ev) => {
        const m = JSON.parse(ev.data);
        if (m.type === 'system') setStatus(m.text);

        if (m.type === 'caption.live' || m.type === 'caption') {
          const cap: Caption = {
            id: m.phrase_id || crypto.randomUUID(),
            original: m.original,
            translated: m.translated,
            from: m.from,
            detected_language: m.detected_language,
            stt_model: m.stt_model || 'prisma-v3.0',
            tts_model: m.tts_model || 'timbre-v2.5',
            latency_ms: m.timings?.trans_ms ? m.timings.trans_ms + (m.timings.stt_latency_ms || 100) : undefined,
          };
          setCaptions((p) => [...p, cap].slice(-150));
        }

        if (m.type === 'rtc.call-invite') {
          setIncomingCall({ from: m.from, call_id: m.call_id });
          setCallPhase('incoming');
          setStatus('Incoming room call — accept or decline.');
        }

        if (m.type === 'rtc.call-accepted' && localCallStreamRef.current) {
          setCallPhase('connecting');
          await negotiateWith(m.from);
        }

        if (m.type === 'rtc.call-rejected' && localCallStreamRef.current) {
          setCallPhase('idle');
          setCallActive(false);
          stopAudioStreaming();
          localCallStreamRef.current?.getTracks().forEach((t) => t.stop());
          localCallStreamRef.current = null;
          setStatus('The other participant declined the call.');
        }

        if (m.type === 'rtc.signal') {
          await handleSignal(m.from, m.payload);
        }

        if (m.type === 'rtc.peer-left' || m.type === 'rtc.call-ended') {
          if (m.type === 'rtc.call-ended') {
            setCallPhase('idle');
            setCallActive(false);
            setCallSeconds(0);
            setIncomingCall(null);
            stopAudioStreaming();
            localCallStreamRef.current?.getTracks().forEach((t) => t.stop());
            localCallStreamRef.current = null;
          }
          peersRef.current[m.from]?.close();
          delete peersRef.current[m.from];
          setRemoteStreams((p) => {
            const n = { ...p };
            delete n[m.from];
            return n;
          });
        }

        if (m.type === 'phrase_status') {
          setBusy(false);
          setStatus(m.text);
        }

        if (m.type === 'processing_error') {
          setBusy(false);
          setStatus(m.text);
        }

        if (m.type === 'speech.audio_ready' && m.audio_base64 && audioRef.current) {
          // Play translated speech from Gnani Timbre v2.5
          audioRef.current.src = `data:${m.mime_type || 'audio/wav'};base64,${m.audio_base64}`;
          audioRef.current.play().catch(() => setStatus('Translated audio ready. Click play below.'));
          if (m.timings?.total_ms) {
            setLatestLatency(m.timings.total_ms);
          }
        }

        if (m.type === 'speech.error') {
          setStatus(`Captions delivered; speech unavailable: ${m.text}`);
        }

        if (m.type === 'chat.message') {
          setChat((p) => {
            const mine = m.sender_id === participantRef.current;
            const incoming = { ...m, mine, pending: false };
            const idx = p.findIndex(
              (x) => x.id === m.id || (m.client_message_id && x.client_message_id === m.client_message_id)
            );
            if (idx >= 0) {
              const next = [...p];
              next[idx] = incoming;
              return next;
            }
            return [...p, incoming].slice(-200);
          });
        }

        if (m.type === 'chat.error') {
          setChat((p) =>
            p.map((x) =>
              x.client_message_id === m.client_message_id
                ? { ...x, pending: false, translation_error: m.text }
                : x
            )
          );
          setNotice(`Message could not be sent: ${m.text}`);
        }

        if (m.type === 'document.shared') {
          setNotice(`A document was shared in this room: ${m.filename}`);
          loadRoomMessages(normalized);
        }

        if (m.type === 'document.unshared') {
          setNotice('A document share was removed.');
        }
      };
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  function peerFor(peerId: string) {
    if (peersRef.current[peerId]) return peersRef.current[peerId];
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }, { urls: 'stun:stun1.l.google.com:19302' }],
    });
    peersRef.current[peerId] = pc;

    pc.onicecandidate = (e) => {
      if (e.candidate) {
        wsRef.current?.send(
          JSON.stringify({ type: 'rtc.signal', to: peerId, payload: { candidate: e.candidate } })
        );
      }
    };
    pc.ontrack = (e) => {
      const stream = e.streams[0] || new MediaStream([e.track]);
      setRemoteStreams((p) => ({ ...p, [peerId]: stream }));
      markCallConnected();
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'connected') {
        markCallConnected();
      }
      if (pc.connectionState === 'failed') {
        setCallPhase('idle');
        setCallActive(false);
        stopAudioStreaming();
        setStatus('Call connection failed. Check your network connection.');
      }
    };
    return pc;
  }

  async function negotiateWith(peerId: string) {
    const pc = peerFor(peerId);
    if (pc.signalingState === 'stable') {
      try {
        pc.createDataChannel('bhashacall-control');
      } catch {}
    }
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    wsRef.current?.send(
      JSON.stringify({ type: 'rtc.signal', to: peerId, payload: { description: pc.localDescription } })
    );
  }

  async function handleSignal(peerId: string, payload: any) {
    try {
      const pc = peerFor(peerId);
      if (payload?.description) {
        await pc.setRemoteDescription(new RTCSessionDescription(payload.description));
        const queued = pendingIceRef.current[peerId] || [];
        delete pendingIceRef.current[peerId];
        for (const candidate of queued) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(candidate));
          } catch {}
        }
        if (payload.description.type === 'offer') {
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          wsRef.current?.send(
            JSON.stringify({ type: 'rtc.signal', to: peerId, payload: { description: pc.localDescription } })
          );
        }
      } else if (payload?.candidate) {
        if (pc.remoteDescription?.type) {
          await pc.addIceCandidate(new RTCIceCandidate(payload.candidate));
        } else {
          (pendingIceRef.current[peerId] ??= []).push(payload.candidate);
        }
      }
    } catch (e) {
      setStatus(`Call setup issue: ${(e as Error).message}`);
    }
  }

  function markCallConnected() {
    setCallPhase('connected');
    setCallActive(true);
    setStatus('Call connected. Gnani Prisma v3.0 STT & Timbre v2.5 TTS active.');
    startAudioStreaming();
  }

  function startAudioStreaming() {
    if (!localCallStreamRef.current || wsRef.current?.readyState !== WebSocket.OPEN) return;
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtx({ sampleRate: 16000 });
      audioContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(localCallStreamRef.current);
      sourceNodeRef.current = source;

      // 512 samples @ 16kHz = 32ms frame = 1024 bytes signed 16-bit PCM (Gnani frame specification)
      const processor = ctx.createScriptProcessor(512, 1, 1);
      scriptProcessorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (callMutedRef.current || wsRef.current?.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);

        // Calculate simple RMS for VAD / speaking indicator
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);
        setIsSpeaking(rms > 0.012);

        // Convert Float32Array [-1.0, 1.0] to 16-bit PCM little-endian
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        // Convert to base64
        const bytes = new Uint8Array(pcm16.buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const b64 = window.btoa(binary);

        wsRef.current?.send(
          JSON.stringify({
            type: 'audio.stream_chunk',
            pcm_base64: b64,
            source_language: sourceLanguage,
            target_language: targetLanguage,
          })
        );
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      setCaptionLive(true);
    } catch (err) {
      console.warn('Web Audio streaming init error:', err);
    }
  }

  function stopAudioStreaming() {
    try {
      scriptProcessorRef.current?.disconnect();
      sourceNodeRef.current?.disconnect();
      audioContextRef.current?.close();
    } catch {}
    scriptProcessorRef.current = null;
    sourceNodeRef.current = null;
    audioContextRef.current = null;
    setCaptionLive(false);
    setIsSpeaking(false);
  }

  async function startLiveCall() {
    if (!connected) return setStatus('Create or join a room before starting a call.');
    if (!navigator.mediaDevices?.getUserMedia) return setStatus('Microphone calling requires HTTPS or localhost.');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
      localCallStreamRef.current = stream;
      setCallMuted(false);
      setCallActive(false);
      setCallSeconds(0);
      const callId = crypto.randomUUID();
      setActiveCallId(callId);
      setCallPhase('outgoing');
      wsRef.current?.send(JSON.stringify({ type: 'rtc.call-start', call_id: callId }));
      setStatus('Calling room participants… waiting for answer.');
    } catch (e) {
      setCallActive(false);
      setCallPhase('idle');
      setStatus(`Could not start microphone call: ${(e as Error).message}`);
    }
  }

  async function acceptCall() {
    if (!incomingCall) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
      localCallStreamRef.current = stream;
      setCallMuted(false);
      setCallActive(false);
      setCallSeconds(0);
      setActiveCallId(incomingCall.call_id);
      setCallPhase('connecting');
      wsRef.current?.send(
        JSON.stringify({
          type: 'rtc.call-accept',
          to: incomingCall.from,
          call_id: incomingCall.call_id,
        })
      );
      setIncomingCall(null);
      setStatus('Call accepted. Connecting…');
    } catch (e) {
      setStatus(`Microphone permission needed to answer: ${(e as Error).message}`);
    }
  }

  function declineCall() {
    if (!incomingCall) return;
    wsRef.current?.send(
      JSON.stringify({
        type: 'rtc.call-reject',
        to: incomingCall.from,
        call_id: incomingCall.call_id,
      })
    );
    setIncomingCall(null);
    setCallPhase('idle');
    setStatus('Incoming call declined.');
  }

  function toggleMute() {
    const next = !callMuted;
    localCallStreamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = !next;
    });
    setCallMuted(next);
  }

  function endLiveCall() {
    wsRef.current?.send(JSON.stringify({ type: 'rtc.call-end' }));
    stopAudioStreaming();
    localCallStreamRef.current?.getTracks().forEach((t) => t.stop());
    localCallStreamRef.current = null;
    Object.values(peersRef.current).forEach((pc) => pc.close());
    peersRef.current = {};
    pendingIceRef.current = {};
    setRemoteStreams({});
    setCallActive(false);
    setCallSeconds(0);
    setCallPhase('idle');
    setIncomingCall(null);
    setCallMuted(false);
    setStatus('Call ended. Room connection remains open.');
  }

  function formatCallTime(n: number) {
    return `${Math.floor(n / 60)
      .toString()
      .padStart(2, '0')}:${(n % 60).toString().padStart(2, '0')}`;
  }

  async function loadRoomMessages(code: string) {
    try {
      const r = await request(`/api/rooms/${code}/messages`);
      const history: Chat[] = (await r.json()).messages.map((m: Chat) => ({
        ...m,
        mine: m.sender_id === participantRef.current,
      }));
      setChat((current) => {
        const byId = new Map<string, Chat>();
        for (const item of history) byId.set(item.id, item);
        for (const item of current) {
          if (item.pending || !byId.has(item.id)) byId.set(item.id, item);
        }
        return [...byId.values()]
          .sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')))
          .slice(-200);
      });
    } catch (e) {
      setNotice(`Could not load room messages: ${(e as Error).message}`);
    }
    try {
      const r = await request(`/api/rooms/${code}/documents`);
      setSharedDocs((await r.json()).documents || []);
    } catch {}
  }

  async function startRecording() {
    if (!connected) return setStatus('Connect to a room first.');
    if (sourceLanguage === targetLanguage) return setStatus('Choose two different languages before recording.');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorderRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        if (!blob.size || wsRef.current?.readyState !== WebSocket.OPEN) return;
        setBusy(true);
        const reader = new FileReader();
        reader.onloadend = () => {
          const b64 = String(reader.result).split(',')[1] || '';
          wsRef.current?.send(
            JSON.stringify({
              type: 'phrase',
              phrase_id: crypto.randomUUID(),
              audio_base64: b64,
              mime_type: blob.type,
              source_language: sourceLanguage,
              target_language: targetLanguage,
            })
          );
          setStatus('Transcribing and translating with Gnani AI…');
        };
        reader.readAsDataURL(blob);
      };
      rec.start();
      setRecording(true);
      setStatus('Recording — speak into your microphone, then click Stop.');
    } catch {
      setStatus('Microphone permission denied or unavailable.');
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  function sendChat() {
    const text = chatText.trim();
    const ws = wsRef.current;
    if (!text) return;
    if (sourceLanguage === targetLanguage) {
      return setNotice('Choose two different languages before sending a translated message.');
    }
    if (!connected || !ws || ws.readyState !== WebSocket.OPEN) {
      return setNotice('You are not connected to the room. Rejoin the room before sending.');
    }
    const clientMessageId = crypto.randomUUID();
    const optimistic: Chat = {
      id: `pending-${clientMessageId}`,
      client_message_id: clientMessageId,
      sender_id: participantRef.current,
      original_text: text,
      translated_text: 'Sending…',
      mine: true,
      pending: true,
      created_at: new Date().toISOString(),
    };
    setChat((p) => [...p, optimistic].slice(-200));
    setChatText('');
    try {
      ws.send(
        JSON.stringify({
          type: 'chat.message',
          client_message_id: clientMessageId,
          text,
          source_language: sourceLanguage,
          target_language: targetLanguage,
        })
      );
    } catch (e) {
      setChat((p) =>
        p.map((x) =>
          x.client_message_id === clientMessageId
            ? { ...x, pending: false, translation_error: 'Network send failed. Please retry.' }
            : x
        )
      );
      setNotice(`Message send failed: ${(e as Error).message}`);
    }
  }

  async function uploadFile(file?: File) {
    if (!file) return;
    setUploading(true);
    setNotice('Uploading and extracting document text…');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('owner_id', USER_ID);
      const r = await request('/api/documents/upload', { method: 'POST', body: form });
      const d = await r.json();
      setNotice(
        `Uploaded ${d.filename}. Extracted ${Number(d.characters || 0).toLocaleString()} characters using ${
          d.extraction_method || 'text extraction'
        }.`
      );
      await openDoc(d.id);
      await loadDocs();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function openDoc(id: string, fromRoom = false) {
    try {
      const query = fromRoom
        ? `room_code=${encodeURIComponent(roomCode)}`
        : `owner_id=${encodeURIComponent(USER_ID)}`;
      const r = await request(`/api/documents/${id}?${query}`);
      setActiveDoc(await r.json());
      setTab('studio');
      setShared(fromRoom);
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  async function translateStandalone() {
    const text = standaloneText.trim();
    if (!text) return;
    if (sourceLanguage === targetLanguage) {
      return setNotice('Choose two different languages to translate.');
    }
    setStandaloneBusy(true);
    try {
      const r = await request('/api/messages/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          source_language: sourceLanguage,
          target_language: targetLanguage,
          sender_id: USER_ID,
        }),
      });
      setStandaloneResult(await r.json());
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setStandaloneBusy(false);
    }
  }

  async function translateDoc() {
    if (!activeDoc) return;
    setWorking(true);
    setNotice('Translating document in paragraphs…');
    try {
      const r = await request(`/api/documents/${activeDoc.id}/translate?owner_id=${encodeURIComponent(USER_ID)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_language: source, target_language: target }),
      });
      const d = await r.json();
      setActiveDoc((p: any) => ({ ...p, ...d, filename: p.filename || p.original_name }));
      setNotice('Translation complete. You can preview, listen with Gnani Timbre, or download.');
      await loadDocs();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setWorking(false);
    }
  }

  async function playDocChunk(index: number, continuous: boolean) {
    if (!activeDoc?.translated_text) return;
    setAudioBusy(true);
    try {
      const access = shared
        ? `room_code=${encodeURIComponent(roomCode)}`
        : `owner_id=${encodeURIComponent(USER_ID)}`;
      const r = await request(`/api/documents/${activeDoc.id}/audio?${access}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: '', language: target, chunk_index: index }),
      });
      const d = await r.json();
      audioSequenceRef.current = continuous;
      audioIndexRef.current = d.chunk_index;
      audioTotalRef.current = d.total_chunks;
      setAudioProgress({ current: d.chunk_index + 1, total: d.total_chunks });
      setListenIndex(d.chunk_index);
      if (docAudioRef.current) {
        docAudioRef.current.src = `data:${d.mime_type || 'audio/wav'};base64,${d.audio_base64}`;
        await docAudioRef.current.play();
        setAudioPlaying(true);
        setAudioPaused(false);
      }
      setNotice(`${continuous ? 'Listening to full document' : 'Playing section'} ${d.chunk_index + 1} of ${d.total_chunks}.`);
    } catch (e) {
      audioSequenceRef.current = false;
      setAudioPlaying(false);
      setNotice((e as Error).message);
    } finally {
      setAudioBusy(false);
    }
  }

  async function listenDoc() {
    await playDocChunk(listenIndex, false);
  }
  async function listenFullDoc() {
    await playDocChunk(0, true);
  }

  function pauseResumeDoc() {
    const audio = docAudioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio
        .play()
        .then(() => {
          setAudioPlaying(true);
          setAudioPaused(false);
        })
        .catch(() => setNotice('Could not resume audio. Press play again.'));
    } else {
      audio.pause();
      setAudioPlaying(false);
      setAudioPaused(true);
    }
  }

  async function handleDocAudioEnded() {
    if (audioSequenceRef.current && audioIndexRef.current + 1 < audioTotalRef.current) {
      await playDocChunk(audioIndexRef.current + 1, true);
    } else {
      audioSequenceRef.current = false;
      setAudioPlaying(false);
      setAudioPaused(false);
      setNotice('Document audio playback complete.');
    }
  }

  function handleDocumentAudioPause() {
    if (docAudioRef.current && !docAudioRef.current.ended) {
      setAudioPlaying(false);
      setAudioPaused(true);
    }
  }

  function handleDocumentAudioPlay() {
    setAudioPlaying(true);
    setAudioPaused(false);
  }

  async function shareDoc() {
    if (!activeDoc || !roomCode) return setNotice('Join a room first, then share this document.');
    try {
      await request(`/api/documents/${activeDoc.id}/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_code: roomCode,
          owner_id: USER_ID,
          include_original: true,
          include_translation: Boolean(activeDoc.translated_text),
        }),
      });
      setShared(true);
      setNotice('Document shared with the current room.');
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  async function saveDownload(urlPath: string, filename: string) {
    try {
      const r = await request(urlPath);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  async function downloadDoc() {
    if (!activeDoc) return;
    const access = shared ? `room_code=${encodeURIComponent(roomCode)}` : `owner_id=${encodeURIComponent(USER_ID)}`;
    await saveDownload(
      `/api/documents/${activeDoc.id}/download?${access}`,
      `${(activeDoc.filename || 'document').replace(/\.[^.]+$/, '')}_translated.docx`
    );
  }

  async function downloadOriginal() {
    if (!activeDoc) return;
    const access = shared ? `room_code=${encodeURIComponent(roomCode)}` : `owner_id=${encodeURIComponent(USER_ID)}`;
    const ext = (activeDoc.filename || 'document.txt').split('.').pop();
    await saveDownload(`/api/documents/${activeDoc.id}/original?${access}`, activeDoc.filename || `original.${ext}`);
  }

  async function copyRoom() {
    await navigator.clipboard.writeText(roomCode);
    setCopyDone(true);
    setTimeout(() => setCopyDone(false), 1200);
  }

  const nav: [Tab, string, any][] = [
    ['home', 'Overview', Home],
    ['rooms', 'Voice rooms', Phone],
    ['messages', 'Messages', MessageSquare],
    ['studio', 'Document studio', Languages],
    ['documents', 'My documents', FolderOpen],
  ];

  return (
    <div className="layout">
      {incomingCall && (
        <div className="incoming-overlay">
          <div className="incoming-card">
            <div className="incoming-icon">
              <Phone size={30} />
            </div>
            <span className="eyebrow">INCOMING BHASHACALL</span>
            <h2>Someone is calling</h2>
            <p>A participant in room {roomCode} is calling you.</p>
            <div className="incoming-actions">
              <button className="incoming-decline" onClick={declineCall}>
                <Phone size={17} /> Decline
              </button>
              <button className="incoming-accept" onClick={acceptCall}>
                <Phone size={17} /> Accept
              </button>
            </div>
          </div>
        </div>
      )}

      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">
            <AudioLines />
          </span>
          <span>
            bhasha<span>call</span>
          </span>
          <small>GNANI.AI</small>
        </div>
        <div className="nav-label">WORKSPACE</div>
        {nav.map(([id, label, Icon]) => (
          <button key={id} className={`side-link ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>
            <Icon size={17} />
            {label}
            {id === 'rooms' && connected && <i />}
          </button>
        ))}
        <div className="sidebar-bottom">
          <ShieldCheck size={15} /> Private by default · Gnani AI
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="crumb">BHASHACALL /</span>{' '}
            <strong>{nav.find((n) => n[0] === tab)?.[1]}</strong>
          </div>
          <div className="top-actions">
            <span className={`connection ${connected ? 'on' : ''}`} />
            {connected ? `Room ${roomCode}` : 'Not in a room'}
          </div>
        </header>

        {notice && (
          <div className="notice">
            <span>{notice}</span>
            <button onClick={() => setNotice('')}>
              <X size={15} />
            </button>
          </div>
        )}

        {tab === 'home' && (
          <>
            <section className="welcome">
              <div>
                <span className="eyebrow">LANGUAGE WITHOUT BARRIERS</span>
                <h1>
                  Every voice. Every language.
                  <br />
                  <em>One seamless conversation.</em>
                </h1>
                <p>
                  Speak naturally in your native language. Gnani Prisma v3.0 recognizes your speech,
                  translates it, and Gnani Timbre v2.5 speaks it in the other person's language.
                </p>
              </div>
              <div className="welcome-icon">
                <Languages size={54} />
                <AudioLines size={26} />
              </div>
            </section>
            <div className="quick-grid">
              <button onClick={() => setTab('rooms')}>
                <span className="quick-icon">
                  <Phone />
                </span>
                <b>Start a voice room</b>
                <small>Real-time multilingual voice calling</small>
              </button>
              <button onClick={() => setTab('studio')}>
                <span className="quick-icon">
                  <FileText />
                </span>
                <b>Translate a document</b>
                <small>Upload PDF, DOCX or TXT</small>
              </button>
              <button onClick={() => setTab('documents')}>
                <span className="quick-icon">
                  <FolderOpen />
                </span>
                <b>My documents</b>
                <small>Open your private translations</small>
              </button>
            </div>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">RECENT WORK</span>
                  <h2>Your documents</h2>
                </div>
                <button className="text-btn" onClick={() => setTab('documents')}>
                  View all →
                </button>
              </div>
              {docs.length ? (
                docs.slice(0, 4).map((d) => <DocRow key={d.id} doc={d} onOpen={() => openDoc(d.id)} />)
              ) : (
                <div className="empty">No documents yet. Upload one in Document Studio to get started.</div>
              )}
            </section>
          </>
        )}

        {tab === 'rooms' && (
          <>
            <section className="page-heading">
              <span className="eyebrow">GNANI.AI REAL-TIME COMMUNICATION</span>
              <h1>Voice rooms</h1>
              <p>
                Each speaker speaks in their own language. Gnani Prisma STT transcribes in real-time,
                translates the speech, and Gnani Timbre TTS speaks it to the other participant.
              </p>
            </section>

            <section className="room-grid">
              <div className="panel">
                <div className="panel-heading">
                  <h2>Room connection</h2>
                  <span className={`pill ${connected ? 'good' : ''}`}>
                    {connected ? 'CONNECTED' : 'NOT CONNECTED'}
                  </span>
                </div>
                <button className="primary" onClick={createRoom}>
                  <Radio size={17} /> Create new room
                </button>
                <div className="join">
                  <input
                    value={roomCode}
                    onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                    placeholder="Enter room code"
                    maxLength={7}
                  />
                  <button className="secondary" onClick={() => connectRoom()}>
                    Join room
                  </button>
                </div>
                {roomCode && (
                  <div className="room-code">
                    <div>
                      <small>ROOM CODE</small>
                      <b>{roomCode}</b>
                    </div>
                    <button className="secondary" onClick={copyRoom}>
                      {copyDone ? <Check size={15} /> : <Copy size={15} />} Copy
                    </button>
                  </div>
                )}
                <div className="status-text">{status}</div>
                <hr />

                <div className="panel-heading">
                  <h3>Language direction</h3>
                  <button className="swap" onClick={swapLanguages}>
                    <ArrowLeftRight size={16} /> Swap
                  </button>
                </div>
                <div className="language-selectors">
                  <label>
                    Speak in
                    <select
                      value={sourceLanguage}
                      disabled={callActive}
                      onChange={(e) => {
                        setSourceLanguage(e.target.value);
                        if (wsRef.current?.readyState === WebSocket.OPEN) {
                          wsRef.current.send(
                            JSON.stringify({
                              type: 'set_languages',
                              source_language: e.target.value,
                              target_language: targetLanguage,
                            })
                          );
                        }
                      }}
                    >
                      {LANGUAGES.map((language) => (
                        <option key={language.code} value={language.code}>
                          {language.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Translate to
                    <select
                      value={targetLanguage}
                      disabled={callActive}
                      onChange={(e) => {
                        setTargetLanguage(e.target.value);
                        if (wsRef.current?.readyState === WebSocket.OPEN) {
                          wsRef.current.send(
                            JSON.stringify({
                              type: 'set_languages',
                              source_language: sourceLanguage,
                              target_language: e.target.value,
                            })
                          );
                        }
                      }}
                    >
                      {LANGUAGES.map((language) => (
                        <option key={language.code} value={language.code}>
                          {language.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="lang-choice">
                  <small>
                    Powered by Gnani Prisma v3.0 STT & Timbre v2.5 TTS. Both participants select what they speak.
                  </small>
                </div>

                <div className="phone-call">
                  <div className={`call-orb ${isSpeaking ? 'speaking' : ''}`}>
                    <Phone size={30} />
                  </div>
                  <b>
                    {callPhase === 'outgoing'
                      ? 'Calling…'
                      : callPhase === 'connecting'
                      ? 'Connecting…'
                      : callPhase === 'connected'
                      ? (isSpeaking ? 'Speaking (Gnani STT Listening…)' : 'Live conversation')
                      : callPhase === 'incoming'
                      ? 'Incoming call'
                      : 'Ready to call'}
                  </b>
                  <span className="call-timer">{callActive ? formatCallTime(callSeconds) : 'No active call'}</span>
                  <small>
                    {callActive
                      ? (captionLive
                          ? (latestLatency ? `Gnani Real-time STT/TTS · Latency: ${latestLatency}ms` : 'Gnani STT streaming enabled · Speaking active')
                          : 'Audio connected')
                      : 'Real-time multilingual calling with Gnani AI'}
                  </small>
                  <div className="call-controls">
                    {callActive ? (
                      <>
                        <button className={`call-control ${callMuted ? 'muted' : ''}`} onClick={toggleMute}>
                          <Mic size={18} />
                          <small>{callMuted ? 'Unmute' : 'Mute'}</small>
                        </button>
                        <button className="call-control hangup" onClick={endLiveCall}>
                          <Phone size={18} />
                          <small>End call</small>
                        </button>
                      </>
                    ) : (
                      <button className="primary call-start" disabled={!connected} onClick={startLiveCall}>
                        <Phone size={17} /> Start live call
                      </button>
                    )}
                  </div>
                </div>

                {Object.entries(remoteStreams).map(([id]) => (
                  <audio
                    className="remote-audio"
                    key={id}
                    ref={(el) => {
                      remoteAudioRefs.current[id] = el;
                    }}
                    autoPlay
                    playsInline
                  />
                ))}

                <div className="record-row compact-record">
                  <div>
                    <b>Fallback: send a recorded phrase</b>
                    <small>Optional phrase-by-phrase mode via Gnani STT</small>
                  </div>
                  <button
                    className={`secondary ${recording ? 'danger' : ''}`}
                    disabled={!connected || busy || callActive}
                    onClick={recording ? stopRecording : startRecording}
                  >
                    {recording ? <X size={16} /> : <Mic size={16} />} {recording ? 'Stop & send' : 'Record phrase'}
                  </button>
                </div>
                <audio ref={audioRef} controls className="audio" />
              </div>

              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="eyebrow">GNANI.AI LIVE TRANSCRIPT</span>
                    <h2>Conversation captions</h2>
                  </div>
                  <button className="text-btn" onClick={() => setCaptions([])}>
                    Clear
                  </button>
                </div>
                <div className="caption-list">
                  {captions.length ? (
                    captions.map((c) => (
                      <div className="caption" key={c.id}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <small>
                            {c.from === participantRef.current ? 'YOU' : 'OTHER PARTICIPANT'} · ORIGINAL
                          </small>
                          {c.detected_language && (
                            <span style={{ fontSize: '11px', color: '#6366f1', background: '#eef2ff', padding: '2px 6px', borderRadius: '4px' }}>
                              Prisma v3.0 ({c.detected_language})
                            </span>
                          )}
                        </div>
                        <p>{c.original}</p>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
                          <small className="translated-label">TRANSLATION</small>
                          <span style={{ fontSize: '11px', color: '#059669', background: '#ecfdf5', padding: '2px 6px', borderRadius: '4px' }}>
                            Timbre v2.5
                          </span>
                        </div>
                        <p>{c.translated}</p>
                        {c.latency_ms && (
                          <small style={{ fontSize: '10px', color: '#888', display: 'block', marginTop: '2px' }}>
                            End-to-end latency: {c.latency_ms}ms
                          </small>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="empty">Your original and translated phrases will appear here.</div>
                  )}
                </div>
              </div>
            </section>

            <section className="panel chat-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">ROOM CONVERSATION</span>
                  <h2>Text chat</h2>
                </div>
                <span className="pill">TRANSLATED</span>
              </div>
              <div className="chat-list">
                {chat.map((m) => (
                  <div className={`chat-bubble ${m.mine ? 'mine' : ''}`} key={m.id}>
                    <small>{m.mine ? 'You' : m.sender_id.slice(0, 8)}</small>
                    <p>{m.original_text}</p>
                    <p className="chat-translated">{m.translated_text}</p>
                    {m.pending && <small>Sending…</small>}
                    {m.translation_error && (
                      <small className="chat-warning">Delivered, but translation unavailable: {m.translation_error}</small>
                    )}
                  </div>
                ))}
                {!chat.length && <div className="empty">Room messages will appear here.</div>}
              </div>
              <div className="chat-compose">
                <input
                  value={chatText}
                  onChange={(e) => setChatText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendChat()}
                  placeholder="Write a message to the room…"
                />
                <button className="primary" disabled={!connected || !chatText.trim()} onClick={sendChat}>
                  Send
                </button>
              </div>
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">ROOM FILES</span>
                  <h2>Shared documents</h2>
                </div>
                <span className="pill">COLLABORATIVE</span>
              </div>
              {sharedDocs.length ? (
                sharedDocs.map((d) => <DocRow key={d.id} doc={d} onOpen={() => openDoc(d.id, true)} />)
              ) : (
                <div className="empty">
                  No documents have been shared in this room yet. Share one from Document Studio.
                </div>
              )}
            </section>
          </>
        )}

        {tab === 'messages' && (
          <>
            <section className="page-heading">
              <span className="eyebrow">MESSAGING</span>
              <h1>Messages</h1>
              <p>Translate a message instantly across the 6 supported languages, or open a room for shared live chat.</p>
            </section>
            <section className="panel">
              <div className="panel-heading">
                <h2>Quick text translation</h2>
                <span className="pill">NO ROOM REQUIRED</span>
              </div>
              <textarea
                className="message-textarea"
                value={standaloneText}
                onChange={(e) => setStandaloneText(e.target.value)}
                placeholder="Write something to translate…"
              />
              <div className="language-selectors message-language-selectors">
                <label>
                  From
                  <select value={sourceLanguage} onChange={(e) => setSourceLanguage(e.target.value)}>
                    {LANGUAGES.map((language) => (
                      <option key={language.code} value={language.code}>
                        {language.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  To
                  <select value={targetLanguage} onChange={(e) => setTargetLanguage(e.target.value)}>
                    {LANGUAGES.map((language) => (
                      <option key={language.code} value={language.code}>
                        {language.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="swap" onClick={swapLanguages}>
                  <ArrowLeftRight size={15} /> Swap
                </button>
                <button
                  className="primary"
                  disabled={!standaloneText.trim() || standaloneBusy || sourceLanguage === targetLanguage}
                  onClick={translateStandalone}
                >
                  {standaloneBusy ? 'Translating…' : 'Translate text'}
                </button>
              </div>
              {standaloneResult && (
                <div className="standalone-result">
                  <small>ORIGINAL</small>
                  <p>{standaloneResult.original_text}</p>
                  <small className="translated-label">TRANSLATION</small>
                  <p>{standaloneResult.translated_text}</p>
                </div>
              )}
            </section>
            <section className="panel">
              <div className="panel-heading">
                <h2>Room messages</h2>
              </div>
              <p className="muted">Open a room to send and receive translated messages with participants.</p>
              <button className="primary" onClick={() => setTab('rooms')}>
                <MessageSquare size={16} /> Open voice room chat
              </button>
            </section>
          </>
        )}

        {tab === 'studio' && (
          <>
            <section className="page-heading">
              <span className="eyebrow">PRIVATE DOCUMENT WORKSPACE</span>
              <h1>Document studio</h1>
              <p>
                Translate documents across 6 Indian languages and listen using Gnani Timbre v2.5 TTS voices.
              </p>
            </section>
            <section className="studio-grid">
              <div className="panel upload-panel">
                <div className="panel-heading">
                  <h2>1. Upload document</h2>
                  <span className="pill">PRIVATE</span>
                </div>
                <div className="dropzone" onClick={() => fileRef.current?.click()}>
                  <Upload size={25} />
                  <b>{uploading ? 'Uploading…' : 'Choose a document'}</b>
                  <span>PDF (including scanned), DOCX or TXT · Up to 50 MB</span>
                  <button className="secondary">Browse files</button>
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  hidden
                  onChange={(e) => uploadFile(e.target.files?.[0])}
                />
                {activeDoc && (
                  <div className="selected-file">
                    <FileText size={19} />
                    <div>
                      <b>{activeDoc.filename || activeDoc.original_name}</b>
                      <small>{activeDoc.status || 'uploaded'}</small>
                    </div>
                  </div>
                )}
              </div>
              <div className="panel">
                <div className="panel-heading">
                  <h2>2. Translate</h2>
                  <Languages size={18} />
                </div>
                <label>Original language</label>
                <select value={source} onChange={(e) => setSource(e.target.value)}>
                  <option value="auto">Auto detect</option>
                  {LANGUAGES.map((language) => (
                    <option key={language.code} value={language.code}>
                      {language.label}
                    </option>
                  ))}
                </select>
                <label>Translate into</label>
                <select value={target} onChange={(e) => setTarget(e.target.value)}>
                  {LANGUAGES.map((language) => (
                    <option key={language.code} value={language.code}>
                      {language.label}
                    </option>
                  ))}
                </select>
                <button className="primary full" disabled={!activeDoc || working} onClick={translateDoc}>
                  {working ? <RefreshCw className="spin" size={16} /> : <Languages size={16} />}{' '}
                  {working ? 'Translating…' : 'Translate document'}
                </button>
                <small className="muted">
                  Supports documents up to 2 million characters with page-by-page OCR and text cleaning. Listen
                  to translated paragraphs using verified Gnani Timbre voices.
                </small>
              </div>
            </section>

            {activeDoc && (
              <section className="panel preview-panel">
                <div className="panel-heading">
                  <div>
                    <span className="eyebrow">DOCUMENT PREVIEW</span>
                    <h2>{activeDoc.filename || activeDoc.original_name}</h2>
                  </div>
                  <span className={`pill ${activeDoc.status === 'translated' ? 'good' : ''}`}>
                    {activeDoc.status}
                  </span>
                </div>
                <div className="preview-columns">
                  <div>
                    <h3>Original text</h3>
                    <pre>{activeDoc.original_text || 'Original text preview is loading.'}</pre>
                  </div>
                  <div>
                    <h3>Translated text</h3>
                    <pre>{activeDoc.translated_text || 'Translate this document to see the result here.'}</pre>
                  </div>
                </div>
                {(activeDoc.translated_text || activeDoc.original_text) && (
                  <div className="doc-actions">
                    <button className="secondary" onClick={downloadOriginal}>
                      <Download size={16} /> Download original
                    </button>
                    {activeDoc.translated_text && (
                      <>
                        <button className="primary" onClick={downloadDoc}>
                          <Download size={16} /> Download translated DOCX
                        </button>
                        <button className="secondary" disabled={audioBusy} onClick={listenDoc}>
                          {audioBusy ? <RefreshCw size={16} /> : <Volume2 size={16} />} Listen to section{' '}
                          {listenIndex + 1}
                        </button>
                        <button className="primary" disabled={audioBusy} onClick={listenFullDoc}>
                          <Play size={16} /> Listen to full document
                        </button>
                        <button
                          className="secondary"
                          disabled={!audioPlaying && !audioPaused}
                          onClick={pauseResumeDoc}
                        >
                          {audioPaused || !audioPlaying ? <Play size={16} /> : <Pause size={16} />}{' '}
                          {audioPaused || !audioPlaying ? 'Resume' : 'Pause'}
                        </button>
                        <button
                          className="secondary"
                          onClick={() => {
                            audioSequenceRef.current = false;
                            docAudioRef.current?.pause();
                            setAudioPlaying(false);
                            setAudioPaused(false);
                            setListenIndex((i) => Math.max(0, i - 1));
                          }}
                        >
                          Previous
                        </button>
                        <button
                          className="secondary"
                          onClick={() => {
                            audioSequenceRef.current = false;
                            docAudioRef.current?.pause();
                            setAudioPlaying(false);
                            setAudioPaused(false);
                            setListenIndex((i) => i + 1);
                          }}
                        >
                          Next section
                        </button>
                        <button className="secondary" disabled={!connected || shared} onClick={shareDoc}>
                          <Share2 size={16} /> {shared ? 'Shared with room' : 'Share to room'}
                        </button>
                      </>
                    )}
                  </div>
                )}
                {activeDoc.translated_text && (
                  <div className="document-audio-player">
                    <div className="audio-player-label">
                      <b>Gnani Timbre v2.5 Audio Player</b>
                      <small>
                        {audioProgress.total
                          ? `Section ${audioProgress.current} of ${audioProgress.total}`
                          : 'Ready to listen'}
                      </small>
                    </div>
                    <audio
                      ref={docAudioRef}
                      controls
                      className="audio"
                      onEnded={handleDocAudioEnded}
                      onPause={handleDocumentAudioPause}
                      onPlay={handleDocumentAudioPlay}
                    />
                  </div>
                )}
              </section>
            )}
          </>
        )}

        {tab === 'documents' && (
          <>
            <section className="page-heading">
              <span className="eyebrow">YOUR PRIVATE LIBRARY</span>
              <h1>My documents</h1>
              <p>Only you can access these documents unless you explicitly share them with a room.</p>
              <button className="primary" onClick={() => setTab('studio')}>
                <Upload size={16} /> Upload a document
              </button>
            </section>
            <section className="panel">
              {docs.length ? (
                docs.map((d) => <DocRow key={d.id} doc={d} onOpen={() => openDoc(d.id)} />)
              ) : (
                <div className="empty">Your document library is empty.</div>
              )}
            </section>
          </>
        )}

        <footer>
          <span>© BhashaCall · Powered by Gnani.ai Speech Intelligence</span>
          <span>
            <Sparkles size={14} /> Prisma v3.0 STT · Timbre v2.5 TTS · 6 Indian Languages
          </span>
        </footer>
      </main>
    </div>
  );
}

function DocRow({ doc, onOpen }: { doc: Doc; onOpen: () => void }) {
  return (
    <button className="doc-row" onClick={onOpen}>
      <span className="file-icon">
        <FileText size={18} />
      </span>
      <span className="doc-meta">
        <b>{doc.original_name}</b>
        <small>
          {doc.source_language && doc.target_language
            ? `${doc.source_language.toUpperCase()} → ${doc.target_language.toUpperCase()} · `
            : ''}
          {doc.created_at || 'Your private document'}
        </small>
      </span>
      <span className={`pill ${doc.status === 'translated' ? 'good' : ''}`}>{doc.status}</span>
      <span className="open-arrow">Open →</span>
    </button>
  );
}
