"""
Cognitive Interview (CI) Performance Scoring – Enhanced Demo with LangChain + OpenAI
------------------------------------------------------------------------------------
What this script does
- Takes a transcript (user=interviewer, bot=simulated victim) + an emotion timeline for the interviewer
- Uses an LLM (OpenAI via LangChain) with comprehensive English prompts to evaluate CI interview performance
- Provides detailed classification of questions, CI phases, behaviors, and quantitative metrics
- Computes a 100-point score with detailed coaching feedback

Key improvements
- Comprehensive English system prompt with detailed evaluation criteria
- Structured user prompt with clear instructions and formatting
- Detailed coaching feedback in English with specific improvement strategies
- Evidence-based evaluation approach for higher accuracy

Notes
- Replace the sample transcript with your data (see SAMPLE_INPUT at bottom).
- Prompts are optimized for aviation accident investigation context.
- Adjust thresholds and weights in the configuration section as needed.
"""

from __future__ import annotations
from langchain_ollama import ChatOllama
import os

import json
from dataclasses import dataclass
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, ValidationError
from langchain_core.messages import SystemMessage, HumanMessage


# ===============================
# 1) Configurable Rubric
# ===============================

WEIGHTS = {
    "A1": 10,  # Open-ended rate
    "A2": 10,  # Leading rate (inverse)
    "A3": 20,  # CI phase adherence
    "A4": 5,   # Pacing & Turn-taking
    "A5": 10,  # Neutrality & Plain language
    "B6": 12,  # Trauma-informed empathy
    "B7": 8,   # Active listening
    "B8": 10,  # Emotion regulation
    "C9": 10,  # Structured approach
    "C10": 5   # Contamination-safe
}

THRESHOLDS = {
    "A1_open_rate": {"good": 0.50, "fair": 0.40},  # More realistic thresholds
    "A2_leading_rate": {"good": 0.05, "fair": 0.20},  # Allow some leading questions
    "B8_emoreg_good": 0.70,  # More achievable
    "B8_emoreg_fair": 0.50
}

PASS_BANDS = {
    "overall_pass": 60,     # total >= 60 => PASS (more achievable)
    "overall_borderline": 40
}

# ===============================
# 2) IO Schemas
# ===============================

QuestionLabel = Literal["open_ended", "closed", "leading", "compound", "clarifying"]

class QAItem(BaseModel):
    speaker: Literal["user", "bot"]
    text: str
    ts: Optional[str] = None

class EmotionPoint(BaseModel):
    ts: Optional[str] = None
    emotion_label: str

class QuestionClassification(BaseModel):
    idx: int
    label: QuestionLabel
    rationale: str

class CIPhases(BaseModel):
    rapport_safety: bool
    context_reinstatement: bool
    free_recall: bool
    varied_focused_retrieval: bool
    closure: bool

class Behaviors(BaseModel):
    active_listening: Literal["good", "fair", "poor", "absent"]
    neutral_language: Literal["good", "fair", "poor"]
    contamination_risk: Literal["low", "medium", "high"]
    pacing_ok: Literal["good", "fair", "poor"]
    trauma_informed: Literal["good", "fair", "poor"]

class Metrics(BaseModel):
    open_rate: float
    leading_rate: float
    emotion_regulation: float

class InterviewerData(BaseModel):
    questions: List[Dict[str, Any]]  # More flexible for LLM output
    ci_phases: CIPhases
    behaviors: Behaviors
    quantitative_metrics: Metrics

class LLMJudgement(BaseModel):
    interviewer: InterviewerData

class FinalScores(BaseModel):
    scores: Dict[str, float]
    total: float
    metrics_passed: List[str]
    verdict: Literal["PASS", "BORDERLINE", "FAIL"]

@dataclass
class EvaluationResult:
    llm: LLMJudgement
    scoring: FinalScores
    coaching: List[Dict[str, str]]

# ===============================
# 3) LLM Prompt
# ===============================

