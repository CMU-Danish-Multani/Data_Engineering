"""Render the Milestone 1 and Milestone 2 PDFs from proposalSource.html.

The source marks sections with m1only / m2only classes; the body class picks
which variant prints. Requires Google Chrome (headless print to PDF).
"""

import subprocess
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
VARIANTS = {"m1": "milestone1Proposal.pdf", "m2": "milestone2Report.pdf"}


def renderVariant(source: Path, variant: str, outPdf: Path, chrome: Path = CHROME) -> None:
    html = source.read_text().replace('<body class="m1">', f'<body class="{variant}">', 1)
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=source.parent, delete=False) as tmp:
        tmp.write(html)
        tmpPath = Path(tmp.name)
    try:
        subprocess.run(
            [str(chrome), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={outPdf}", tmpPath.as_uri()],
            check=True, capture_output=True,
        )
    finally:
        tmpPath.unlink()


def main(projectDir: Path = PROJECT_DIR) -> None:
    source = projectDir / "proposalSource.html"
    for variant, pdfName in VARIANTS.items():
        renderVariant(source, variant, projectDir / pdfName)
        print(f"wrote {pdfName}")


if __name__ == "__main__":
    main()
