/** Browser text-to-speech helpers for the FestOS assistant. */

export const ttsSupported = typeof window !== "undefined" && "speechSynthesis" in window;

/** Strip markdown, citations, and symbols that would be read aloud awkwardly. */
function cleanForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " code block omitted. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\s*\(plan #\d+\)\s*/gi, " ")
    .replace(/[#*_>|~]/g, " ")
    .replace(/\b(Source|Ref|Reference|audit \d+)[:\s]/gi, " ")
    .replace(/:\s*\/\//g, " ")
    .replace(/https?:\S+/g, " ")
    .replace(/\s*\b(?=[A-Z]{3,}\d*)\b:?/g, " ")
    .replace(/[•・▪»]+\s*/g, " ")
    .replace(/(\b[^\s.]{20,})\b/g, (w) => (/@|\d|[A-Z]/.test(w) ? " " : w))
    .replace(/₹\s?/g, "rupees ")
    .replace(/\s*\n+/g, ". ")
    .replace(/\s{2,}/g, " ")
    .replace(/\.\s*\./g, ".")
    .trim()
    .slice(0, 600);
}

/** Speak the given text aloud, cancelling anything already speaking. */
export function speak(text: string) {
  if (!ttsSupported || !text) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const utterance = new SpeechSynthesisUtterance(cleanForSpeech(text));
  const voices = synth.getVoices();
  const voice =
    voices.find((v) => v.lang.startsWith("en") && /google|natural|neural/i.test(v.name)) ||
    voices.find((v) => v.lang.startsWith("en"));
  if (voice) utterance.voice = voice;
  utterance.rate = 1.02;
  utterance.pitch = 1;
  synth.speak(utterance);
}

/** Stop any speech currently in progress. */
export function stopSpeaking() {
  if (ttsSupported) window.speechSynthesis.cancel();
}

/* ---------------- Speech-to-text (Web Speech API) ---------------- */

type RecognizerResult = { isFinal: boolean; [index: number]: { transcript: string } };
type RecognizerEvent = { resultIndex: number; results: { length: number; [index: number]: RecognizerResult } };
export type Recognizer = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: RecognizerEvent) => void) | null;
  onerror: ((e: unknown) => void) | null;
  onend: (() => void) | null;
};

type WindowWithSpeech = Window & typeof globalThis & {
  SpeechRecognition?: new () => Recognizer;
  webkitSpeechRecognition?: new () => Recognizer;
};

const getRecognitionCtor = (): (new () => Recognizer) | null =>
  (window as WindowWithSpeech).SpeechRecognition ?? (window as WindowWithSpeech).webkitSpeechRecognition ?? null;

export const sttSupported = typeof window !== "undefined" && getRecognitionCtor() !== null;

/**
 * Create a one-shot recognizer for a single question.
 * Speech is sent to onInterim live, and the final sentence to onFinal when the user pauses.
 */
export function createRecognizer(
  lang: string,
  onInterim: (text: string) => void,
  onFinal: (text: string) => void,
  onError: (message: string) => void,
): Recognizer | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = lang;
  rec.continuous = false;
  rec.interimResults = true;
  let finalSent = false;
  rec.onresult = (e) => {
    if (finalSent) return;
    let interim = "";
    let final = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) final += r[0].transcript;
      else interim += r[0].transcript;
    }
    if (final.trim()) {
      finalSent = true;
      onFinal(final.trim());
    } else if (interim.trim()) {
      onInterim(interim.trim());
    }
  };
  rec.onerror = (e) => onError(String((e as { error?: string })?.error ?? "recognition failed"));
  return rec;
}

export function micPermissionError(code: string): string {
  const map: Record<string, string> = {
    "not-allowed": "microphone access was blocked — allow it in your browser settings",
    "service-not-allowed": "microphone service unavailable in this browser",
    "no-speech": "no speech was detected — try again",
    "audio-capture": "no microphone found",
    "network": "speech recognition needs a network connection",
  };
  return map[code] ?? "speech recognition failed — type your question instead";
}
