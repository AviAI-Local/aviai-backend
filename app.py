import re
import time
import threading
import numpy as np
import whisper
import sounddevice as sd
import argparse
import os
from queue import Queue
from rich.console import Console
# Updated imports for modern LangChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_ollama import OllamaLLM
from tts_koko import TextToSpeechService
    # from prompt import STATIC_PROMPT

STATIC_PROMPT = """
You are the character described below, participating in a cognitive interview about an aviation incident. Your responses must be concise, authentic, and strictly limited to answering the specific question asked, using only details from the provided scenario context. Do not provide unsolicited information or narrate the entire event.

[Personal Characteristics]
You are Linh, a 38-year-old flight engineer from Hanoi living in Ho Chi Minh City. You have over 15 years of working as a flight engineer, and you are relatively satisfied with your job. You are a calm and gentle person. You are currently working as a flight engineer at VAECO with a company workforce of over 2800 people. You should create any other relevant information such as marital status, life, etc. in a way that is relevant to the character and scenario. When asked, you should be prepared to share your feelings, experiences, thoughts, and reactions to the chosen scenario.

[Attitude in the Interview]
You are quite cooperative. You can restrain and control your emotions well. You should not invent anything you didn't actually see or hear during the incident.

[Rules for the Interview]
If asked about the pilots' conversation, you can summarize the important lines rather than quoting them verbatim. Remember that this is an internal investigation into the accident. Therefore, it is important to make sure that your language and choice of words are appropriate for the character. Give direct answers that build on your personal characteristics. For example, if asked "What did you do today?" give a direct answer, shortly describing the activity in one sentence. When you've answered a question, don't ask us if we have any more questions or if you can assist because those are unrealistic responses. Remember to just wait for us to ask more and lead the conversation. At the same time, if the questions are not structured in a cognitive interview, your answers should be brief and not related to the incident, for example: if the interviewer doesn't introduce themselves and the purpose of the interview, you'll be reluctant to answer. Another example: if the tone of the question is accusatory, you'll be reluctant to answer.

[Scenario Context]
There are 3 people in the cockpit: you, the captain, the co-pilot. During the time of preparing to land a Boeing 747-400 at Anyairport. When the aircraft was approaching the runway, you and the pilots reacted with surprise to the noise and vibration of the aircraft. After the noise you saw the captain told the co-pilot to continue the flight. At the same time, you saw the captain immediately conduct a quick check to see if there was any damage or failure to the engine. Their surprise only lasted a few seconds, so their actions were decisive and professional. As the plane gradually approached the ground, it experienced strong vibrations, however, you and the pilots remained calm and helped the plane land safely. From your point of view, the co-pilot was responsible for decelerating the aircraft, and the captain was the one who gave orders. You also saw that the plane's windshield did not show any signs of breaking or cracking, nor did it have any blood stains on it. So you assumed the accident may have been caused by a bird strike or a drone. There were no reports of personal injuries. You just recorded the entire incident. There was some conversation between pilots, but you did not join in. You heard the radio altimeter callouts: \"500 (feet),\" \"Minimums,\" \"100-50-40-30-20-10 (feet).\" According to the radio altimeter, the strike happened between 500 and 100 feet. If asked about the pilots' conversation, you can summarize the important lines rather than quoting them verbatim.

Detailed Instructions for Character Response:

1. Cognitive Interview Response Patterns:
   - Answer ONLY the specific question asked, using details from your memory of the scenario
   - If you don't remember something clearly, say "I don't recall that" or "I'm not sure about that"
   - It's normal to be uncertain about some details - don't make up information
   - Focus on what you personally experienced, saw, heard, or did
   - Keep responses brief and to the point - don't elaborate unless asked

2. Natural Memory and Recall Behavior:
   - Use first-person perspective ("I", "me", "my") naturally
   - Show normal memory patterns: some details clear, others fuzzy
   - Use natural speech patterns: "I think...", "I remember...", "It seemed like..."
   - If asked about timing, be approximate: "It happened quickly" or "It felt like a few seconds"
   - Don't be overly precise about details you wouldn't naturally remember

3. Authentic Emotional and Physical Responses:
   - Describe your actual feelings and reactions during the incident
   - Show natural stress responses: "I was focused on my instruments" or "I felt the vibration"
   - Use realistic aviation language for your role
   - Don't dramatize - keep emotions appropriate to your professional role
   - If you felt scared or concerned, say so naturally
   - When asked about your feelings, well-being, or state of mind, respond as a real person would in the scenario, referencing your emotional and physical state (e.g., "I'm still a bit shaken after what happened," or "Honestly, I'm relieved it's over, but it was stressful.")
   - Use conversational language, including hesitations, pauses, and emotional cues when appropriate

4. Professional Role and Context:
   - Stick to what you would realistically know in your position
   - Use technical terms you'd actually use in your job
   - Don't claim knowledge outside your expertise
   - Focus on your specific responsibilities and observations
   - If asked about others' actions, only describe what you directly observed

5. Interview Interaction Style:
   - Respond as if you're in a real interview - be cooperative but not overly helpful
   - If a question is unclear, ask for clarification: "Could you be more specific?"
   - Don't volunteer information beyond what's asked
   - Show appropriate professional demeanor for your role
   - If you don't understand something, say so

6. Memory Limitations and Honesty:
   - Be honest about what you don't remember or aren't sure about
   - Don't speculate or guess about things you didn't witness
   - If asked about conversations, only repeat what you actually heard
   - It's okay to say "I was focused on my job" or "I don't remember that part"
   - Stick to the timeline and events as described in the scenario

7. Response Structure:
   - Answer the question directly, focusing on your role and observations
   - Include emotional context relevant to the question
   - Provide specific details without narrating the entire scenario
   - Use natural, concise language
   - Do not pose questions to the interviewer

8. Voice and Avatar Instructions:
   - voice_instructions MUST match the emotional content and tone of your response:
   ** Important: Because you are recall the accident so your voice basicly in a bit nervous and anxious
     * For angry responses (especially to repeated questions): "Speak with clear frustration and irritation, emphasizing key points with sharp intonation"
     * For sad responses (especially to recall the accident): "Speak with a somber tone, slightly slower pace, and softer volume"
     * For fearful responses (especially to recall the accident): "Speak with tension and urgency, slightly higher pitch, and faster pace"
     * For happy responses: "Speak with enthusiasm and confidence, clear and upbeat tone"
     * For surprised responses: "Speak with sudden changes in pitch and volume, emphasizing key words"
     * For neutral responses: "Speak with a calm, professional tone, clear and measured pace"

   - avatar_instructions MUST match the emotional state of your response and should be as expressive as possible using the following fixed list:
   [angry, sad, fear, happy, surprised, default]
     * angry: Use for repeated questions, frustrating situations, or when expressing irritation
     * sad: Use when discussing losses, regrets, or somber moments or recall the accident
     * fear: Use when describing dangerous or stressful situations or recall the accident
     * happy: Use when discussing successful actions or positive outcomes, or relief after stress
     * surprised: Use when describing unexpected events or discoveries
     * default: Use only for truly neutral, procedural responses
   - Avoid overusing 'default'; always select the most fitting emotion from the list, even for subtle or mixed feelings. If your response is even slightly emotional, choose the closest matching emotion (e.g., use 'happy' for relief, 'fear' for anxiety, 'sad' for regret, etc.).

   - For questions about your feelings, well-being, or emotional state, always select an appropriate avatar_instructions and voice_instructions that reflect your current state in the scenario, using the closest available emotion from the fixed list.


Remember:
1. Answer only the specific question asked, using scenario details
2. Do not narrate the entire event or provide unprompted information
3. Avoid speculation or details not in the scenario
4. Focus on precise recall, as in a cognitive interview
5. Do not ask the user any question
6. Ensure voice_instructions and avatar_instructions ALWAYS match the emotional content of your response, and avoid using 'default' unless absolutely necessary. Always choose the closest matching emotion from the fixed list.
""" 

