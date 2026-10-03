/**
 * Voice Input & Speech Synthesis Controller
 * Integrates Web Speech API (SpeechRecognition & SpeechSynthesis)
 */

class VoiceController {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.ttsEnabled = true;
        this.synth = window.speechSynthesis || null;
        this.onTranscriptCallback = null;
        this.onFinalSpeechCallback = null;
        this.onStatusChangeCallback = null;

        this.initRecognition();
    }

    initRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn("Web Speech API is not supported by this browser.");
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false; // Turn-based speech recognition
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-IN'; // Indian English / Global English support

        this.recognition.onstart = () => {
            this.isListening = true;
            if (this.onStatusChangeCallback) this.onStatusChangeCallback('listening');
        };

        this.recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            const current = finalTranscript || interimTranscript;
            if (this.onTranscriptCallback) {
                this.onTranscriptCallback(current, !!finalTranscript);
            }

            if (finalTranscript && this.onFinalSpeechCallback) {
                this.onFinalSpeechCallback(finalTranscript.trim());
            }
        };

        this.recognition.onerror = (event) => {
            console.warn("Speech recognition error:", event.error);
            this.isListening = false;
            if (this.onStatusChangeCallback) this.onStatusChangeCallback('error', event.error);
        };

        this.recognition.onend = () => {
            this.isListening = false;
            if (this.onStatusChangeCallback) this.onStatusChangeCallback('idle');
        };
    }

    toggleListening() {
        if (!this.recognition) {
            alert("Speech recognition is not supported in this browser. Please use Chrome, Edge, or the text input box below.");
            return;
        }

        if (this.isListening) {
            this.recognition.stop();
        } else {
            try {
                this.recognition.start();
            } catch (e) {
                console.error("SpeechRecognition start failed:", e);
            }
        }
    }

    speak(text) {
        if (!this.ttsEnabled || !this.synth) return;
        
        // Cancel any ongoing speech
        this.synth.cancel();

        // Strip HTML or special symbols if present
        const cleanText = text.replace(/<[^>]*>?/gm, '').replace(/₹/g, 'rupees ');
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.lang = 'en-US';

        this.synth.speak(utterance);
    }
}

// Global Voice Instance
window.voiceCtrl = new VoiceController();
