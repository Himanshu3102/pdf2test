import io
from fpdf import FPDF


def make_text_pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Sample Exam\n\n1. What is 2+2?\nA) 3\nB) 4\nC) 5\nD) 6\nAnswer: B\nExplanation: 2+2=4\n\n2. Select primes.\nA) 2\nB) 3\nC) 4\nD) 5\nAnswer: A, B, D\n\n3. Enter value of pi approx.\nAnswer: 3.14\nTolerance: 0.01\n")
    return bytes(pdf.output(dest="S"))