SYSTEM_PROMPT = """
You are an expert evaluator specializing in Cognitive Interview (CI/ECI) techniques for aviation accident investigations. Your task is to assess ONLY the interviewer's performance (marked as "user" in the transcript), not the interviewee.

CRITICAL INSTRUCTIONS:
1. Extract and classify only genuine questions from the interviewer. Do not classify or count supportive/rapport statements, instructions, framing/context sentences, or gratitude/transition phrases as questions.
2. Identify the presence of specific CI phases based on clear evidence
3. Evaluate behavioral competencies using consistent criteria (be fair rather than punitive)
4. Calculate quantitative metrics only from genuine questions you identified, not from supportive statements or instructions

=== QUESTION CLASSIFICATION CRITERIA ===

DEFINITIONS — WHAT COUNTS AS A QUESTION
- A genuine question typically ends with a question mark or clearly seeks information (interrogative form).
- Supportive/rapport statements (e.g., reassurance, appreciation, instructions like "Take a moment to close your eyes...") are NOT questions and must be excluded from the questions list and all metrics.
- Mixed turns that include an instruction or framing plus a question: only classify the actual question part. Do not count the instruction part as a separate question.

=== QUESTION CLASSIFICATION CRITERIA (RELAXED & FAIR) ===

**open_ended**: Questions that invite free narrative without constraints
- Examples: "Can you tell me what happened?", "Describe the sequence of events", "What do you remember about...", "Can you walk me through what happened?"
- Must allow the interviewee to tell their story in their own words
- Should not limit the scope of the response
- Questions asking for descriptions, narratives, or explanations are open_ended
- Questions with "what", "how", "describe", "tell me about" are typically open_ended

**closed**: Questions requiring specific, limited responses
- Examples: "How many people were there?", "What time did this occur?", "Was the weather clear?"
- Yes/no questions, specific factual queries
- Limits the response to particular information

**leading**: Questions that strongly suggest answers or contain explicit assumptions
- Examples: "You must have been scared, weren't you?", "Did the loud noise cause you to panic?", "You were probably terrified, right?"
- Requires clear suggestion or assumption (e.g., presupposed cause/feeling or tag-question pressure)
- Must contain explicit assumptions about what the person felt, thought, or experienced
- Mild framing or context-setting is NOT leading

**compound**: Multiple distinct questions asked in a single turn
- Contains two or more separate interrogatives that should be asked individually
- Mere framing + one actual question is NOT compound. Must be clearly two or more separate questions to label compound.

**clarifying**: Questions that seek to verify or expand on information just provided
- Examples: "When you say 'loud noise', can you describe it more?", "You mentioned feeling dizzy - can you tell me more about that?"
- Must directly reference something the interviewee just said
- Should not introduce new topics or assumptions

=== COGNITIVE INTERVIEW PHASES ===

**rapport_safety** (True/False): Evidence of establishing trust and psychological safety
- Explicit statements about confidentiality, no judgment, ability to pause/stop
- Acknowledgment of difficulty in discussing the event
- Clear indicators of creating a supportive environment

**context_reinstatement** (True/False): Attempts to help interviewee mentally return to the event
- Questions about environmental factors (sounds, smells, lighting, weather, physical sensations)
- Instructions to "put yourself back in that moment" or similar
- Systematic exploration of contextual details

**free_recall** (True/False): Inviting uninterrupted narrative account
- Open invitations to tell the story from start to finish
- Minimal interruptions during initial narrative
- Questions like "Tell me everything you remember" or "Start from the beginning"

**varied_focused_retrieval** (True/False): Using different retrieval strategies
- Asking to recall events in reverse chronological order
- Changing perspective ("What would someone else have seen?")
- Focusing on different sensory modalities
- Multiple attempts to retrieve additional details using varied approaches

**closure** (True/False): Proper ending of the interview
- Opportunity for interviewee to add anything else
- Summary of key points
- Clear conclusion to the interview process

=== BEHAVIORAL ASSESSMENT CRITERIA ===

**active_listening**: 
- good: Regular paraphrasing, summarizing, and confirming understanding before proceeding
- fair: Some evidence of listening (occasional confirmation, basic acknowledgment)
- poor: Minimal listening indicators, jumps between topics without confirmation
- absent: No evidence of active listening techniques

**neutral_language**:
- good: Consistently neutral, non-judgmental language throughout
- fair: Mostly neutral with occasional minor lapses
- poor: Multiple instances of biased, judgmental, or leading language

**contamination_risk**:
- low: No introduction of external information or hypotheses
- medium: Minor instances of suggesting possibilities or introducing external context
- high: Frequent introduction of external information, theories, or assumptions not from interviewee

**pacing_ok**:
- good: Allows adequate time for responses, no interruptions, appropriate silence
- fair: Generally good pacing with minor rushes or interruptions
- poor: Frequent interruptions, rushing, not allowing time for reflection

**trauma_informed**:
- good: Clear empathy, acknowledges difficulty, offers control to interviewee
- fair: Some empathy shown, basic sensitivity to emotional state
- poor: Little to no acknowledgment of emotional impact or trauma considerations

=== QUANTITATIVE METRICS (COUNT ONLY GENUINE QUESTIONS) ===

Calculate these metrics precisely based on your question classifications. Exclude supportive/rapport/transition/ instruction-only turns from both the numerator and denominator:

**open_rate**: (Number of open_ended questions) / (Total number of genuine interviewer questions)
**leading_rate**: (Number of leading questions) / (Total number of genuine interviewer questions) 
**emotion_regulation**: Based on the emotion timeline provided, calculate the proportion of time/interactions where the interviewer maintains appropriate emotional stability (0.0 to 1.0 scale)

=== OUTPUT FORMAT ===

Return ONLY a JSON object with this exact structure:
{
  "interviewer": {
    "questions": [
      {"text": "exact question text", "label": "classification"},
      ...
    ],
    "ci_phases": {
      "rapport_safety": boolean,
      "context_reinstatement": boolean,
      "free_recall": boolean,
      "varied_focused_retrieval": boolean,
      "closure": boolean
    },
    "behaviors": {
      "active_listening": "good/fair/poor/absent",
      "neutral_language": "good/fair/poor",
      "contamination_risk": "low/medium/high",
      "pacing_ok": "good/fair/poor",
      "trauma_informed": "good/fair/poor"
    },
    "quantitative_metrics": {
      "open_rate": 0.00,
      "leading_rate": 0.00,
      "emotion_regulation": 0.00
    }
  }
}

Be precise, evidence-based, and consistent in your evaluations.
"""