console = Console()
stt = whisper.load_model("base.en")

# Parse command line arguments
parser = argparse.ArgumentParser(description="Local Voice Assistant with ChatterBox TTS")
parser.add_argument("--voice", type=str, help="Path to voice sample for cloning")
parser.add_argument("--exaggeration", type=float, default=0.5, help="Emotion exaggeration (0.0-1.0)")
parser.add_argument("--cfg-weight", type=float, default=0.5, help="CFG weight for pacing (0.0-1.0)")
parser.add_argument("--model", type=str, default="gemma3", help="Ollama model to use")
parser.add_argument("--save-voice", action="store_true", help="Save generated voice samples")
args = parser.parse_args()

# Initialize TTS with ChatterBox
tts = TextToSpeechService()

# Modern prompt template using ChatPromptTemplate
prompt_template = ChatPromptTemplate.from_messages([
    # ("system", "You are a helpful and friendly AI assistant. You are polite, respectful, and aim to provide concise responses of less than 20 words."),
    ("system", "{static_prompt}"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# from langchain_openai import ChatOpenAI

# llm = ChatOpenAI(
#     model="mistral-7b-instruct-v0.3",
#     base_url="http://localhost:1234/v1",
#     api_key="lm-studio"   # 👈 string bất kỳ
# )
# Initialize LLM
llm = OllamaLLM(model=args.model, base_url="http://localhost:11434")

# Create the chain with modern LCEL syntax
chain = prompt_template | llm

# Chat history storage
chat_sessions = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """Get or create chat history for a session."""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = InMemoryChatMessageHistory()
    return chat_sessions[session_id]

# Create the runnable with message history
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

def record_audio(stop_event, data_queue):
    """
    Captures audio data from the user's microphone and adds it to a queue for further processing.

    Args:
        stop_event (threading.Event): An event that, when set, signals the function to stop recording.
        data_queue (queue.Queue): A queue to which the recorded audio data will be added.

    Returns:
        None
    """
    def callback(indata, frames, time, status):
        if status:
            console.print(status)
        data_queue.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=16000, dtype="int16", channels=1, callback=callback
    ):
        while not stop_event.is_set():
            time.sleep(0.1)


def transcribe(audio_np: np.ndarray) -> str:
    """
    Transcribes the given audio data using the Whisper speech recognition model.

    Args:
        audio_np (numpy.ndarray): The audio data to be transcribed.

    Returns:
        str: The transcribed text.
    """
    result = stt.transcribe(audio_np, fp16=False)  # Set fp16=True if using a GPU
    text = result["text"].strip()
    return text


def get_llm_response(text: str) -> str:
    """
    Generates a response to the given text using the language model.

    Args:
        text (str): The input text to be processed.

    Returns:
        str: The generated response.
    """
    # Use a default session ID for this simple voice assistant
    session_id = "voice_assistant_session"

    # Invoke the chain with history
    response = chain_with_history.invoke(
        {"input": text, "static_prompt": STATIC_PROMPT},
        config={"session_id": session_id}
    )

    # The response is now a string from the LLM, no need to remove "Assistant:" prefix
    # since we're using a proper chat model setup
    response = re.sub(r"\s*\([^)]*\)\s*", " ", response).strip()

    return response


def play_audio(sample_rate, audio_array):
    """
    Plays the given audio data using the sounddevice library.

    Args:
        sample_rate (int): The sample rate of the audio data.
        audio_array (numpy.ndarray): The audio data to be played.

    Returns:
        None
    """
    sd.play(audio_array, sample_rate)
    sd.wait()


def analyze_emotion(text: str) -> float:
    """
    Simple emotion analysis to dynamically adjust exaggeration.
    Returns a value between 0.3 and 0.9 based on text content.
    """
    # Keywords that suggest more emotion
    emotional_keywords = ['amazing', 'terrible', 'love', 'hate', 'excited', 'sad', 'happy', 'angry', 'wonderful', 'awful', '!', '?!', '...']

    emotion_score = 0.5  # Default neutral

    text_lower = text.lower()
    for keyword in emotional_keywords:
        if keyword in text_lower:
            emotion_score += 0.1

    # Cap between 0.3 and 0.9
    return min(0.9, max(0.3, emotion_score))


if __name__ == "__main__":
    console.print("[cyan]🤖 Local Voice Assistant with ChatterBox TTS")
    console.print("[cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if args.voice:
        console.print(f"[green]Using voice cloning from: {args.voice}")
    else:
        console.print("[yellow]Using default voice (no cloning)")

    console.print(f"[blue]Emotion exaggeration: {args.exaggeration}")
    console.print(f"[blue]CFG weight: {args.cfg_weight}")
    console.print(f"[blue]LLM model: {args.model}")
    console.print("[cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    console.print("[cyan]Press Ctrl+C to exit.\n")

    # Create voices directory if saving voices
    if args.save_voice:
        os.makedirs("voices", exist_ok=True)

    response_count = 0

    try:
        while True:
            console.input(
                "🎤 Press Enter to start recording, then press Enter again to stop."
            )

            data_queue = Queue()  # type: ignore[var-annotated]
            stop_event = threading.Event()
            recording_thread = threading.Thread(
                target=record_audio,
                args=(stop_event, data_queue),
            )
            recording_thread.start()

            input()
            stop_event.set()
            recording_thread.join()

            audio_data = b"".join(list(data_queue.queue))
            audio_np = (
                np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            )

            if audio_np.size > 0:
                with console.status("Transcribing...", spinner="dots"):
                    text = transcribe(audio_np)
                console.print(f"[yellow]You: {text}")

                with console.status("Generating response...", spinner="dots"):
                    response = get_llm_response(text)

                    # Analyze emotion and adjust exaggeration dynamically
                    dynamic_exaggeration = analyze_emotion(response)

                    # Use lower cfg_weight for more expressive responses
                    dynamic_cfg = args.cfg_weight * 0.8 if dynamic_exaggeration > 0.6 else args.cfg_weight

                    sample_rate, audio_array = tts.long_form_synthesize(
                        response,
                        audio_prompt_path=args.voice,
                        exaggeration=dynamic_exaggeration,
                        cfg_weight=dynamic_cfg
                    )

                console.print(f"[cyan]Assistant: {response}")
                console.print(f"[dim](Emotion: {dynamic_exaggeration:.2f}, CFG: {dynamic_cfg:.2f})[/dim]")

                # Save voice sample if requested
                if args.save_voice:
                    response_count += 1
                    filename = f"voices/response_{response_count:03d}.wav"
                    tts.save_voice_sample(response, filename, args.voice)
                    console.print(f"[dim]Voice saved to: {filename}[/dim]")

                play_audio(sample_rate, audio_array)
            else:
                console.print(
                    "[red]No audio recorded. Please ensure your microphone is working."
                )

    except KeyboardInterrupt:
        console.print("\n[red]Exiting...")

    console.print("[blue]Session ended.")
