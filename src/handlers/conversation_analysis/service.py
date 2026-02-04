import json
from typing import Dict, Any
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from .summary_chain import get_conversation_summary_chain
from .chain import analyze_conversation

from .model import ConversationHistoryInput, ConversationAnalysisOutput
from .pdf_styles import get_style, DEFAULT_STYLE


def _wrap_text(text: str, style, story: list, cfg: dict):
    """Append text as wrapped Paragraphs to story list."""
    threshold = cfg["wrap_threshold"]
    max_line = cfg["wrap_line_length"]
    if len(text) > threshold:
        words = text.split()
        lines, current = [], ""
        for word in words:
            if len(current + " " + word) <= max_line:
                current += " " + word if current else word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        for line in lines:
            story.append(Paragraph(line, style))
    else:
        story.append(Paragraph(text, style))


def convert_timestamp_to_readable(timestamp: float, base_timestamp: float) -> str:
    """
    Convert Unix timestamp to readable time format in MM:SS format
    """
    # Calculate seconds from base timestamp
    total_seconds = int(timestamp - base_timestamp)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def calculate_conversation_times(conversation_history: list) -> list:
    """
    Calculate time offsets for each conversation entry
    """
    if not conversation_history:
        return []
    
    # Get the first timestamp as base
    base_timestamp = conversation_history[0]["timestamp"]
    
    # Calculate time for each entry
    times = []
    for entry in conversation_history:
        time_str = convert_timestamp_to_readable(entry["timestamp"], base_timestamp)
        times.append(time_str)
    
    return times


def create_pdf_from_analysis(analysis_data: ConversationAnalysisOutput, analysis_id: str = None, style: str = DEFAULT_STYLE) -> bytes:
    """Create a PDF from conversation analysis data with improved layout."""
    cfg = get_style(style)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=cfg["margin"], leftMargin=cfg["margin"],
        topMargin=cfg["margin"], bottomMargin=cfg["margin"],
    )
    story = []

    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=cfg["title_font_size"], spaceAfter=30,
        alignment=1, textColor=cfg["heading_color"],
    )
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'],
        fontSize=cfg["heading_font_size"], spaceAfter=12,
        spaceBefore=20, textColor=cfg["heading_color"],
    )
    normal_style = ParagraphStyle(
        'CustomNormal', parent=styles['Normal'],
        fontSize=cfg["body_font_size"], spaceAfter=6, leading=14,
    )
    analysis_style = ParagraphStyle(
        'AnalysisStyle', parent=styles['Normal'],
        fontSize=cfg["analysis_font_size"], spaceAfter=8,
        leading=14, leftIndent=20,
    )
    field_style = ParagraphStyle(
        'FieldStyle', parent=styles['Normal'],
        fontSize=cfg["body_font_size"], spaceAfter=4,
        leading=12, leftIndent=30,
    )

    # Title
    story.append(Paragraph(cfg["title"], title_style))
    story.append(Spacer(1, 20))

    # Analysis ID
    if analysis_id:
        story.append(Paragraph("Analysis Information", heading_style))
        story.append(Paragraph(f"<b>Analysis ID:</b> {analysis_id}", normal_style))
        story.append(Spacer(1, 20))

    # Summary
    story.append(Paragraph("Conversation Summary", heading_style))
    _wrap_text(analysis_data.summary, normal_style, story, cfg)
    story.append(Spacer(1, 20))

    # Emotion analysis timeline
    story.append(Paragraph("Emotion Analysis Timeline", heading_style))

    for i, entry in enumerate(analysis_data.analysis, 1):
        story.append(Paragraph(f"<b>Entry {i} - Time: {entry.time}</b>", analysis_style))
        story.append(Paragraph("<b>Emotion Analysis:</b>", field_style))
        _wrap_text(entry.user_emotion_analysis, field_style, story, cfg)
        story.append(Spacer(1, 15))

        if i < len(analysis_data.analysis):
            story.append(Paragraph("<hr/>", normal_style))
            story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()


async def analyze_conversation_history(conversation_data: Dict[str, Any]) -> ConversationAnalysisOutput:
    """
    Analyze conversation history using LLM
    """
    # Validate input data
    input_model = ConversationHistoryInput(**conversation_data)
    
    # Calculate times for each conversation entry
    times = calculate_conversation_times(conversation_data["conversation_history"])
    
    # Prepare data for LLM (without time, only emotion analysis)
    llm_data = {
        "conversation_history": []
    }
    
    for entry in conversation_data["conversation_history"]:
        llm_entry = {
            "user_query": entry["user_query"],
            "user_emotion": entry["user_emotion"],
            "response": entry["response"]
        }
        llm_data["conversation_history"].append(llm_entry)
    
    # Convert to JSON string for LLM processing
    conversation_json = json.dumps(llm_data, indent=2)
    
    # Process with LLM to get emotion analysis
    llm_result =  await analyze_conversation({
    "conversation_data": conversation_json
})
    summary_chain = get_conversation_summary_chain()
    # Generate conversation summary
    summary_result = await summary_chain.ainvoke({
    "conversation_data": conversation_json
})
    
    # Combine calculated times with LLM emotion analysis
    analysis_entries = []
    for i, emotion_analysis in enumerate(llm_result.analysis):
        analysis_entry = {
            "time": times[i],
            "user_emotion_analysis": emotion_analysis.user_emotion_analysis
        }
        analysis_entries.append(analysis_entry)
    
    return ConversationAnalysisOutput(
        analysis=analysis_entries,
        summary=summary_result.conversation_summary
    )


async def process_conversation_analysis(conversation_json: str) -> ConversationAnalysisOutput:
    """
    Main function to process conversation analysis
    """
    try:
        # Parse JSON input
        conversation_data = json.loads(conversation_json)
        
        # Analyze conversation
        result = await analyze_conversation_history(conversation_data)
        
        return result
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    except Exception as e:
        raise Exception(f"Error processing conversation analysis: {e}") 