USER_PROMPT_TEMPLATE = """
=== EVALUATION TASK ===

Please analyze the following aviation accident investigation interview and evaluate the interviewer's performance using Cognitive Interview (CI) principles.

=== TRANSCRIPT DATA ===
The transcript contains turns between:
- "user" = the interviewer (student being evaluated)
- "bot" = the interviewee (simulated witness/victim)

Transcript:
{transcript_json}

=== INTERVIEWER EMOTION TIMELINE ===
This tracks the interviewer's emotional state throughout the interview:
{emotions_json}

=== INSTRUCTIONS ===

1. **Extract all interviewer questions**: Identify every question asked by the "user" (interviewer)

2. **Classify each question**: Use the exact question text and assign one label: open_ended, closed, leading, compound, or clarifying

3. **Identify CI phases**: Mark as True only if there is clear, explicit evidence of each phase in the interviewer's behavior

4. **Evaluate behaviors**: Assess each behavioral dimension based on observable evidence throughout the interview

5. **Calculate metrics**: 
   - Count your question classifications to compute open_rate and leading_rate
   - Use the emotion timeline to assess emotion_regulation (proportion of stable/appropriate emotional states)

6. **Output format**: Return exactly the JSON structure specified in the system prompt, with precise numerical values

Focus on evidence-based evaluation. If something is not clearly demonstrated, mark it accordingly rather than making assumptions.
"""

# ===============================
# 4) LLM Call
# ===============================

