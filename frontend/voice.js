/* Voice input and output via the browser's Web Speech API (FR-05).
   Exposes window.KQVoice. Every feature degrades gracefully: callers check
   the *Supported flags and hide controls the browser can't provide. */
(function () {
  "use strict";

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const synth = window.speechSynthesis;
  const LANG = "en-GB";
  let recognizer = null;

  function listen({ onInterim, onFinal, onEnd, onError }) {
    if (!Recognition) return false;
    stopListening();
    recognizer = new Recognition();
    recognizer.lang = LANG;
    recognizer.interimResults = true;
    recognizer.maxAlternatives = 1;

    recognizer.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          onFinal && onFinal(transcript.trim());
        } else {
          interim += transcript;
        }
      }
      if (interim && onInterim) onInterim(interim.trim());
    };
    recognizer.onerror = (event) => onError && onError(event.error);
    recognizer.onend = () => {
      recognizer = null;
      onEnd && onEnd();
    };
    recognizer.start();
    return true;
  }

  function stopListening() {
    if (recognizer) recognizer.stop();
  }

  function speak(text) {
    if (!synth || !text) return;
    const utterance = new SpeechSynthesisUtterance(
      // Read bullet lists naturally rather than announcing "dash"
      text.replace(/^\s*-\s*/gm, "").replace(/\n+/g, ". ")
    );
    utterance.lang = LANG;
    synth.speak(utterance);
  }

  function cancelSpeech() {
    if (synth) synth.cancel();
  }

  window.KQVoice = {
    recognitionSupported: Boolean(Recognition),
    synthesisSupported: Boolean(synth),
    listen,
    stopListening,
    speak,
    cancelSpeech,
  };
})();
