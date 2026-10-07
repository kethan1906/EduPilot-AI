from exceptions import DocumentError


def extract_pdf_pages(file):
    """Read an uploaded PDF from memory; return [{"page": n, "text": str}, ...].

    Pages without extractable text (e.g. scanned images) are skipped.
    """
    import fitz  # PyMuPDF

    data = file.read()
    try:
        pdf = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise DocumentError("Could not read the PDF. The file may be corrupt.") from exc

    try:
        if pdf.needs_pass:
            raise DocumentError("The PDF is password-protected and cannot be read.")
        pages = []
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            if text.strip():
                pages.append({"page": page_number, "text": text})
        return pages
    finally:
        pdf.close()
