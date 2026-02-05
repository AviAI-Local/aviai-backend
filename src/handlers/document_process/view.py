from fastapi import APIRouter, UploadFile, File, HTTPException
from .service import process_document
from .schema import DocumentExtractResp

router = APIRouter()


@router.post(
    "/extract",
    response_model=DocumentExtractResp,
)
async def extract_document(file: UploadFile = File(...)):
    """
    Upload a document (.txt, .pdf, .docx) and extract structured data + LLM metadata.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    try:
        return await process_document(file)
    except ValueError as e:
        # Unsupported file type or parsing issue
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch-all for LLM / parsing failures
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Failed to process document"
        )
