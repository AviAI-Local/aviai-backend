import json
import base64
from typing import Dict, Any
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from .summary_chain import conversation_summary_chain
from .chain import analyze_conversation

from .model import ConversationHistoryInput, ConversationAnalysisOutput, LLMEmotionAnalysisOutput


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


def create_pdf_from_analysis(analysis_data: ConversationAnalysisOutput, analysis_id: str = None) -> bytes:
    """Create a PDF from conversation analysis data with improved layout."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                          rightMargin=0.5*inch, leftMargin=0.5*inch,
                          topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.darkblue
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.darkblue
    )
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        leading=14
    )
    analysis_style = ParagraphStyle(
        'AnalysisStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        leading=14,
        leftIndent=20
    )
    field_style = ParagraphStyle(
        'FieldStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4,
        leading=12,
        leftIndent=30
    )
    
    # Add title
    story.append(Paragraph("Conversation Analysis Report", title_style))
    story.append(Spacer(1, 20))
    
    # Add analysis details
    if analysis_id:
        story.append(Paragraph("Analysis Information", heading_style))
        story.append(Paragraph(f"<b>Analysis ID:</b> {analysis_id}", normal_style))
        story.append(Spacer(1, 20))
    
    # Add summary section
    story.append(Paragraph("Conversation Summary", heading_style))
    summary_text = analysis_data.summary
    if len(summary_text) > 100:
        # Split long text into paragraphs
        words = summary_text.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line + " " + word) <= 80:
                current_line += " " + word if current_line else word
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        for line in lines:
            story.append(Paragraph(line, normal_style))
    else:
        story.append(Paragraph(summary_text, normal_style))
    
    story.append(Spacer(1, 20))
    
    # Add emotion analysis section
    story.append(Paragraph("Emotion Analysis Timeline", heading_style))
    
    for i, entry in enumerate(analysis_data.analysis, 1):
        story.append(Paragraph(f"<b>Entry {i} - Time: {entry.time}</b>", analysis_style))
        
        # Add emotion analysis
        story.append(Paragraph(f"<b>Emotion Analysis:</b>", field_style))
        emotion_analysis = entry.user_emotion_analysis
        if len(emotion_analysis) > 100:
            # Split long text into paragraphs
            words = emotion_analysis.split()
            lines = []
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= 80:
                    current_line += " " + word if current_line else word
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            for line in lines:
                story.append(Paragraph(line, field_style))
        else:
            story.append(Paragraph(emotion_analysis, field_style))
        
        story.append(Spacer(1, 15))
        
        # Add a separator line between entries
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
    
    # Generate conversation summary
    summary_result = await conversation_summary_chain.ainvoke({
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