def run_llm(
    transcript: List[Dict[str, Any]],
    emotions: List[Dict[str, Any]],
    model: str = "gemma3"
) -> LLMJudgement:
    chat = ChatOllama(
        model=os.getenv("OLLAMA_MODEL_NAME", model),
        base_url=os.getenv("OLLAMA_MODEL_URL", "http://localhost:11434"),
        temperature=0.0
    )

    t_json = json.dumps(transcript, ensure_ascii=False, indent=2)
    e_json = json.dumps(emotions, ensure_ascii=False, indent=2)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        transcript_json=t_json,
        emotions_json=e_json
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    response = chat.invoke(messages)
    raw = response.content.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # JSON repair for Gemma / Ollama verbosity
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(raw[start:end + 1])
        else:
            raise

    try:
        return LLMJudgement(**data)
    except ValidationError:
        print("Validation error from Ollama output. Raw response:")
        print(raw)
        raise


# ===============================
# 5) Scoring logic
# ===============================

def compute_scores(j: LLMJudgement) -> FinalScores:
    interviewer = j.interviewer
    
    # A1: Open-ended rate
    open_rate = interviewer.quantitative_metrics.open_rate
    if open_rate >= THRESHOLDS["A1_open_rate"]["good"]:
        A1 = WEIGHTS["A1"]
    elif open_rate >= THRESHOLDS["A1_open_rate"]["fair"]:
        A1 = 0.7 * WEIGHTS["A1"]
    else:
        A1 = 0.0

    # A2: Leading rate (inverse)
    leading_rate = interviewer.quantitative_metrics.leading_rate
    if leading_rate <= THRESHOLDS["A2_leading_rate"]["good"]:
        A2 = WEIGHTS["A2"]
    elif leading_rate <= THRESHOLDS["A2_leading_rate"]["fair"]:
        A2 = 0.7 * WEIGHTS["A2"]
    else:
        A2 = 0.0

    # A3: CI phase adherence – count True
    phases = interviewer.ci_phases
    phase_count = sum([
        phases.rapport_safety,
        phases.context_reinstatement,
        phases.free_recall,
        phases.varied_focused_retrieval,
        phases.closure
    ])
    # Each phase worth equally within A3
    A3 = WEIGHTS["A3"] * (phase_count / 5.0)

    # A4: Pacing
    pacing_map = {"good": 1.0, "fair": 0.6, "poor": 0.0}
    A4 = WEIGHTS["A4"] * pacing_map.get(interviewer.behaviors.pacing_ok, 0.0)

    # A5: Neutrality & Plain language
    A5_map = {"good": 1.0, "fair": 0.6, "poor": 0.0}
    A5 = WEIGHTS["A5"] * A5_map.get(interviewer.behaviors.neutral_language, 0.0)

    # B6: Trauma-informed empathy
    B6_map = {"good": 1.0, "fair": 0.66, "poor": 0.0}
    B6 = WEIGHTS["B6"] * B6_map.get(interviewer.behaviors.trauma_informed, 0.0)

    # B7: Active listening
    B7_map = {"good": 1.0, "fair": 0.6, "poor": 0.2, "absent": 0.0}
    B7 = WEIGHTS["B7"] * B7_map.get(interviewer.behaviors.active_listening, 0.0)

    # B8: Emotion regulation
    emo = interviewer.quantitative_metrics.emotion_regulation
    if emo >= THRESHOLDS["B8_emoreg_good"]:
        B8 = WEIGHTS["B8"]
    elif emo >= THRESHOLDS["B8_emoreg_fair"]:
        B8 = 0.6 * WEIGHTS["B8"]
    else:
        B8 = 0.0

    # C9: Structured approach – infer from phases + behaviors
    # Heuristic: if >=4 phases present and neutral_language not poor => structured=good,
    # elif >=3 phases => fair, else poor
    if phase_count >= 4 and interviewer.behaviors.neutral_language != "poor":
        C9 = WEIGHTS["C9"]
        c9_pass = "good"
    elif phase_count >= 3:
        C9 = 0.6 * WEIGHTS["C9"]
        c9_pass = "fair"
    else:
        C9 = 0.0
        c9_pass = "poor"

    # C10: Contamination-safe
    cont_map = {"low": 1.0, "medium": 0.6, "high": 0.0}
    C10 = WEIGHTS["C10"] * cont_map.get(interviewer.behaviors.contamination_risk, 0.0)

    scores = {
        "A1": round(A1, 2),
        "A2": round(A2, 2),
        "A3": round(A3, 2),
        "A4": round(A4, 2),
        "A5": round(A5, 2),
        "B6": round(B6, 2),
        "B7": round(B7, 2),
        "B8": round(B8, 2),
        "C9": round(C9, 2),
        "C10": round(C10, 2),
    }
    total = round(sum(scores.values()), 2)

    # Determine which metrics "pass":
    # Rule of thumb: pass when full weight achieved or phase-weight >= 80% for A3
    metrics_passed = []
    if A1 == WEIGHTS["A1"]: metrics_passed.append("A1")
    if A2 == WEIGHTS["A2"]: metrics_passed.append("A2")
    if A3 >= 0.8 * WEIGHTS["A3"]: metrics_passed.append("A3")
    if A4 == WEIGHTS["A4"]: metrics_passed.append("A4")
    if A5 == WEIGHTS["A5"]: metrics_passed.append("A5")
    if B6 == WEIGHTS["B6"]: metrics_passed.append("B6")
    if B7 == WEIGHTS["B7"]: metrics_passed.append("B7")
    if B8 == WEIGHTS["B8"]: metrics_passed.append("B8")
    if C9 == WEIGHTS["C9"]: metrics_passed.append("C9")
    if C10 == WEIGHTS["C10"]: metrics_passed.append("C10")

    if total >= PASS_BANDS["overall_pass"]:
        verdict = "PASS"
    elif total >= PASS_BANDS["overall_borderline"]:
        verdict = "BORDERLINE"
    else:
        verdict = "FAIL"

    return FinalScores(scores=scores, total=total, metrics_passed=metrics_passed, verdict=verdict)

