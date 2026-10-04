"""Generate the demo printable (good_corporate) with AcroForm fields.

The real product prints from form pdfs (e.g. formpdfs/TY24/WVST/printables/SchNIPA2.pdf);
this synthesized stand-in exists so the render-layer check has something to read.
Needs: python -m pip install reportlab
"""
from pathlib import Path

from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "fixtures" / "pdf" / "SchNIPA2_good.pdf"

FIELDS = [
    ("SchNIPA2.EntityType", "corporate"),
    ("SchNIPA2.Line4", "92500.50"),
    ("SchNIPA2.RemainingNIPACredit", "0.00"),
]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT))
    c.setFont("Helvetica", 10)
    c.drawString(72, 760, "WV/NIPA-2 - Neighborhood Investment Program Credit (demo printable)")
    y = 720
    for name, value in FIELDS:
        c.drawString(72, y, name.split(".")[-1])
        c.acroForm.textfield(name=name, value=value, x=220, y=y - 3,
                             width=120, height=16, borderWidth=0, forceBorder=False)
        y -= 28
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