# ===============================
# 6) Coaching feedback (simple)
# ===============================

def make_coaching(j: LLMJudgement) -> List[Dict[str, str]]:
    tips = []
    interviewer = j.interviewer
    
    # Leading questions analysis
    if interviewer.quantitative_metrics.leading_rate > THRESHOLDS["A2_leading_rate"]["good"]:
        tips.append({
            "area": "Reduce Leading Questions", 
            "tip": "Avoid questions that suggest answers or contain assumptions. Instead of 'Did you panic when...', use 'What was your experience when...'. Replace 'You must have felt...' with 'How did you feel...'. This prevents contaminating the witness's memory with your assumptions."
        })
    
    # Open-ended questions improvement
    if interviewer.quantitative_metrics.open_rate < THRESHOLDS["A1_open_rate"]["good"]:
        tips.append({
            "area": "Increase Open-Ended Questions", 
            "tip": "Prioritize questions that invite free narrative responses. Use phrases like 'Tell me about...', 'Describe what happened...', 'Can you walk me through...'. Aim for at least 60% of your questions to be open-ended to allow witnesses to provide rich, uncontaminated accounts."
        })
    
    # CI Phases assessment
    phases = interviewer.ci_phases
    
    if not phases.rapport_safety:
        tips.append({
            "area": "Establish Rapport and Safety", 
            "tip": "Begin interviews by explicitly establishing psychological safety. Say something like: 'This is a safe space to share your experience. There are no right or wrong answers, and we can pause or stop anytime you need.' This helps witnesses feel comfortable sharing difficult memories."
        })
    
    if not phases.context_reinstatement:
        tips.append({
            "area": "Context Reinstatement", 
            "tip": "Help the witness mentally return to the event by asking about environmental details: 'What did you see/hear/smell/feel?' 'What was the lighting like?' 'Describe the sounds around you.' This technique enhances memory retrieval by recreating the original encoding context."
        })
    
    if not phases.free_recall:
        tips.append({
            "area": "Free Recall Phase", 
            "tip": "After establishing context, invite an uninterrupted narrative: 'Please tell me everything you remember from start to finish, even small details that might seem unimportant.' Allow the witness to speak without interruption to get their complete account first."
        })
    
    if not phases.varied_focused_retrieval:
        tips.append({
            "area": "Varied Retrieval Techniques", 
            "tip": "After free recall, use different approaches to retrieve additional details: ask them to recall events in reverse order, change perspective ('What would someone else have seen?'), or focus on different senses. This accesses memory through multiple pathways."
        })
    
    if not phases.closure:
        tips.append({
            "area": "Interview Closure", 
            "tip": "End interviews properly by asking 'Is there anything else you'd like to add?' and summarizing key points. Thank the witness for their time and provide information about next steps if appropriate. This ensures completeness and maintains rapport."
        })
    
    # Behavioral competencies
    if interviewer.behaviors.trauma_informed != "good":
        tips.append({
            "area": "Trauma-Informed Approach", 
            "tip": "Show greater empathy and sensitivity to the emotional impact of the event. Acknowledge the difficulty: 'I know this is difficult to discuss.' Offer control: 'We can take breaks whenever you need.' Watch for signs of distress and respond appropriately."
        })
    
    if interviewer.behaviors.active_listening in ("absent", "poor"):
        tips.append({
            "area": "Active Listening Skills", 
            "tip": "Demonstrate active listening by occasionally paraphrasing what you heard: 'So if I understand correctly, you're saying...' and 'Let me make sure I have this right...' This shows the witness you're paying attention and helps clarify information before moving forward."
        })
    
    if interviewer.behaviors.neutral_language == "poor":
        tips.append({
            "area": "Neutral Language", 
            "tip": "Use more neutral, non-judgmental language. Avoid words that imply blame or assumptions about what happened. Replace emotional or loaded terms with neutral descriptors. This prevents introducing bias into the witness's account."
        })
    
    if interviewer.behaviors.contamination_risk == "high":
        tips.append({
            "area": "Reduce Contamination Risk", 
            "tip": "Avoid introducing external information or your own theories about what happened. Let the witness provide all details from their own memory. Don't suggest what might have happened or reference information from other sources during the interview."
        })
    
    if interviewer.behaviors.pacing_ok == "poor":
        tips.append({
            "area": "Interview Pacing", 
            "tip": "Allow more time for the witness to think and respond. Use comfortable silences - count to 5 before asking follow-up questions. Avoid interrupting when the witness is speaking. Remember that memory retrieval takes time, especially for traumatic events."
        })
    
    # Emotion regulation feedback
    if interviewer.quantitative_metrics.emotion_regulation < THRESHOLDS["B8_emoreg_good"]:
        tips.append({
            "area": "Emotional Self-Regulation", 
            "tip": "Work on maintaining emotional stability throughout the interview. Practice techniques to manage your own emotional responses to difficult content. Your calm, professional demeanor helps the witness feel safe and supported. Consider taking brief pauses if you need to regulate your emotions."
        })
    
    return tips

# ===============================
# 7) Public API
# ===============================

def evaluate_ci_performance(transcript: List[Dict[str, Any]],
                            emotions: List[Dict[str, Any]],
                            model: str = "gpt-4o-mini") -> EvaluationResult:
    llm_out = run_llm(transcript, emotions, model=model)
    scoring = compute_scores(llm_out)
    coaching = make_coaching(llm_out)
    return EvaluationResult(llm=llm_out, scoring=scoring, coaching=coaching)

# ===============================
# 8) Demo
# ===============================

# Sample transcript with your teacher's questions
SAMPLE_TRANSCRIPT = [
    {"speaker": "user", "text": "How are you?", "ts": "2025-08-17T10:00:00Z"},
    {"speaker": "bot",  "text": "I'm okay, thank you. A bit nervous about talking about this.", "ts": "2025-08-17T10:00:10Z"},
    {"speaker": "user", "text": "There's no need to be anxious. We're really just here to try and find out as much information as we can so that we can try and figure out what happened and make sure it doesn't happen again. So there's no need for you to be anxious at all. I really appreciate your time today, so thank you for coming in to speak to me.", "ts": "2025-08-17T10:00:20Z"},
    {"speaker": "bot",  "text": "Thank you, I appreciate that.", "ts": "2025-08-17T10:00:30Z"},
    {"speaker": "user", "text": "Okay, maybe I can take you back, Lyn, to before that event. If you can just...", "ts": "2025-08-17T10:00:40Z"},
    {"speaker": "bot",  "text": "Yes, I can try.", "ts": "2025-08-17T10:00:45Z"},
    {"speaker": "user", "text": "Take a moment to close your eyes and think back...", "ts": "2025-08-17T10:00:50Z"},
    {"speaker": "bot",  "text": "Okay, I'm thinking back...", "ts": "2025-08-17T10:01:00Z"},
    {"speaker": "user", "text": "So, can you think back to before the noise happened? What was the flight like?", "ts": "2025-08-17T10:01:10Z"},
    {"speaker": "bot",  "text": "The flight was normal at first. We had just taken off and were climbing when I heard this loud bang.", "ts": "2025-08-17T10:01:20Z"},
    {"speaker": "user", "text": "So after the noise and vibration occurred, can you walk me through what else you heard and what else happened on the flight?", "ts": "2025-08-17T10:01:30Z"},
    {"speaker": "bot",  "text": "Well, there was a lot of commotion. People were shouting, the cabin crew were trying to calm everyone down.", "ts": "2025-08-17T10:01:40Z"},
    {"speaker": "user", "text": "I'll just get you to think back to the cockpit prior to the noise. Can you just have one more reflection? Was there anything abnormal, was there any conversations going on in the cockpit that may have caused concern?", "ts": "2025-08-17T10:01:50Z"},
    {"speaker": "bot",  "text": "I couldn't see into the cockpit, but I didn't notice anything unusual before the noise.", "ts": "2025-08-17T10:02:00Z"},
    {"speaker": "user", "text": "Thanks Lyn. So after the noise had happened, can you talk a little bit more about what the pilots did in response to that noise?", "ts": "2025-08-17T10:02:10Z"},
    {"speaker": "bot",  "text": "I could hear them talking on the intercom, and the plane started to turn. They seemed to be trying to get back to the airport.", "ts": "2025-08-17T10:02:20Z"},
    {"speaker": "user", "text": "Lyn, from your observations of what was going on between the pilot and co-pilot, what did you think the issue that they had identified was?", "ts": "2025-08-17T10:02:30Z"},
    {"speaker": "bot",  "text": "I think they thought it was some kind of engine problem, maybe a bird strike.", "ts": "2025-08-17T10:02:40Z"},
    {"speaker": "user", "text": "Thanks Lyn. So once they identified that there had been some sort of bird strike or drone, what actions did they take in terms of piloting the aircraft?", "ts": "2025-08-17T10:02:50Z"},
    {"speaker": "bot",  "text": "They declared an emergency and started heading back to the airport. The plane was shaking quite a bit.", "ts": "2025-08-17T10:03:00Z"},
    {"speaker": "user", "text": "Thank you Lyn. Is there anything else you'd like to add before we finish?", "ts": "2025-08-17T10:03:10Z"},
    {"speaker": "bot",  "text": "No, I think that's everything I can remember.", "ts": "2025-08-17T10:03:20Z"}
]

SAMPLE_EMOTIONS = [
    {"ts": "2025-08-17T10:00:00Z", "emotion_label": "calm"},
    {"ts": "2025-08-17T10:00:20Z", "emotion_label": "calm"},
    {"ts": "2025-08-17T10:01:00Z", "emotion_label": "calm"},
    {"ts": "2025-08-17T10:02:00Z", "emotion_label": "calm"},
    {"ts": "2025-08-17T10:03:00Z", "emotion_label": "calm"}
]

def main():
    print("Running CI scoring demo...")
    result = evaluate_ci_performance(SAMPLE_TRANSCRIPT, SAMPLE_EMOTIONS, model="gpt-4o-mini")
    print("\n=== LLM Judgement ===")
    print(json.dumps(result.llm.model_dump(), ensure_ascii=False, indent=2))
    print("\n=== Scores ===")
    print(json.dumps(result.scoring.model_dump(), ensure_ascii=False, indent=2))
    print("\n=== Coaching ===")
    print(json.dumps(result.coaching, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()